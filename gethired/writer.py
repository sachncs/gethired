"""Writer agent.

The main tailoring agent. Takes the master resume, JD analysis, and voice
profile; produces a TailoredResume. Emits Job records for traceability.

Uses Pydantic AI with read-only tools (per user directive) and Anthropic
provider (which works with both Anthropic native and the MiniMax platform).
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gethired.streaming import ProgressCallback, ProgressEvent

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from gethired.constants import MODEL_ENV_VAR
from gethired.description import DescriptionAnalysis
from gethired.exceptions import ConfigurationError
from gethired.models import (
    Bullet,
    DropReason,
    Experience,
    GroundedCitation,
    Job,
    JobType,
    MasterResume,
    Project,
    SkillsByCategory,
    TailoredResume,
    VoiceProfile,
    job,
)
from gethired.observability import step_logger
from gethired.provider import resolve_model
from gethired.rubric import ANTI_AI_RULES, BANNED_WORDS, GROUNDING_RULES


class WriterDeps:
    """Dependencies injected into the writer agent's RunContext."""

    def __init__(
        self,
        master: MasterResume,
        analysis: DescriptionAnalysis,
        voice: VoiceProfile,
        previous_violations: tuple[str, ...] = (),
    ) -> None:
        self.master = master
        self.analysis = analysis
        self.voice = voice
        self.previous_violations = previous_violations


class WriterOutput(BaseModel):
    """Structured output the writer agent produces.

    Uses flat string lists rather than nested models so Pydantic AI's
    tool-based output validation works reliably across providers
    (including the MiniMax Anthropic-compatible API).

    The agent returns a map of master paths (e.g.
    ``experiences[0].bullets[0]``) to a list of rewritten bullet strings.
    The writer applies these onto the master, preserving canonical
    fields (company, dates, urls, contact, education, awards).
    """

    summary: str = Field(description="Rewritten summary, ≤ 3 sentences")
    tailored_bullets: dict[str, list[str]] = Field(
        description=(
            "Map of master_path (e.g. 'experiences[0].bullets[0]') to a list "
            "of rewritten bullet strings. The first string replaces the master bullet."
        )
    )
    dropped: list[str] = Field(
        default_factory=list,
        description="Master paths to drop, with reason in rationale",
    )
    rationale: str = Field(description="One-sentence explanation of tailoring choices")


