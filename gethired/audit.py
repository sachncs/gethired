"""Audit: re-run all four validators against a previous run directory.

Loads ``tailored.json`` + ``master.json`` from ``run_dir``, runs grounding,
style, plagiarism, and the 11 ATS gates, and emits ``audit.json`` + ``audit.md``
alongside the run artefacts. Idempotent and offline (no LLM call).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gethired.critic import Critic
from gethired.exceptions import ResumeTailoringError
from gethired.models import (
    Award,
    Bullet,
    ContactInformation,
    Education,
    Experience,
    MasterResume,
    Project,
    Run,
    RunResult,
    SkillsByCategory,
    TailoredResume,
)
from gethired.validator import (
    grounding_check,
    plagiarism_check,
    style_check,
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

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable dict view of the report."""
        return {
            "run_id": self.run_id,
            "grounding_violations": list(self.grounding_violations),
            "style_violations": list(self.style_violations),
            "plagiarism_violations": list(self.plagiarism_violations),
            "ats_passed": self.ats_passed,
            "ats_failed_gates": list(self.ats_failed_gates),
        }


def audit_run(run_dir: Path) -> AuditReport:
    """Re-run all four validators against a previous run directory.

    Args:
        run_dir: Path containing ``tailored.json`` and ``master.json``.

    Returns:
        ``AuditReport`` summarising all four validator outputs.

    Raises:
        ResumeTailoringError: When ``run_dir`` does not contain the required inputs.
    """
    tailored_path = Path(run_dir) / "tailored.json"
    master_path = Path(run_dir) / "master.json"
    tex_path = Path(run_dir) / "tailored.tex"
    txt_path = Path(run_dir) / "tailored.txt"
    pdf_path = Path(run_dir) / "tailored.pdf"
    if not tailored_path.exists():
        raise ResumeTailoringError(f"tailored.json missing in {run_dir}")
    if not master_path.exists():
        raise ResumeTailoringError(f"master.json missing in {run_dir}")
    tailored, master = __load_tailored_and_master(tailored_path, master_path)

    grounding = grounding_check(tailored, master)
    style = style_check(tailored)
    plagiarism = plagiarism_check(tailored, ())

    critic = Critic()
    ats_report, _ = critic.evaluate(
        tailored=tailored,
        master=master,
        jds=(),
        tex_source=tex_path.read_text() if tex_path.exists() else "",
        txt_source=txt_path.read_text() if txt_path.exists() else "",
        pdf_path=pdf_path if pdf_path.exists() else None,
    )
    run_id = (
        tailored.run_result.run.id
        if tailored.run_result is not None
        else run_dir.name
    )
    return AuditReport(
        run_id=run_id,
        grounding_violations=tuple(f"{v.path}: {v.detail}" for v in grounding),
        style_violations=tuple(f"{v.path}: {v.detail}" for v in style),
        plagiarism_violations=tuple(f"{v.path}: {v.ngram}" for v in plagiarism),
        ats_passed=ats_report.all_passed,
        ats_failed_gates=tuple(g.value for g in ats_report.failed_gates),
    )


def render_audit_json(report: AuditReport) -> str:
    """Render the audit report as pretty-printed JSON."""
    return json.dumps(report.to_dict(), indent=2)


def render_audit_markdown(report: AuditReport) -> str:
    """Render the audit report as a markdown document."""
    lines: list[str] = []
    lines.append(f"# Audit report for run {report.run_id}")
    lines.append("")
    lines.append(f"- **ATS gates passed**: {'yes' if report.ats_passed else 'no'}")
    if report.ats_failed_gates:
        lines.append(f"- **Failed gates**: {', '.join(report.ats_failed_gates)}")
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


def __load_tailored_and_master(
    tailored_path: Path, master_path: Path
) -> tuple[TailoredResume, MasterResume]:
    tailored_raw: Any = json.loads(tailored_path.read_text())
    master_raw: Any = json.loads(master_path.read_text())
    return __coerce_tailored(tailored_raw), __coerce_master(master_raw)


def __coerce_tailored(raw: Any) -> TailoredResume:
    contact = ContactInformation(**raw["contact"])
    skills = SkillsByCategory(
        categories={k: tuple(v) for k, v in raw["skills"]["categories"].items()}
    )

    def bullet(text: str) -> Bullet:
        return Bullet(text=text)

    def bullets(items: list[dict[str, str]]) -> tuple[Bullet, ...]:
        return tuple(bullet(b["text"]) for b in items)

    experiences = tuple(
        Experience(
            role=e["role"],
            company=e["company"],
            start_date=e["start_date"],
            end_date=e["end_date"],
            bullets=bullets(e["bullets"]),
        )
        for e in raw["experiences"]
    )
    projects = tuple(
        Project(name=p["name"], url=p["url"], bullets=bullets(p["bullets"]))
        for p in raw["projects"]
    )
    education = tuple(Education(**e) for e in raw["education"])
    awards = tuple(Award(**a) for a in raw["awards"])
    run = Run(**raw["run_result"]["run"])
    run_data: dict[str, Any] = {**raw["run_result"], "run": run}
    run_result = RunResult(**run_data)
    return TailoredResume(
        contact=contact,
        summary=raw["summary"],
        skills=skills,
        experiences=experiences,
        projects=projects,
        education=education,
        awards=awards,
        dropped=(),
        rationale=raw.get("rationale", ""),
        grounding=(),
        jobs=(),
        run_result=run_result,
    )


def __coerce_master(raw: Any) -> MasterResume:
    contact = ContactInformation(**raw["contact"])
    skills = SkillsByCategory(
        categories={k: tuple(v) for k, v in raw["skills"]["categories"].items()}
    )

    def bullets(items: list[dict[str, str]]) -> tuple[Bullet, ...]:
        return tuple(Bullet(text=b["text"]) for b in items)

    experiences = tuple(
        Experience(
            role=e["role"],
            company=e["company"],
            start_date=e["start_date"],
            end_date=e["end_date"],
            bullets=bullets(e["bullets"]),
        )
        for e in raw["experiences"]
    )
    projects = tuple(
        Project(name=p["name"], url=p["url"], bullets=bullets(p["bullets"]))
        for p in raw["projects"]
    )
    education = tuple(Education(**e) for e in raw["education"])
    awards = tuple(Award(**a) for a in raw["awards"])
    return MasterResume(
        contact=contact,
        summary=raw["summary"],
        skills=skills,
        experiences=experiences,
        projects=projects,
        education=education,
        awards=awards,
    )


__all__ = [
    "AuditReport",
    "audit_run",
    "render_audit_json",
    "render_audit_markdown",
]
