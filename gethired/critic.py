"""Critic agent.

Runs the deterministic validators (grounding, style, plagiarism, ATS gates)
and emits Job records for traceability.
"""

from __future__ import annotations

from pathlib import Path

from gethired.constants import QUANTIFY
from gethired.models import (
    Job,
Resume,
    Step,
    StepEnv,
    StepKind,
    Tailored,
    job_validate,
    Resume,
)
from gethired.observability import logger
from gethired.validator import (
    AtsReport,
    ats,
    grounding,
    plagiarism,
    style)


class Critic:
    """Validation agent."""

    def __init__(self, debug: bool = False) -> None:
        self.debug = debug
        self.logger = logger("critic")

    def evaluate(
        self,
        tailored: Tailored,
        master: Resume,
        jds: tuple[Job, ...],
        tex_source: str,
        txt_source: str,
        pdf_path: Path | None,
        quantification_threshold: float = QUANTIFY) -> tuple[AtsReport, tuple[Step, ...]]:
        """Run all four validators and emit Step records.

        Returns:
            Tuple of ``(AtsReport, jobs)``.
        """
        jobs: list[Step] = []

        jobs.append(
            job_validate(
                StepKind.VALIDATE_GROUNDING,
                outputs=("grounding_violations"),
                rationale="Validated that every claim traces to master",
                envelope=StepEnv(model="deterministic"))
        )
        grounding_result = grounding(tailored, master)

        jobs.append(
            job_validate(
                StepKind.VALIDATE_STYLE,
                outputs=("style_violations"),
                rationale="Validated banned words, parallelism, quantification",
                envelope=StepEnv(model="deterministic"))
        )
        style_result = style(tailored, quantification_threshold)

        jobs.append(
            job_validate(
                StepKind.VALIDATE_PLAGIARISM,
                outputs=("plagiarism_violations"),
                rationale="Validated no verbatim JD phrase overlap",
                envelope=StepEnv(model="deterministic"))
        )
        plagiarism_result = plagiarism(tailored, jds)

        jobs.append(
            job_validate(
                StepKind.VALIDATE_ATS,
                outputs=("ats_gates"),
                rationale="Ran all 12 ATS gates (9 hard-blocking, 3 advisory)",
                envelope=StepEnv(model="deterministic"))
        )
        ats_report = ats(
            tailored,
            tex_source=tex_source,
            pdf_path=pdf_path,
            txt_source=txt_source,
            jds=jds,
            quantification_threshold=quantification_threshold)

        if grounding_result:
            self.logger.warning("grounding violations detected", count=len(grounding_result))
        if style_result:
            self.logger.warning("style violations detected", count=len(style_result))
        if plagiarism_result:
            self.logger.warning("plagiarism violations detected", count=len(plagiarism_result))
        if not ats_report.all_passed:
            self.logger.warning(
                "ATS gates failed",
                failed=[gate.value for gate in ats_report.failed_gates])
            if ats_report.hard_failed_gates:
                self.logger.error(
                    "ATS hard gates failed",
                    failed=[gate.value for gate in ats_report.hard_failed_gates])
        return ats_report, tuple(jobs)


__all__ = ["Critic"]
