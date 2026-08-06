"""Renderer: Tailored → tex/txt/match_report.

JSON serialisation lives in ``gethired.serialize`` so that every consumer
of the on-disk snapshot agrees on the schema. This module owns the
human-readable renderings (TeX, plain text, and the match report).
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from jinja2 import Environment, FileSystemLoader, select_autoescape

from gethired import serialize as serialize_module
from gethired.models import (
    Run,
    RunResult,
    Tailored,
)
from gethired.validator import AtsReport

TEMPLATES: Final[Path] = Path(__file__).parent / "templates"

TEX_ESCAPES: Final[dict[str, str]] = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def tex_escape(value: object) -> str:
    """Escape LaTeX special characters in user-supplied text."""
    if value is None:
        return ""
    text = str(value)
    for char, replacement in _TEX_ESCAPES.items():
        text = text.replace(char, replacement)
    return text


def env() -> Environment:
    jinja_env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(disabled_extensions=("tex",), default=False),
        keep_trailing_newline=True,
    )
    jinja_env.filters["tex"] = tex_escape
    return jinja_env


def tex(tailored: Tailored) -> str:
    """Render the tailored resume as TeX source."""
    jinja_env = env()
    template = jinja_env.get_template("resume.tex.j2")
    return template.render(resume=tailored)


def text(tailored: Tailored) -> str:
    """Render the tailored resume as a plain-text ATS version."""
    lines: list[str] = []
    lines.append(tailored.name)
    contact_bits = [tailored.city, tailored.phone, tailored.email]
    if tailored.github:
        contact_bits.append(tailored.github)
    if tailored.linkedin:
        contact_bits.append(tailored.linkedin)
    lines.append(" | ".join(bit for bit in contact_bits if bit))
    lines.append("")
    lines.append("SUMMARY")
    lines.append(tailored.summary)
    lines.append("")
    lines.append("TECHNICAL SKILLS")
    for category, items in tailored.skills.categories.items():
        lines.append(f"{category}: {', '.join(items)}")
    lines.append("")
    lines.append("EXPERIENCE")
    for exp in tailored.experience:
        lines.append(f"{exp.role}, {exp.company} ({exp.start_date} -- {exp.end_date})")
        for bullet in exp.bullets:
            lines.append(f"- {bullet.text}")
        lines.append("")
    if tailored.projects:
        lines.append("SELECTED PROJECTS")
        for project in tailored.projects:
            lines.append(f"{project.name} ({project.url})")
            for bullet in project.bullets:
                lines.append(f"- {bullet.text}")
            lines.append("")
    if tailored.education:
        lines.append("EDUCATION")
        for edu in tailored.education:
            bits = [edu.institution, edu.location, edu.degree, edu.major, edu.graduation]
            if edu.gpa:
                bits.append(f"CGPA: {edu.gpa}")
            lines.append(" - " + ", ".join(bits))
        lines.append("")
    if tailored.awards:
        lines.append("AWARDS")
        for award in tailored.awards:
            bits = [award.title]
            if award.organization:
                bits.append(award.organization)
            if award.date:
                bits.append(award.date)
            lines.append(" - " + ", ".join(bits))
            if award.description:
                lines.append(f"  {award.description}")
    return "\n".join(lines).strip() + "\n"


def run_description(run: Run) -> list[str]:
    """Return the '## Run Description' section as a list of lines."""
    lines = [
        "## Run Description",
        f"- Run.id: `{run.id}`",
        f"- started_at: {run.started_at}",
        f"- resume_hash: `{run.resume_hash}`",
        f"- jd_hash: `{run.jd_hash}`",
        f"- model: `{run.model}`",
    ]
    if run.draft_model:
        lines.append(f"- draft_model: `{run.draft_model}`")
    return lines


def result_description(run_result: RunResult) -> list[str]:
    """Return the '## Result Description' section as a list of lines."""
    return [
        "## Result Description",
        f"- completed_at: {run_result.completed_at}",
        f"- duration_seconds: {run_result.duration_seconds:.2f}",
        f"- total_input_tokens: {run_result.total_input_tokens}",
        f"- total_output_tokens: {run_result.total_output_tokens}",
        f"- retry_attempts: {run_result.retry_attempts}",
        f"- final_outcome: `{run_result.final_outcome.value}`",
    ]


def job_trail(run_result: RunResult) -> list[str]:
    """Return the '## Job Trail' section as a list of lines."""
    lines = [
        "## Job Trail",
        "| id | type | inputs | outputs | rationale | status |",
        "|----|------|--------|---------|-----------|--------|",
    ]
    for job in run_result.jobs:
        lines.append(job.description().markdown())
    return lines


def websearch_audit(run_result: RunResult) -> list[str]:
    """Return the '## Web Search Audit' section, or [] if no searches."""
    searches = run_result.websearch_calls
    if not searches:
        return []
    lines = [
        "## Web Search Audit",
        "| # | query | reason | result snippet |",
        "|---|-------|--------|----------------|",
    ]
    for idx, ws in enumerate(searches, start=1):
        query = ws.metadata.query or ""
        lines.append(f"| {idx} | {query} | {ws.rationale} | (result snippet) |")
    return lines


def ats_results(ats_report: AtsReport) -> list[str]:
    """Return the '## ATS Gate Results' section as a list of lines."""
    return [
        "## ATS Gate Results",
        "| gate | tier | status | detail |",
        "|------|------|--------|--------|",
        *[
            f"| `{result.gate.value}` | {result.gate.tier.value} | "
            f"{result.status.value.upper()} | {result.detail} |"
            for result in ats_report.results
        ],
    ]


def reasoning_trace(run_result: RunResult) -> list[str]:
    """Return the '## Reasoning Trace' section as a list of lines."""
    return [
        "## Reasoning Trace",
        "| # | rationale |",
        "|---|-----------|",
        *[
            f"| {idx} | {job.rationale} |"
            for idx, job in enumerate(run_result.jobs, start=1)
        ],
    ]


def render_summary(tailored: Tailored) -> list[str]:
    """Return the '## Tailored Summary' section, or [] if no summary."""
    if not tailored.summary:
        return []
    return ["## Tailored Summary", tailored.summary]


def report(
    run: Run,
    run_result: RunResult,
    tailored: Tailored,
    ats_report: AtsReport | None = None,
) -> str:
    """Render a markdown match report covering the full run.

    Composes the per-section helpers above into the full report.
    """
    lines: list[str] = [
        f"# gethired run `{run.id}`",
        "",
        *_run_description(run),
        "",
        *_result_description(run_result),
        "",
        *_job_trail(run_result),
        "",
    ]
    websearch = _websearch_audit(run_result)
    if websearch:
        lines.extend(websearch)
        lines.append("")
    if ats_report is not None:
        lines.extend(_ats_results(ats_report))
        lines.append("")
    lines.extend(_reasoning_trace(run_result))
    lines.append("")
    lines.append("## Keyword Coverage")
    lines.append("(See Job Trail above for per-step keyword usage.)")
    lines.append("")
    summary = _summary(tailored)
    if summary:
        lines.extend(summary)
        lines.append("")
    return "\n".join(lines)


def to_json(tailored: Tailored) -> str:
    """Serialise a Tailored resume to JSON."""
    return serialize_module.render_json(tailored)


# Backward-compat alias for the original 'json' name in the renderer module
def json(tailored: Tailored) -> str:
    """Deprecated: use to_json() instead. Kept for backward compat."""
    return to_json(tailored)


__all__ = [
    "json",
    "report",
    "tex",
    "text",
]
