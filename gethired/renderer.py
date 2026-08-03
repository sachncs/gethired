"""Renderer: Tailored → tex/txt/match_report.

JSON serialisation lives in ``gethired.serialize`` so that every consumer
of the on-disk snapshot agrees on the schema. This module owns the
human-readable renderings (TeX, plain text, and the match report).
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from jinja2 import Environment, FileSystemLoader, select_autoescape

from gethired.models import (
    Run,
    RunResult,
    Tailored,
)
from gethired import serialize
from gethired.validator import AtsReport

TEMPLATES: Final[Path] = Path(__file__).parent / "templates"


def env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(disabled_extensions=("tex",), default=False),
        keep_trailing_newline=True,
    )


def tex(tailored: Tailored) -> str:
    """Render the tailored resume as TeX source."""
    jinja_env = env()
    template = jinja_env.get_template("resume.tex.j2")
    return template.render(resume=tailored)


def text(tailored: Tailored) -> str:
    """Render the tailored resume as a plain-text ATS version."""
    lines: list[str] = []
    lines.append(tailored.contact.name)
    contact_bits = [tailored.contact.city, tailored.contact.phone, tailored.contact.email]
    if tailored.contact.github_url:
        contact_bits.append(tailored.contact.github_url)
    if tailored.contact.linkedin_url:
        contact_bits.append(tailored.contact.linkedin_url)
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
    for exp in tailored.experiences:
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


def report(
    run: Run,
    run_result: RunResult,
    tailored: Tailored,
    ats_report: AtsReport | None = None,
) -> str:
    """Render a markdown match report covering the full run."""
    lines: list[str] = []
    lines.append(f"# gethired run `{run.id}`")
    lines.append("")
    lines.append("## Run Description")
    lines.append(f"- Run.id: `{run.id}`")
    lines.append(f"- started_at: {run.started_at}")
    lines.append(f"- master_hash: `{run.master_hash}`")
    lines.append(f"- jd_urls_hash: `{run.jd_urls_hash}`")
    lines.append(f"- model: `{run.model}`")
    if run.draft_model:
        lines.append(f"- draft_model: `{run.draft_model}`")
    lines.append("")
    lines.append("## Result Description")
    lines.append(f"- completed_at: {run_result.completed_at}")
    lines.append(f"- duration_seconds: {run_result.duration_seconds:.2f}")
    lines.append(f"- total_input_tokens: {run_result.total_input_tokens}")
    lines.append(f"- total_output_tokens: {run_result.total_output_tokens}")
    lines.append(f"- retry_attempts: {run_result.retry_attempts}")
    lines.append(f"- final_outcome: `{run_result.final_outcome.value}`")
    lines.append("")
    lines.append("## Job Trail")
    lines.append("| id | type | inputs | outputs | rationale | status |")
    lines.append("|----|------|--------|---------|-----------|--------|")
    for job in run_result.jobs:
        desc = job.description()
        lines.append(desc.markdown())
    lines.append("")
    searches = run_result.websearch_calls
    if searches:
        lines.append("## Web Search Audit")
        lines.append("| # | query | reason | result snippet |")
        lines.append("|---|-------|--------|----------------|")
        for idx, ws in enumerate(searches, start=1):
            query = ws.metadata.query or ""
            lines.append(f"| {idx} | {query} | {ws.rationale} | (result snippet) |")
        lines.append("")
    if ats_report is not None:
        lines.append("## ATS Gate Results")
        lines.append("| gate | tier | status | detail |")
        lines.append("|------|------|--------|--------|")
        for result in ats_report.results:
            lines.append(
                f"| `{result.gate.value}` | {result.gate.tier.value} | "
                f"{result.status.value.upper()} | {result.detail} |"
            )
        lines.append("")
    lines.append("## Reasoning Trace")
    lines.append("| # | rationale |")
    lines.append("|---|-----------|")
    for idx, job in enumerate(run_result.jobs, start=1):
        lines.append(f"| {idx} | {job.rationale} |")
    lines.append("")
    lines.append("## Keyword Coverage")
    lines.append("(See Job Trail above for per-step keyword usage.)")
    lines.append("")
    if tailored.summary:
        lines.append("## Tailored Summary")
        lines.append(tailored.summary)
        lines.append("")
    return "\n".join(lines)


def json(tailored: Tailored) -> str:
    """Serialise a Tailored resume to JSON. Backward-compat alias for the serialize module."""
    return serialize.json(tailored)


__all__ = [
    "json",
    "report",
    "tex",
    "text",
]