class Writer:
    """Main tailoring agent.

    Delegates to Pydantic AI's Agent with read-only tools and
    Anthropic-compatible API. Either ``model`` or ``model_instance`` must be
    provided; otherwise ``ConfigurationError`` is raised at ``tailor()`` time.
    """

    def __init__(
        self,
        model: str | None = None,
        debug: bool = False,
        model_instance: object | None = None,
    ) -> None:
        self._model_string = model or os.environ.get(MODEL_ENV_VAR)
        self._debug = debug
        self._logger = step_logger("writer")
        self._model_instance = model_instance

    def tailor(
        self,
        master: MasterResume,
        analysis: DescriptionAnalysis,
        voice: VoiceProfile,
        previous_violations: tuple[str, ...] = (),
        on_progress: ProgressCallback | None = None,
    ) -> tuple[TailoredResume, tuple[Job, ...]]:
        """Produce a tailored resume and the Job trail.

        Args:
            master: The canonical master resume.
            analysis: Structured JD analysis.
            voice: Voice profile for fingerprint preservation.
            previous_violations: Style violations from prior retry (if any).
            on_progress: Optional callable invoked with each ``ProgressEvent``
                emitted during the tailoring run.

        Returns:
            Tuple of ``(TailoredResume, jobs)``.
        """
        if self._model_string is None and self._model_instance is None:
            raise ConfigurationError(
                "MODEL is required. Set the MODEL env var (e.g. 'MiniMax-M3', "
                "'anthropic:claude-sonnet-4-5', 'openai:gpt-5') and API_KEY "
                "(or ANTHROPIC_API_KEY / OPENAI_API_KEY), or pass "
                "model_instance=TestModel() for offline tests."
            )
        return self.__llm_tailor(
            master, analysis, voice, previous_violations, on_progress
        )

    # ------------------------------------------------------------------
    # LLM-backed tailoring
    # ------------------------------------------------------------------

    def __llm_tailor(
        self,
        master: MasterResume,
        analysis: DescriptionAnalysis,
        voice: VoiceProfile,
        previous_violations: tuple[str, ...],
        on_progress: ProgressCallback | None = None,
    ) -> tuple[TailoredResume, tuple[Job, ...]]:
        """Run the Pydantic AI Agent against the configured model.

        Args:
            master: The canonical master resume.
            analysis: Structured JD analysis.
            voice: Voice profile for fingerprint preservation.
            previous_violations: Style violations from prior retry (if any).
            on_progress: Optional callable invoked with each ProgressEvent.

        Returns:
            Tuple of ``(TailoredResume, jobs)``.
        """
        if self._model_instance is not None:
            model: Any = self._model_instance
        else:
            resolved = resolve_model(self._model_string)
            model = resolved.model
        deps = WriterDeps(master, analysis, voice, previous_violations)

        if on_progress is not None:
            on_progress(
                ProgressEvent(
                    step="writer",
                    message=f"Invoking agent for {analysis.role}",
                )
            )

        agent: Agent[WriterDeps, WriterOutput] = Agent(
            model,
            deps_type=WriterDeps,
            output_type=WriterOutput,
            instructions=[
                base_instructions(),
                rubric_dynamic_instruction(previous_violations),
                jd_dynamic_instruction(),
                voice_dynamic_instruction(voice),
            ],
        )

        self.__register_read_only_tools(agent)

        result = asyncio.run(agent.run(user_prompt(master, analysis), deps=deps))
        writer_output = result.output
        tool_jobs = jobs_from_tool_calls(result, master)

        tailored = apply_writer_output(master, writer_output, analysis)
        model_name = (
            getattr(model, "model_name", None)
            if not isinstance(model, str)
            else str(model)
        )
        all_jobs = tool_jobs + (
            job(
                JobType.TAILOR,
                outputs=("tailored_resume",),
                rationale=f"LLM produced {len(writer_output.tailored_bullets)} rewritten bullets; rationale: {writer_output.rationale[:100]}",
                model=str(model_name) if model_name else "model",
            ),
        )
        tailored = TailoredResume(
            contact=tailored.contact,
            summary=tailored.summary,
            skills=tailored.skills,
            experiences=tailored.experiences,
            projects=tailored.projects,
            education=tailored.education,
            awards=tailored.awards,
            dropped=tailored.dropped,
            rationale=tailored.rationale,
            grounding=tailored.grounding,
            jobs=all_jobs,
            run_result=None,
        )
        if on_progress is not None:
            on_progress(
                ProgressEvent(
                    step="writer",
                    message=f"Produced {len(writer_output.tailored_bullets)} rewritten bullets",
                    job_type="tailor",
                )
            )
        return tailored, all_jobs

    # ------------------------------------------------------------------
    # Read-only tools
    # ------------------------------------------------------------------

    def __register_read_only_tools(self, agent: Agent[WriterDeps, WriterOutput]) -> None:
        @agent.tool
        async def lookup_experience(
            ctx: RunContext[WriterDeps], role_or_company: str
        ) -> dict[str, Any]:
            """Look up an experience in the master by role or company."""
            master = ctx.deps.master
            lowered = role_or_company.lower()
            for exp in master.experiences:
                if lowered in exp.role.lower() or lowered in exp.company.lower():
                    return asdict(exp)
            return {}

        @agent.tool
        async def lookup_project(
            ctx: RunContext[WriterDeps], name: str
        ) -> dict[str, Any]:
            """Look up a project in the master by name."""
            master = ctx.deps.master
            lowered = name.lower()
            for project in master.projects:
                if lowered in project.name.lower() or lowered in project.url.lower():
                    return asdict(project)
            return {}

        @agent.tool
        async def list_skills(ctx: RunContext[WriterDeps]) -> dict[str, list[str]]:
            """Return the master's skills by category."""
            return {
                category: list(items)
                for category, items in ctx.deps.master.skills.categories.items()
            }

        @agent.tool
        async def list_projects(ctx: RunContext[WriterDeps]) -> list[dict[str, Any]]:
            """Return all projects from the master."""
            return [asdict(p) for p in ctx.deps.master.projects]

        @agent.tool
        async def list_education(ctx: RunContext[WriterDeps]) -> list[dict[str, Any]]:
            """Return all education entries from the master."""
            return [asdict(e) for e in ctx.deps.master.education]

        @agent.tool
        async def list_awards(ctx: RunContext[WriterDeps]) -> list[dict[str, Any]]:
            """Return all awards from the master."""
            return [asdict(a) for a in ctx.deps.master.awards]

        @agent.tool
        async def read_jd_summary(ctx: RunContext[WriterDeps]) -> dict[str, Any]:
            """Return the structured JD analysis the writer is optimising for."""
            analysis = ctx.deps.analysis
            return {
                "role": analysis.role,
                "seniority": analysis.seniority,
                "must_have_skills": list(analysis.must_have_skills),
                "nice_to_have_skills": list(analysis.nice_to_have_skills),
                "keywords_to_mirror": list(analysis.keywords_to_mirror),
                "responsibilities": list(analysis.responsibilities),
            }

    # ---------------------------------------------------------------------------
