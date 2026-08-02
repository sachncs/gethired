"""Critic agent.

Runs the deterministic validators (grounding, style, plagiarism, ATS gates)
and emits Job records for traceability.
"""

from __future__ import annotations

from pathlib import Path

from gethired.constants import BULLET_QUANTIFICATION_THRESHOLD
from gethired.models import (
    Job,
    JobDescription,
    JobType,
    MasterResume,
    TailoredResume,
    job,
)
from gethired.observability import step_logger
from gethired.validator import (
    AtsGateReport,
    ats_check,
    grounding_check,
    plagiarism_check,
    style_check,
)


class Critic:
    """Validation agent."""

    def __init__(self, debug: bool = False) -> None:
        self._debug = debug
        self._logger = step_logger("critic")

    def evaluate(
        self,
        tailored: TailoredResume,
        master: MasterResume,
        jds: tuple[JobDescription, ...],
        tex_source: str,
        txt_source: str,
        pdf_path: Path | None,
        quantification_threshold: float = BULLET_QUANTIFICATION_THRESHOLD,
    ) -> tuple[AtsGateReport, tuple[Job, ...]]:
        """Run all four validators and emit Job records.

        Returns:
            Tuple of ``(AtsGateReport, jobs)``.
        """
        jobs: list[Job] = []

        jobs.append(
            job(
                JobType.VALIDATE_GROUNDING,
                outputs=("grounding_violations",),
                rationale="Validated that every claim traces to master",
                model="deterministic",
            )
        )
        grounding = grounding_check(tailored, master, quantification_threshold)

        jobs.append(
            job(
                JobType.VALIDATE_STYLE,
                outputs=("style_violations",),
                rationale="Validated banned words, parallelism, quantification",
                model="deterministic",
            )
        )
        style = style_check(tailored, quantification_threshold)

        jobs.append(
            job(
                JobType.VALIDATE_PLAGIARISM,
                outputs=("plagiarism_violations",),
                rationale="Validated no verbatim JD phrase overlap",
                model="deterministic",
            )
        )
        plagiarism = plagiarism_check(tailored, jds)

        jobs.append(
            job(
                JobType.VALIDATE_ATS,
                outputs=("ats_gates",),
                rationale="Ran all 11 ATS gates (compile, extract, headings, layout, etc.)",
                model="deterministic",
            )
        )
        ats_report = ats_check(
            tailored,
            tex_source=tex_source,
            pdf_path=pdf_path,
            txt_source=txt_source,
            jds=jds,
            quantification_threshold=quantification_threshold,
        )

        if grounding:
            self._logger.warning("grounding violations detected", count=len(grounding))
        if style:
            self._logger.warning("style violations detected", count=len(style))
        if plagiarism:
            self._logger.warning("plagiarism violations detected", count=len(plagiarism))
        if not ats_report.all_passed:
            self._logger.warning(
                "ATS gates failed",
                failed=[gate.value for gate in ats_report.failed_gates],
            )
        return ats_report, tuple(jobs)


__all__ = ["Critic"]
