"""Audit: re-run all four validators against a previous run directory.

Loads ``tailored.json`` + ``master.json`` from ``run_dir``, runs grounding,
style, plagiarism, and the 12 ATS gates (9 hard, 3 advisory), and emits
``audit.json`` + ``audit.md`` alongside the run artefacts. Idempotent and
offline (no LLM call).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gethired.critic import Critic
from gethired.exceptions import TailorError
from gethired.models import Resume, Tailored
from gethired.serialize import from_master_dict, from_tailored_dict
from gethired.validator import (
    grounding,
    plagiarism,
    style,
)


@dataclass(frozen=True, slots=True)
class AuditReport:
    """Aggregate audit result for a previous run directory."""

    run_id: str
    grounding_violations: tuple[str, ...]
    style_violations: tuple[str, ...]
    plagiarism_violations: tuple[str, ...]
    ats_passed: bool
    ats_failed_gates: tuple[str, ...]
    ats_advisory_failed_gates: tuple[str, ...]
    ats_skipped_gates: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable dict view of the report."""
        return {
            "run_id": self.run_id,
            "grounding_violations": list(self.grounding_violations),
            "style_violations": list(self.style_violations),
            "plagiarism_violations": list(self.plagiarism_violations),
            "ats_passed": self.ats_passed,
            "ats_failed_gates": list(self.ats_failed_gates),
            "ats_advisory_failed_gates": list(self.ats_advisory_failed_gates),
            "ats_skipped_gates": list(self.ats_skipped_gates),
        }


def audit_paths(run_dir: Path) -> dict[str, Path]:
    """Return the input artefact paths for an audit run."""
    return {
        "tailored": Path(run_dir) / "tailored.json",
        "master": Path(run_dir) / "master.json",
        "tex": Path(run_dir) / "tailored.tex",
        "txt": Path(run_dir) / "tailored.txt",
        "pdf": Path(run_dir) / "tailored.pdf",
    }


def audit_load(tailored_path: Path, master_path: Path) -> tuple[Tailored, Master]:
    """Load both JSON files or raise TailorError with the offending path."""
    if not tailored_path.exists():
        raise TailorError(f"tailored.json missing in {tailored_path.parent}")
    if not master_path.exists():
        raise TailorError(f"master.json missing in {master_path.parent}")
    return __load(tailored_path, master_path)


def read_optional(path: Path) -> str:
    """Return the file contents, or empty string if absent."""
    return path.read_text() if path.exists() else ""


def stringify_violations(violations: tuple[Any, ...]) -> tuple[str, ...]:
    """Convert validator-fault tuples to ``"path: detail"`` strings."""
    return tuple(f"{v.path}: {v.detail}" for v in violations)


def audit(run_dir: Path) -> AuditReport:
    """Re-run all four validators against a previous run directory.

    Args:
        run_dir: Path containing ``tailored.json`` and ``master.json``.

    Returns:
        ``AuditReport`` summarising all four validator outputs.

    Raises:
        TailorError: When ``run_dir`` does not contain the required inputs.
    """
    paths = audit_paths(run_dir)
    tailored, master = _audit_load(paths["tailored"], paths["master"])

    grounding_violations = grounding(tailored, master)
    style_violations = style(tailored)
    plagiarism_violations = plagiarism(tailored, ())

    ats_report, _ = Critic().evaluate(
        tailored=tailored,
        master=master,
        jds=(),
        tex_source=_read_optional(paths["tex"]),
        txt_source=_read_optional(paths["txt"]),
        pdf_path=paths["pdf"] if paths["pdf"].exists() else None,
    )
    run_id = (
        tailored.run_result.run.id if tailored.run_result is not None else run_dir.name
    )
    return AuditReport(
        run_id=run_id,
        grounding_violations=_stringify_violations(grounding_violations),
        style_violations=_stringify_violations(style_violations),
        plagiarism_violations=tuple(f"{v.ngram}" for v in plagiarism_violations),
        ats_passed=not ats_report.hard_failed_gates,
        ats_failed_gates=tuple(g.value for g in ats_report.hard_failed_gates),
        ats_advisory_failed_gates=tuple(g.value for g in ats_report.advisory_failed_gates),
        ats_skipped_gates=tuple(g.value for g in ats_report.skipped_gates),
    )


def audit_json(report: AuditReport) -> str:
    """Render the audit report as pretty-printed JSON."""
    return json.dumps(report.as_dict(), indent=2)


def audit_markdown(report: AuditReport) -> str:
    """Render the audit report as a markdown document."""
    lines: list[str] = []
    lines.append(f"# Audit report for run {report.run_id}")
    lines.append("")
    lines.append(f"- **ATS gates passed**: {'yes' if report.ats_passed else 'no'}")
    if report.ats_failed_gates:
        lines.append(f"- **Hard-failed gates**: {', '.join(report.ats_failed_gates)}")
    if report.ats_advisory_failed_gates:
        lines.append(f"- **Advisory-failed gates**: {', '.join(report.ats_advisory_failed_gates)}")
    if report.ats_skipped_gates:
        lines.append(f"- **Skipped gates**: {', '.join(report.ats_skipped_gates)}")
    lines.append(f"- **Grounding violations**: {len(report.grounding_violations)}")
    lines.append(f"- **Style violations**: {len(report.style_violations)}")
    lines.append(f"- **Plagiarism violations**: {len(report.plagiarism_violations)}")
    lines.append("")
    if report.grounding_violations:
        lines.append("## Grounding")
        for v in report.grounding_violations:
            lines.append(f"- {v}")
        lines.append("")
    if report.style_violations:
        lines.append("## Style")
        for v in report.style_violations:
            lines.append(f"- {v}")
        lines.append("")
    if report.plagiarism_violations:
        lines.append("## Plagiarism")
        for v in report.plagiarism_violations:
            lines.append(f"- {v}")
        lines.append("")
    return "\n".join(lines)


def __load(tailored_path: Path, master_path: Path) -> tuple[Tailored, Master]:
    tailored_raw: Any = json.loads(tailored_path.read_text())
    master_raw: Any = json.loads(master_path.read_text())
    return from_tailored_dict(tailored_raw), from_master_dict(master_raw)


__all__ = [
    "AuditReport",
    "audit",
    "audit_json",
    "audit_markdown",
]