# Helpers (module-level)
# ---------------------------------------------------------------------------


def rank_experiences(master: MasterResume, analysis: DescriptionAnalysis):
    must_have = {kw.lower() for kw in analysis.must_have_skills}
    nice = {kw.lower() for kw in analysis.nice_to_have_skills}
    scored: list[tuple[int, int, object]] = []
    for idx, exp in enumerate(master.experiences):
        text = " ".join((exp.role, exp.company, *(b.text for b in exp.bullets))).lower()
        score = sum(2 for kw in must_have if kw in text) + sum(1 for kw in nice if kw in text)
        scored.append((score, -idx, exp))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return tuple(item[2] for item in scored)


def reorder_skills(skills: SkillsByCategory, mirror_keywords):
    mirror = [kw.lower() for kw in mirror_keywords]
    new_categories: dict[str, tuple[str, ...]] = {}
    for category, items in skills.categories.items():
        ranked: list[tuple[int, int, str]] = []
        for idx, item in enumerate(items):
            score = sum(2 if item.lower() == kw else 1 for kw in mirror if kw in item.lower())
            ranked.append((score, -idx, item))
        ranked.sort(key=lambda t: (-t[0], t[1]))
        new_categories[category] = tuple(item[2] for item in ranked)
    return SkillsByCategory(categories=new_categories)


def base_instructions() -> str:
    banned_words = ", ".join(sorted(BANNED_WORDS)[:10]) + ", ..."
    return f"""You are gethired's writer agent. Your job: produce a TailoredResume
that matches a job description while staying strictly grounded in the master
resume.

GROUNDING (HARD RULES):
{chr(10).join(f"- {rule}" for rule in GROUNDING_RULES)}

ANTI-AI LANGUAGE (HARD RULES):
{chr(10).join(f"- {rule}" for rule in ANTI_AI_RULES)}

BANNED WORDS (sample): {banned_words}

TOOLS:
You have 7 read-only tools to inspect the master (lookup_experience,
lookup_project, list_skills, list_projects, list_education, list_awards,
read_jd_summary). Use them before claiming any fact. NEVER invent facts.

OUTPUT:
Return a TailoredResume with grounding citations (each tailored bullet must
cite its source master path + verbatim span). Do NOT invent companies,
projects, dates, numbers, or skills."""


def rubric_dynamic_instruction(previous_violations: tuple[str, ...]) -> str:
    if not previous_violations:
        return ""
    return (
        "PRIOR VIOLATIONS TO AVOID (retry constraints):\n"
        + "\n".join(f"- {v}" for v in previous_violations)
    )


def jd_dynamic_instruction() -> str:
    return (
        "Use the read_jd_summary tool to retrieve must-have skills, "
        "nice-to-have skills, and responsibilities. Mirror must-have keywords "
        "in your bullet rewrites — never invent, but rephrase to include them."
    )


def voice_dynamic_instruction(voice: VoiceProfile) -> str:
    verbs = ", ".join(voice.opening_verbs[:5]) or "n/a"
    return (
        f"VOICE PROFILE (preserve):\n"
        f"- avg bullet length: {voice.avg_bullet_length:.0f} chars "
        f"(stddev {voice.bullet_length_stddev:.0f})\n"
        f"- opening verbs to honour: {verbs}\n"
        f"- sentence count per bullet: {voice.sentence_count_per_bullet}"
    )


