"""JSON ↔ domain-model coercion.

Single source of truth for converting between the on-disk JSON snapshot and
the canonical ``Resume`` / ``Tailored`` dataclasses. The same
mapping previously lived in three places (``tailor.load_master``,
``audit.__coerce_tailored``, ``cli.validate``); this module consolidates
them so every reader agrees on the schema.

The on-disk schema is whatever ``renderer.render_json`` writes — i.e. the
default ``dataclasses.asdict`` shape. Both ``Resume`` and
``Tailored`` use the same field layout for the common sections
(contact / skills / experiences / projects / education / awards);
``Tailored`` adds ``dropped``, ``rationale``, ``grounding``, ``jobs``,
and ``run_result``.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from gethired.models import (
    Award,
    Bullet,
    Citation,
    Contact,
    Education,
    Experience,
Resume,
    Outcome,
    Project,
    Reason,
    Run,
    RunResult,
    Skills,
    Step,
    StepKind,
    StepMeta,
    StepStatus,
    Tailored)
from gethired.observability import now

__all__ = [
    "MasterSnapshot",
    "from_bullets",
    "from_master_dict",
    "from_run_result_dict",
    "from_tailored_dict",
    "load_master",
    "snapshot",
    "render_json",
    "as_dict",
]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def from_bullets(items: list[dict[str, str]]) -> tuple[Bullet, ...]:
    """Map a list of ``{"text": str}`` dicts to a tuple of ``Bullet`` values."""
    return tuple(Bullet(text=item["text"]) for item in items)


def from_master_dict(raw: dict[str, Any]) -> Resume:
    """Construct a ``Resume`` from the JSON-serialised shape.

    The ``raw`` mapping must contain ``summary``, ``skills``, ``experience``,
    ``projects``, ``education``, and ``awards``. Optional ``version`` (or
    legacy ``schema_version``) is ignored.
    """
    contact = raw.get("contact", {})
    skills_data = Skills(categories={k: tuple(v) for k, v in raw["skills"]["categories"].items()})
    experience_data = tuple(
        Experience(
            role=exp["role"],
            company=exp["company"],
            start_date=exp["start_date"],
            end_date=exp["end_date"],
            bullets=from_bullets(exp["bullets"]))
        for exp in raw["experience"]
    )
    project_data = tuple(
        Project(
            name=project["name"],
            url=project["url"],
            bullets=from_bullets(project["bullets"]))
        for project in raw["projects"]
    )
    education_data = tuple(Education(**edu) for edu in raw["education"])
    award_data = tuple(Award(**award) for award in raw["awards"])
    return Resume(
        name=contact.get("name", ""),
        email=contact.get("email", ""),
        city=contact.get("city", ""),
        phone=contact.get("phone", ""),
        github=contact.get("github") or contact.get("github_url"),
        linkedin=contact.get("linkedin") or contact.get("linkedin_url"),
        summary=raw["summary"],
        skills=skills_data,
        experience=experience_data,
        projects=project_data,
        education=education_data,
        awards=award_data)


def skills_from(raw: dict[str, Any]) -> Skills:
    """Reconstruct the Skills dataclass from the serialised categories."""
    return Skills(categories={k: tuple(v) for k, v in raw["skills"]["categories"].items()})


def experiences_from(raw: dict[str, Any]) -> tuple[Experience, ...]:
    """Reconstruct Experience entries from the serialised list."""
    return tuple(
        Experience(
            role=exp["role"],
            company=exp["company"],
            start_date=exp["start_date"],
            end_date=exp["end_date"],
            bullets=from_bullets(exp["bullets"]))
        for exp in raw["experiences"]
    )


def projects_from(raw: dict[str, Any]) -> tuple[Project, ...]:
    """Reconstruct Project entries from the serialised list."""
    return tuple(
        Project(
            name=project["name"],
            url=project["url"],
            bullets=from_bullets(project["bullets"]))
        for project in raw["projects"]
    )


def grounding_from(raw: dict[str, Any]) -> tuple[Citation, ...]:
    """Reconstruct Citation entries from the serialised list."""
    return tuple(Citation(**citation) for citation in raw.get("grounding", []))


def from_tailored_dict(raw: dict[str, Any]) -> Tailored:
    """Construct a ``Tailored`` from the JSON-serialised shape.

    Tolerates a missing ``run_result`` (legacy snapshots) by returning
    ``run_result=None``.
    """
    contact = raw.get("contact", {})
    return Tailored(
        name=contact.get("name", ""),
        email=contact.get("email", ""),
        city=contact.get("city", ""),
        phone=contact.get("phone", ""),
        github=contact.get("github") or contact.get("github_url"),
        linkedin=contact.get("linkedin") or contact.get("linkedin_url"),
        summary=raw["summary"],
        skills=skills_from(raw),
        experience=experiences_from(raw),
        projects=projects_from(raw),
        education=tuple(Education(**edu) for edu in raw["education"]),
        awards=tuple(Award(**award) for award in raw["awards"]),
        dropped=tuple(Reason(**dropped) for dropped in raw.get("dropped", [])),
        rationale=raw.get("rationale", ""),
        grounding=grounding_from(raw),
        jobs=(),
        run_result=from_run_result_dict(raw.get("run_result")))


def load_resume(path: Path) -> Resume:
    """Read a resume JSON snapshot from disk and coerce it.

    Args:
        path: Path to a JSON file produced by ``render_json`` against a
            ``Resume`` (typically via ``snapshot``).

    Returns:
        The reconstructed ``Resume``.

    Deprecated alias for :func:`load_resume`. Removed in Unit 11.
    """
    raw: dict[str, Any] = json.loads(Path(path).read_text())
    return from_master_dict(raw)


# ---------------------------------------------------------------------------
# Snapshotting (Resume → Tailored for JSON serialisation)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MasterSnapshot:
    """Identifies the provenance of a master-snapshot run.

    Used by ``snapshot`` to attach a deterministic run identity
    so the JSON file is traceable back to the source master.
    """

    model: str = "master"
    draft_model: str | None = None


def snapshot(
    master: Resume,
    *,
    snapshot: MasterSnapshot | None = None) -> Tailored:
    """Wrap a master resume in a ``Tailored`` for JSON serialisation.

    The produced object carries the master fields verbatim and a synthetic
    run result (model='master') so the JSON is structurally identical to a
    real tailored run. ``jobs``, ``grounding``, and ``dropped`` are empty.
    """
    snap = snapshot or MasterSnapshot()
    return Tailored(
        name=master.name,
        email=master.email,
        city=master.city,
        phone=master.phone,
        github=master.github,
        linkedin=master.linkedin,
        summary=master.summary,
        skills=master.skills,
        experience=master.experience,
        projects=master.projects,
        education=master.education,
        awards=master.awards,
        dropped=(),
        rationale="Resume snapshot",
        grounding=(),
        jobs=(),
        run_result=RunResult(
            run=Run(
                id=str(uuid4()),
                started_at=now(),
                resume_hash=master.content_hash(),
                jd_hash="",
                model=snap.model,
                draft_model=snap.draft_model),
            completed_at=now(),
            duration_seconds=0.0,
            total_input_tokens=0,
            total_output_tokens=0,
            retry_attempts=0,
            final_outcome=Outcome.SUCCESS,
            jobs=()))


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_json(tailored: Tailored) -> str:
    """Serialise a ``Tailored`` to pretty-printed JSON.

    ``dataclasses.asdict`` already recurses through the tree, unwraps
    nested dataclasses, and converts ``StrEnum`` fields to their string
    values. ``default=str`` covers anything asdict doesn't recognise
    (e.g. ``UUID``-derived identifiers).
    """
    return json.dumps(asdict(tailored), indent=2, default=str)


def as_dict(tailored: Tailored) -> dict[str, Any]:
    """Return the same ``render_json`` payload but as a dict, not a string."""
    result: dict[str, Any] = json.loads(render_json(tailored))
    return result


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def from_run_result_dict(raw: dict[str, Any] | None) -> RunResult | None:
    """Rebuild a ``RunResult`` from the embedded ``run`` block, if present.

    Restores StrEnum fields (``final_outcome``) from their serialised string
    form so the reconstructed model respects the ``RunResult`` type contract.
    """
    if raw is None:
        return None
    run = Run(**raw.get("run", {}))
    data_dict: dict[str, Any] = {**raw, "run": run}
    if "final_outcome" in data_dict and isinstance(data_dict["final_outcome"], str):
        data_dict["final_outcome"] = Outcome(data_dict["final_outcome"])
    if "jobs" in data_dict:
        data_dict["jobs"] = tuple(from_step_dict(job) for job in data_dict["jobs"])
    return RunResult(**data_dict)


def from_step_dict(raw: dict[str, Any]) -> Step:
    """Rebuild a ``Step`` from its serialised form, restoring StrEnum fields."""
    if "type" in raw and isinstance(raw["type"], str):
        raw = {**raw, "type": StepKind(raw["type"])}
    if "status" in raw and isinstance(raw["status"], str):
        raw = {**raw, "status": StepStatus(raw["status"])}
    if "metadata" in raw and isinstance(raw["metadata"], dict):
        raw = {**raw, "metadata": StepMeta(**raw["metadata"])}
    return Step(**raw)


# Deprecated alias for load_resume. Removed in Unit 11.
load_master = load_resume
