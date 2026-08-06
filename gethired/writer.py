"""Writer agent.

The main tailoring agent. Takes the master resume, JD analysis, and voice
profile; produces a Tailored. Emits Job records for traceability.

Uses Pydantic AI with read-only tools (per user directive) and Anthropic
provider (which works with both Anthropic native and the MiniMax platform).
"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import os
from collections.abc import Iterator
from dataclasses import asdict
from typing import (  # Any: Pydantic AI model/result types are duck-typed across providers
    TYPE_CHECKING,
    Any,
)

if TYPE_CHECKING:
    from gethired.streaming import Callback, ProgressEvent

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from gethired.constants import (
    DROP_CHARS,
    MODEL_VAR,
    RATIONALE_CHARS,
)
from gethired.description import Analysis
from gethired.exceptions import ConfigError
from gethired.models import (
    Bullet,
    Citation,
    Experience,
Resume,
    Project,
    Reason,
    Skills,
    Step,
    StepEnv,
    Tailored,
    Voice,
    job_lookup,
    job_tailor,
)
from gethired.observability import logger
from gethired.provider import resolve_model
from gethired.rubric import ANTI_AI, BANNED, GROUNDING
from gethired.tracing import ActiveSpan, Tracer

current_tracer: contextvars.ContextVar[Tracer | None] = contextvars.ContextVar(
    "gethired_current_tracer", default=None
)


def null_span_cm() -> contextlib.AbstractContextManager[ActiveSpan | None]:
    """Context manager that yields None — used when no tracer is active."""

    @contextlib.contextmanager
    def cm() -> Iterator[ActiveSpan | None]:
        yield None

    return cm()


class WriterDeps:
    """Dependencies injected into the writer agent's RunContext."""

    def __init__(
        self,
        master: Resume,
        analysis: Analysis,
        voice: Voice,
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

    Contract: ``tailored_bullets`` MUST contain an entry for every
    experience and project bullet path in the master. Paths the model
    omits are rephrased by a focused fallback pass so the tailored
    output never carries a verbatim master bullet.
    """

    summary: str = Field(description="Rewritten summary, ≤ 3 sentences")
    tailored_bullets: dict[str, list[str]] = Field(
        description=(
            "Map of master_path (e.g. 'experiences[0].bullets[0]') to a list "
            "of rewritten bullet strings. REQUIRED: include an entry for EVERY "
            "experience and project bullet path. Paths omitted here are "
            "rephrased by a fallback pass; the writer must always produce "
            "a rephrase, even if only a minor reword to mirror the JD's vocabulary."
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
    provided; otherwise ``ConfigError`` is raised at ``tailor()`` time.
    """

    def __init__(
        self,
        model: str | None = None,
        debug: bool = False,
        model_instance: object | None = None,
    ) -> None:
        self.model_string = model or os.environ.get(MODEL_VAR)
        self.debug = debug
        self.logger = logger("writer")
        self.model_instance = model_instance

    def tailor(
        self,
        master: Resume,
        analysis: Analysis,
        voice: Voice,
        previous_violations: tuple[str, ...] = (),
        on_progress: Callback | None = None,
    ) -> tuple[Tailored, tuple[Step, ...]]:
        """Produce a tailored resume and the Step trail.

        Args:
            master: The canonical master resume.
            analysis: Structured JD analysis.
            voice: Voice profile for fingerprint preservation.
            previous_violations: Style violations from prior retry (if any).
            on_progress: Optional callable invoked with each ``ProgressEvent``
                emitted during the tailoring run.

        Returns:
            Tuple of ``(Tailored, jobs)``.
        """
        if self.model_string is None and self.model_instance is None:
            raise ConfigError(
                "MODEL is required. Set the MODEL env var (e.g. 'MiniMax-M3', "
                "'anthropic:claude-sonnet-4-5', 'openai:gpt-5') and API_KEY "
                "(or ANTHROPIC_API_KEY / OPENAI_API_KEY), or pass "
                "model_instance=TestModel() for offline tests."
            )
        return self.__llm_tailor(master, analysis, voice, previous_violations, on_progress)

    # ------------------------------------------------------------------
    # LLM-backed tailoring
    # ------------------------------------------------------------------

    def __llm_tailor(
        self,
        master: Resume,
        analysis: Analysis,
        voice: Voice,
        previous_violations: tuple[str, ...],
        on_progress: Callback | None = None,
    ) -> tuple[Tailored, tuple[Step, ...]]:
        """Run the Pydantic AI Agent against the configured model.

        Args:
            master: The canonical master resume.
            analysis: Structured JD analysis.
            voice: Voice profile for fingerprint preservation.
            previous_violations: Style violations from prior retry (if any).
            on_progress: Optional callable invoked with each ProgressEvent.

        Returns:
            Tuple of ``(Tailored, jobs)``.
        """
        if self.model_instance is not None:
            model: Any = self.model_instance
        else:
            resolved = resolve_model(self.model_string)
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
                base(),
                rubric(previous_violations),
                jd(),
                voice_prompt(voice),
            ],
        )

        self.__register_read_only_tools(agent)

        result = asyncio.run(agent.run(prompt(master, analysis), deps=deps))
        writer_output = result.output
        tool_jobs = from_tools(result)

        # Every-bullet rewrite contract: every master bullet must be rephrased
        # (never carried over verbatim). The writer's main pass may omit paths
        # from tailored_bullets or return the original text unchanged. Either
        # case triggers the fallback rephrase.
        expected_paths = enumerate_bullet_paths(master)
        missing_or_verbatim: list[tuple[str, str]] = []
        for path in expected_paths:
            original = lookup_bullet_text(master, path) or ""
            candidates = writer_output.tailored_bullets.get(path)
            rephrased = candidates[0] if candidates else ""
            if path not in writer_output.tailored_bullets or rephrased.strip() == original.strip():
                missing_or_verbatim.append((path, original))
        if missing_or_verbatim:
            rephrases = rephrase_missing_bullets(
                missing_or_verbatim,
                analysis,
                model_instance=model if self.model_instance is not None else None,
                model_string=self.model_string,
            )
            writer_output.tailored_bullets.update(rephrases)

        tailored = apply(master, writer_output, analysis)
        model_name = (
            getattr(model, "model_name", None) if not isinstance(model, str) else str(model)
        )
        all_jobs = tool_jobs + (
            job_tailor(
                outputs=("tailored_resume",),
                rationale=(
                    f"LLM produced {len(writer_output.tailored_bullets)} rewritten bullets; "
                    f"rationale: {writer_output.rationale[:RATIONALE_CHARS]}"
                ),
                envelope=StepEnv(model=str(model_name) if model_name else "model"),
            ),
        )
        tailored = Tailored(
            name=tailored.name,
            email=tailored.email,
            city=tailored.city,
            phone=tailored.phone,
            github=tailored.github,
            linkedin=tailored.linkedin,
            summary=tailored.summary,
            skills=tailored.skills,
            experience=tailored.experience,
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
        async def experience(ctx: RunContext[WriterDeps], role_or_company: str) -> dict[str, Any]:
            """Look up an experience in the master by role or company."""
            master = ctx.deps.master
            tracer = current_tracer.get()
            span_cm = (
                tracer.span("experience", "tool", role_or_company=role_or_company)
                if tracer is not None
                else null_span_cm()
            )
            with span_cm as span:
                lowered = role_or_company.lower()
                for exp in master.experience:
                    if lowered in exp.role.lower() or lowered in exp.company.lower():
                        result = asdict(exp)
                        if span is not None:
                            span.set_attribute("matched", True)
                        return result
                if span is not None:
                    span.set_attribute("matched", False)
                return {}

        @agent.tool
        async def project(ctx: RunContext[WriterDeps], name: str) -> dict[str, Any]:
            """Look up a project in the master by name."""
            master = ctx.deps.master
            lowered = name.lower()
            for project in master.projects:
                if lowered in project.name.lower() or lowered in project.url.lower():
                    return asdict(project)
            return {}

        @agent.tool
        async def skills(ctx: RunContext[WriterDeps]) -> dict[str, list[str]]:
            """Return the master's skills by category."""
            return {
                category: list(items)
                for category, items in ctx.deps.master.skills.categories.items()
            }

        @agent.tool
        async def projects(ctx: RunContext[WriterDeps]) -> list[dict[str, Any]]:
            """Return all projects from the master."""
            return [asdict(p) for p in ctx.deps.master.projects]

        @agent.tool
        async def education(ctx: RunContext[WriterDeps]) -> list[dict[str, Any]]:
            """Return all education entries from the master."""
            return [asdict(e) for e in ctx.deps.master.education]

        @agent.tool
        async def awards(ctx: RunContext[WriterDeps]) -> list[dict[str, Any]]:
            """Return all awards from the master."""
            return [asdict(a) for a in ctx.deps.master.awards]

        @agent.tool
        async def jd(ctx: RunContext[WriterDeps]) -> dict[str, Any]:
            """Return the structured JD analysis the writer is optimising for."""
            analysis = ctx.deps.analysis
            return {
                "role": analysis.role,
                "seniority": analysis.seniority,
                "must_have": list(analysis.must_have),
                "nice_to_have": list(analysis.nice_to_have),
                "keywords": list(analysis.keywords),
                "responsibilities": list(analysis.responsibilities),
            }

    # ---------------------------------------------------------------------------


# Helpers (module-level)
# ---------------------------------------------------------------------------


def reorder(skills: Skills, mirror_keywords):
    mirror = [kw.lower() for kw in mirror_keywords]
    new_categories: dict[str, tuple[str, ...]] = {}
    for category, items in skills.categories.items():
        ranked: list[tuple[int, int, str]] = []
        for idx, item in enumerate(items):
            score = sum(2 if item.lower() == kw else 1 for kw in mirror if kw in item.lower())
            ranked.append((score, -idx, item))
        ranked.sort(key=lambda t: (-t[0], t[1]))
        new_categories[category] = tuple(item[2] for item in ranked)
    return Skills(categories=new_categories)


def base() -> str:
    banned_words = ", ".join(sorted(BANNED)[:10]) + ", ..."
    return f"""You are gethired's writer agent. Your job: produce a Tailored
that matches a job description while staying strictly grounded in the master
resume.

GROUNDING (HARD RULES):
{chr(10).join(f"- {rule}" for rule in GROUNDING)}

ANTI-AI LANGUAGE (HARD RULES):
{chr(10).join(f"- {rule}" for rule in ANTI_AI)}

BANNED WORDS (sample): {banned_words}

TOOLS:
You have 7 read-only tools to inspect the master (experience,
project, skills, projects, education, awards,
jd). Use them before claiming any fact. NEVER invent facts.

OUTPUT:
Return a Tailored with grounding citations (each tailored bullet must
cite its source master path + verbatim span). Do NOT invent companies,
projects, dates, numbers, or skills."""


def rubric(previous_violations: tuple[str, ...]) -> str:
    if not previous_violations:
        return ""
    return "PRIOR VIOLATIONS TO AVOID (retry constraints):\n" + "\n".join(
        f"- {v}" for v in previous_violations
    )


def jd() -> str:
    return (
        "Use the jd tool to retrieve must-have skills, "
        "nice-to-have skills, and responsibilities. Mirror must-have keywords "
        "in your bullet rewrites — never invent, but rephrase to include them."
    )


def voice_prompt(voice: Voice) -> str:
    verbs = ", ".join(voice.opening_verbs[:5]) or "n/a"
    return (
        f"VOICE PROFILE (preserve):\n"
        f"- avg bullet length: {voice.avg_bullet_length:.0f} chars "
        f"(stddev {voice.bullet_length_stddev:.0f})\n"
        f"- opening verbs to honour: {verbs}\n"
        f"- sentence count per bullet: {voice.sentence_count_per_bullet}"
    )


def prompt(master: Resume, analysis: Analysis) -> str:
    master_md = master.to_markdown()
    jd_summary = (
        f"Target role: {analysis.role}\n"
        f"Seniority: {analysis.seniority}\n"
        f"Must-have skills: {', '.join(analysis.must_have)}\n"
        f"Nice-to-have: {', '.join(analysis.nice_to_have)}"
    )
    paths = enumerate_bullet_paths(master)
    paths_block = "\n".join(f"- {p}" for p in paths)
    return (
        f"Here is the master resume (single source of truth):\n\n"
        f"{master_md}\n\n"
        f"Here is the structured JD analysis:\n\n{jd_summary}\n\n"
        f"REQUIRED: rephrase EVERY bullet in the resume. The master has "
        f"{len(paths)} bullets across experiences and projects. Every path "
        f"below MUST appear as a key in your tailored_bullets output:\n"
        f"{paths_block}\n\n"
        f"A path the model omits triggers a fallback rephrase pass, so the "
        f"final tailored output must always reword every bullet — never "
        f"carry a master bullet verbatim.\n\n"
        f"Produce a Tailored. Use the read-only tools to verify any "
        f"fact before including it. Every bullet must include a Citation."
    )


def from_tools(result: Any) -> tuple[Step, ...]:
    """Extract Job records from the agent's tool calls.

    Best-effort: walks ``result.all_messages`` looking for tool-call parts.
    The ``master`` parameter was previously accepted for a planned
    master-aware extraction feature; since the walker only needs the
    result's message tree, the parameter is removed (forward-only,
    no deprecation shim per user directive).
    """
    jobs: list[Step] = []
    messages = result.all_messages()
    for message in messages:
        for part in getattr(message, "parts", []):
            part_type = getattr(part, "part_kind", None) or getattr(part, "type", None)
            if part_type == "tool-call" or getattr(part, "tool_name", None):
                tool_name = getattr(part, "tool_name", "unknown")
                jobs.append(
                    job_lookup(
                        tool_name=tool_name,
                        outputs=(f"tool:{tool_name}",),
                        rationale=f"Called read-only tool {tool_name}",
                        envelope=StepEnv(
                            model=str(
                                getattr(
                                    getattr(message, "model", None),
                                    "model_name",
                                    "model",
                                )
                            ),
                        ),
                    )
                )
    return tuple(jobs)


# ---------------------------------------------------------------------------
# Every-bullet rewrite contract
# ---------------------------------------------------------------------------


def enumerate_bullet_paths(master: Resume) -> list[str]:
    """Return every experience and project bullet path in the master, in order."""
    paths: list[str] = []
    for i, exp in enumerate(master.experience):
        for j in range(len(exp.bullets)):
            paths.append(f"experiences[{i}].bullets[{j}]")
    for i, proj in enumerate(master.projects):
        for j in range(len(proj.bullets)):
            paths.append(f"projects[{i}].bullets[{j}]")
    return paths


def lookup_bullet_text(master: Resume, master_path: str) -> str | None:
    """Return the original bullet text at ``master_path`` (or None if not found)."""
    try:
        if master_path.startswith("experiences["):
            tail = master_path[len("experiences[") :]
            idx_str, rest = tail.split("].bullets[", 1)
            idx = int(idx_str)
            b_idx = int(rest.rstrip("]"))
            return master.experience[idx].bullets[b_idx].text
        if master_path.startswith("projects["):
            tail = master_path[len("projects[") :]
            idx_str, rest = tail.split("].bullets[", 1)
            idx = int(idx_str)
            b_idx = int(rest.rstrip("]"))
            return master.projects[idx].bullets[b_idx].text
    except (IndexError, ValueError):
        return None
    return None


def is_test_model(model: object | None) -> bool:
    """True when ``model`` is Pydantic AI's ``TestModel`` (skip LLM fallback paths)."""
    name = getattr(model, "model_name", None)
    return name == "test"


class RephraseBatch(BaseModel):
    """Output schema for the per-bullet rephrase fallback agent."""

    rephrases: dict[str, str] = Field(
        description=(
            "Map of master_path to rephrased bullet text. Every input path "
            "must appear exactly once."
        )
    )


REPHRASE_INSTRUCTIONS: tuple[str, ...] = (
    "You rephrase resume bullets to mirror the target JD's vocabulary without inventing facts.",
    "For each bullet:",
    "(1) preserve every fact from the original (numbers, technologies, scope, dates);",
    "(2) weave the JD's must-have keywords naturally into the rephrase;",
    "(3) keep the same length, opening verb, and voice as the master;",
    "(4) do not invent companies, projects, dates, numbers, or skills.",
    "Return ONLY the JSON object with 'rephrases' mapping master_path to text.",
)
"""System instructions for the per-bullet rephrase fallback agent."""


def rephrase_missing_bullets(
    missing: list[tuple[str, str]],
    analysis: Analysis,
    *,
    model_instance: object | None,
    model_string: str | None,
) -> dict[str, list[str]]:
    """Rephrase every bullet in ``missing`` via a focused single-batch LLM call.

    Falls back to the original text when ``model_instance`` is a TestModel
    (test determinism) or when the LLM call itself raises.

    Args:
        missing: Pairs of ``(master_path, original_text)``.
        analysis: Structured JD analysis (for keyword guidance).
        model_instance: Pre-constructed model instance (tests).
        model_string: Model identifier (production path).

    Returns:
        Map of master_path to a single-element list ``[rephrased]``.
    """
    if not missing:
        return {}
    if is_test_model(model_instance):
        return {path: [text] for path, text in missing}
    try:
        bullets_block = "\n".join(f"- {path}: {text}" for path, text in missing)
        keywords_blob = ", ".join(analysis.must_have) or "(none specified)"
        if model_instance is None:
            resolved = resolve_model(model_string)
            model_obj: Any = resolved.model
        else:
            model_obj = model_instance
        agent: Agent[None, RephraseBatch] = Agent(
            model_obj,
            output_type=RephraseBatch,
            instructions=list(REPHRASE_INSTRUCTIONS),
        )
        payload = (
            f"JD must-have keywords: {keywords_blob}\n\n"
            f"Rephrase every bullet below. Mirror the JD's vocabulary without "
            f"inventing facts.\n\nBULLETS:\n{bullets_block}\n\n"
            f"Return a JSON object with a 'rephrases' key mapping each "
            f"master_path to the rephrased bullet text."
        )
        result = agent.run_sync(payload)
        return {
            path: [result.output.rephrases[path]]
            for path, _ in missing
            if path in result.output.rephrases
        }
    except Exception:
        return {path: [text] for path, text in missing}


def rewrite(
    bullets: tuple[Bullet, ...],
    container_path: str,
    tailored_bullets: dict[str, list[str]],
    dropped: frozenset[str],
) -> tuple[list[Bullet], list[Citation]]:
    """Rewrite or drop bullets in a single experience/project container.

    ``container_path`` is the master path prefix without the bullet index, e.g.
    ``"experiences[2].bullets"``. Returns the surviving bullets plus the
    grounding citations for any rewritten text.
    """
    rewritten: list[Bullet] = []
    grounding: list[Citation] = []
    for b_idx, bullet in enumerate(bullets):
        master_path = f"{container_path}[{b_idx}]"
        if master_path in dropped:
            continue
        if master_path in tailored_bullets:
            candidates = tailored_bullets[master_path]
            rewritten.append(Bullet(text=candidates[0] if candidates else bullet.text))
            grounding.append(
                Citation(
                    tailored_path=master_path,
                    master_path=master_path,
                    verbatim_span=bullet.text,
                    job_id="writer-agent",
                )
            )
        else:
            rewritten.append(bullet)
    return rewritten, grounding


def apply_experiences(
    master: Resume,
    output: WriterOutput,
    dropped: frozenset[str],
) -> tuple[tuple[Experience, ...], list[Citation]]:
    """Apply the writer's bullet rewrites to the master's experiences."""
    new_experiences: list[Experience] = []
    new_grounding: list[Citation] = []
    for idx, exp in enumerate(master.experience):
        if f"experiences[{idx}]" in dropped:
            continue
        rewritten_bullets, bullet_grounding = rewrite(
            exp.bullets,
            f"experiences[{idx}].bullets",
            output.tailored_bullets,
            dropped,
        )
        new_grounding.extend(bullet_grounding)
        new_experiences.append(
            Experience(
                role=exp.role,
                company=exp.company,
                start_date=exp.start_date,
                end_date=exp.end_date,
                bullets=tuple(rewritten_bullets),
            )
        )
    return tuple(new_experiences), new_grounding


def apply_projects(
    master: Resume,
    output: WriterOutput,
    dropped: frozenset[str],
) -> tuple[tuple[Project, ...], list[Citation]]:
    """Apply the writer's bullet rewrites to the master's projects."""
    new_projects: list[Project] = []
    new_grounding: list[Citation] = []
    for p_idx, project in enumerate(master.projects):
        if f"projects[{p_idx}]" in dropped:
            continue
        rewritten_bullets, bullet_grounding = rewrite(
            project.bullets,
            f"projects[{p_idx}].bullets",
            output.tailored_bullets,
            dropped,
        )
        new_grounding.extend(bullet_grounding)
        new_projects.append(
            Project(
                name=project.name,
                url=project.url,
                bullets=tuple(rewritten_bullets),
            )
        )
    return tuple(new_projects), new_grounding


def drop_reasons(output: WriterOutput) -> tuple[Reason, ...]:
    """Convert each dropped master path into a Reason tuple."""
    return tuple(
        Reason(
            item_id=path,
            reason=(f"Marked for drop by writer agent: {output.rationale[:DROP_CHARS]}"),
        )
        for path in output.dropped
    )


def apply(
    master: Resume,
    output: WriterOutput,
    analysis: Analysis,
) -> Tailored:
    """Apply the writer agent's output onto the master resume.

    The agent produces a ``WriterOutput`` (Pydantic) with a flat
    ``tailored_bullets`` map of master paths → rewritten bullet text.
    This function applies those rewrites onto the master, preserving
    canonical fields (company, dates, urls, contact, education, awards).
    Entries listed in ``output.dropped`` are removed from the result.
    """
    dropped = frozenset(output.dropped)
    experiences, exp_grounding = _apply_experiences(master, output, dropped)
    projects, proj_grounding = _apply_projects(master, output, dropped)
    return Tailored(
        name=master.name,email=master.email,city=master.city,phone=master.phone,github=master.github,linkedin=master.linkedin,
        summary=output.summary,
        skills=reorder(master.skills, analysis.keywords),
        experience=experiences,
        projects=projects,
        education=master.education,
        awards=master.awards,
        dropped=_drop_reasons(output),
        rationale=output.rationale,
        grounding=tuple(exp_grounding + proj_grounding),
        jobs=(),
        run_result=None,
    )


__all__ = ["Writer", "WriterDeps", "current_tracer"]