def user_prompt(master: MasterResume, analysis: DescriptionAnalysis) -> str:
    master_md = master.to_markdown()
    jd_summary = (
        f"Target role: {analysis.role}\n"
        f"Seniority: {analysis.seniority}\n"
        f"Must-have skills: {', '.join(analysis.must_have_skills)}\n"
        f"Nice-to-have: {', '.join(analysis.nice_to_have_skills)}"
    )
    return (
        f"Here is the master resume (single source of truth):\n\n"
        f"{master_md}\n\n"
        f"Here is the structured JD analysis:\n\n{jd_summary}\n\n"
        f"Produce a TailoredResume. Use the read-only tools to verify any "
        f"fact before including it. Every bullet must include a GroundedCitation."
    )


def jobs_from_tool_calls(result: Any, master: MasterResume) -> tuple[Job, ...]:
    """Extract Job records from the agent's tool calls.

    Best-effort: walks ``result.all_messages`` looking for tool-call parts.
    """
    jobs: list[Job] = []
    messages = result.all_messages()
    for message in messages:
        for part in getattr(message, "parts", []):
            part_type = getattr(part, "part_kind", None) or getattr(part, "type", None)
            if part_type == "tool-call" or getattr(part, "tool_name", None):
                tool_name = getattr(part, "tool_name", "unknown")
                jobs.append(
                    job(
                        JobType.LOOKUP,
                        outputs=(f"tool:{tool_name}",),
                        rationale=f"Called read-only tool {tool_name}",
                        model=str(getattr(getattr(message, "model", None), "model_name", "model")),
                        tool_name=tool_name,
                    )
                )
    return tuple(jobs)


def apply_writer_output(
    master: MasterResume,
    output: WriterOutput,
    analysis: DescriptionAnalysis,
) -> TailoredResume:
    """Apply the writer agent's output onto the master resume.

    The agent produces a ``WriterOutput`` (Pydantic) with a flat
    ``tailored_bullets`` map of master paths → rewritten bullet text.
    This function applies those rewrites onto the master, preserving
    canonical fields (company, dates, urls, contact, education, awards).
    """
    new_experiences: list[Experience] = []
    new_grounding: list[GroundedCitation] = []
    for idx, exp in enumerate(master.experiences):
        rewritten_bullets: list[Bullet] = []
        for b_idx, bullet in enumerate(exp.bullets):
            master_path = f"experiences[{idx}].bullets[{b_idx}]"
            if master_path in output.tailored_bullets:
                candidates = output.tailored_bullets[master_path]
                new_text = candidates[0] if candidates else bullet.text
                rewritten_bullets.append(Bullet(text=new_text))
                new_grounding.append(
                    GroundedCitation(
                        tailored_path=master_path,
                        master_path=master_path,
                        verbatim_span=bullet.text,
                        job_id="writer-agent",
                    )
                )
            else:
                rewritten_bullets.append(bullet)
        new_experiences.append(
            Experience(
                role=exp.role,
                company=exp.company,
                start_date=exp.start_date,
                end_date=exp.end_date,
                bullets=tuple(rewritten_bullets),
            )
        )

    new_projects: list[Project] = []
    for p_idx, project in enumerate(master.projects):
        rewritten_bullets = []
        for b_idx, bullet in enumerate(project.bullets):
            master_path = f"projects[{p_idx}].bullets[{b_idx}]"
            if master_path in output.tailored_bullets:
                candidates = output.tailored_bullets[master_path]
                new_text = candidates[0] if candidates else bullet.text
                rewritten_bullets.append(Bullet(text=new_text))
                new_grounding.append(
                    GroundedCitation(
                        tailored_path=master_path,
                        master_path=master_path,
                        verbatim_span=bullet.text,
                        job_id="writer-agent",
                    )
                )
            else:
                rewritten_bullets.append(bullet)
        new_projects.append(
            Project(
                name=project.name,
                url=project.url,
                bullets=tuple(rewritten_bullets),
            )
        )

    dropped = tuple(
        DropReason(
            item_id=path,
            reason=f"Marked for drop by writer agent: {output.rationale[:80]}",
        )
        for path in output.dropped
    )

    return TailoredResume(
        contact=master.contact,
        summary=output.summary,
        skills=reorder_skills(master.skills, analysis.keywords_to_mirror),
        experiences=tuple(new_experiences),
        projects=tuple(new_projects),
        education=master.education,
        awards=master.awards,
        dropped=dropped,
        rationale=output.rationale,
        grounding=tuple(new_grounding),
        jobs=(),
        run_result=None,
    )


__all__ = ["Writer", "WriterDeps"]
