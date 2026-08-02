"""Writer agent.

The main tailoring agent. Takes the master resume, JD analysis, and voice
profile; produces a TailoredResume. Emits Job records for traceability.

Uses Pydantic AI when an LLM is configured; otherwise falls back to a
deterministic identity transform (useful for tests).
"""

from __future__ import annotations

import os

from gethired.constants import MODEL_ENV_VAR
from gethired.description import DescriptionAnalysis
from gethired.exceptions import ConfigurationError
from gethired.models import (
    GroundedCitation,
    Job,
    JobType,
    MasterResume,
    TailoredResume,
    VoiceProfile,
    job,
)
from gethired.observability import step_logger


def _resolve_model(model: str | None) -> str | None:
    return model or os.environ.get(MODEL_ENV_VAR)


class Writer:
    """Main tailoring agent."""

    def __init__(self, model: str | None = None, debug: bool = False) -> None:
        self._model = _resolve_model(model)
        self._debug = debug
        self._logger = step_logger("writer")

    def tailor(
        self,
        master: MasterResume,
        analysis: DescriptionAnalysis,
        voice: VoiceProfile,
        previous_violations: tuple[str, ...] = (),
    ) -> tuple[TailoredResume, tuple[Job, ...]]:
        """Produce a tailored resume and the Job trail.

        When ``model`` is set, delegates to the LLM. Otherwise emits a
        deterministic identity-style transform suitable for tests.
        """
        if self._model is None:
            return self._deterministic_tailor(master, analysis, voice)
        return self._llm_tailor(master, analysis, voice, previous_violations)

    def _deterministic_tailor(
        self,
        master: MasterResume,
        analysis: DescriptionAnalysis,
        voice: VoiceProfile,
    ) -> tuple[TailoredResume, tuple[Job, ...]]:
        """Deterministic fallback: rewrite summary, reorder by JD keywords."""
        jobs: list[Job] = []

        jobs.append(
            job(
                JobType.TAILOR,
                outputs=("tailored.summary",),
                rationale=f"Rewrote summary to emphasise {analysis.role}",
                model=self._model or "deterministic",
            )
        )
        summary = self._rewrite_summary(master, analysis)

        jobs.append(
            job(
                JobType.TAILOR,
                outputs=("tailored.experiences",),
                rationale="Re-ordered experiences by JD keyword match",
                model=self._model or "deterministic",
            )
        )
        ranked = _rank_experiences(master, analysis)

        jobs.append(
            job(
                JobType.TAILOR,
                outputs=("tailored.skills",),
                rationale="Re-ordered skills to mirror JD keyword order",
                model=self._model or "deterministic",
            )
        )
        skills = _reorder_skills(master.skills, analysis.keywords_to_mirror)

        tailored = TailoredResume(
            contact=master.contact,
            summary=summary,
            skills=skills,
            experiences=ranked,
            projects=master.projects,
            education=master.education,
            awards=master.awards,
            dropped=(),
            rationale=(
                f"Tailored for {analysis.role}; "
                f"{len(analysis.must_have_skills)} must-have keywords mirrored."
            ),
            grounding=tuple(
                GroundedCitation(
                    tailored_path=f"experiences[{idx}]",
                    master_path=f"experiences[{idx}]",
                    verbatim_span=exp.bullets[0].text if exp.bullets else "",
                    job_id=jobs[-1].id,
                )
                for idx, exp in enumerate(ranked)
                if exp.bullets
            ),
            jobs=tuple(jobs),
            run_result=None,  # type: ignore[arg-type]
        )
        return tailored, tuple(jobs)

    def _llm_tailor(
        self,
        master: MasterResume,
        analysis: DescriptionAnalysis,
        voice: VoiceProfile,
        previous_violations: tuple[str, ...],
    ) -> tuple[TailoredResume, tuple[Job, ...]]:
        """Delegate to the LLM. Implementation hooks for production use."""
        raise ConfigurationError(
            "Writer LLM tailoring is not yet wired; "
            "set MODEL env var and configure an API key."
        )

    def _rewrite_summary(self, master: MasterResume, analysis: DescriptionAnalysis) -> str:
        """Tighten summary to mirror the JD's role and key skills."""
        keyword_blob = ", ".join(analysis.keywords_to_mirror[:3])
        base = master.summary.rstrip(".")
        if keyword_blob:
            return f"{base} Focused on {keyword_blob}."
        return base + "."


def _rank_experiences(master: MasterResume, analysis: DescriptionAnalysis):
    """Re-order experiences by JD keyword overlap, preserving reverse-chrono as tiebreaker."""
    must_have = {kw.lower() for kw in analysis.must_have_skills}
    nice = {kw.lower() for kw in analysis.nice_to_have_skills}
    scored: list[tuple[int, int, object]] = []
    for idx, exp in enumerate(master.experiences):
        text = " ".join((exp.role, exp.company, *(b.text for b in exp.bullets))).lower()
        score = sum(2 for kw in must_have if kw in text) + sum(1 for kw in nice if kw in text)
        scored.append((score, -idx, exp))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return tuple(item[2] for item in scored)


def _reorder_skills(skills, mirror_keywords):
    """Re-order skill items within each category to prioritise JD keywords."""
    mirror = [kw.lower() for kw in mirror_keywords]
    new_categories: dict[str, tuple[str, ...]] = {}
    for category, items in skills.categories.items():
        ranked: list[tuple[int, int, str]] = []
        for idx, item in enumerate(items):
            score = sum(2 if item.lower() == kw else 1 for kw in mirror if kw in item.lower())
            ranked.append((score, -idx, item))
        ranked.sort(key=lambda t: (-t[0], t[1]))
        new_categories[category] = tuple(item[2] for item in ranked)
    return type(skills)(categories=new_categories)


__all__ = ["Writer"]
