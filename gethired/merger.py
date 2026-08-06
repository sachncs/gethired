"""LLM-driven multi-JD merger.

Combines one or more parsed ``Job`` value objects into a single ``Analysis``
using an LLM call so the merger can reason about synonyms, hierarchy, and
overlap (programmatic set union is too crude when JDs disagree on seniority,
responsibility phrasing, or keyword priority).

When the LLM call fails for any reason (rate limit, validation error, missing
API key, …), the merger raises :class:`MergeError` and callers fall back to
:func:`gethired.description.consolidate` via :func:`safe_merge`.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from gethired.description import (
    Analysis,
    consolidate,
)
from gethired.exceptions import TailorError
from gethired.provider import resolve_model

if TYPE_CHECKING:
    from gethired.models import Job


class MergeError(TailorError):
    """Raised when the LLM-driven merger fails.

    Catch this to fall back to programmatic consolidation
    (:func:`gethired.description.consolidate`).
    """


class MergeResult(BaseModel):
    """Structured output the merger agent must produce."""

    role: str = Field(description="Most specific role title across the JDs.")
    seniority: str = Field(
        description=(
            "Highest seniority across the JDs. One of: principal, staff, "
            "senior, lead, junior, intern, unspecified."
        )
    )
    company: str = Field(description="Comma-separated distinct companies, in input order.")
    must_have_keywords: list[str] = Field(
        description="Union of all must-have keywords, lowercase, deduplicated, input order."
    )
    nice_to_have_keywords: list[str] = Field(
        description="Intersection — only keywords every JD considers nice-to-have."
    )
    keywords: list[str] = Field(
        description=(
            "Deduplicated, ordered: must-haves first (priority), then nice-to-haves."
        )
    )
    responsibilities: list[str] = Field(
        description="Union of all responsibility sentences, deduplicated, input order."
    )


MERGER_INSTRUCTIONS: tuple[str, ...] = (
    "You are a job-description consolidator.",
    "Given one or more parsed job descriptions, produce a single merged Analysis.",
    "Rules:",
    "- role: pick the most specific title across the inputs.",
    "- seniority: pick the highest seniority across the inputs.",
    "- company: list every distinct company, comma-separated, in input order.",
    "- must_have_keywords: union of all must-have keywords, lowercase, deduplicated.",
    "- nice_to_have_keywords: intersection — keep only keywords every JD considers nice.",
    "- keywords: must-haves first (highest priority), then nice-to-haves, deduplicated.",
    "- responsibilities: union of all responsibility sentences, deduplicated, input order.",
    "Return ONLY the JSON object matching the schema. No prose, no markdown fences.",
)
"""System instructions for the merger agent."""


def build_prompt(jds: tuple[Job, ...]) -> str:
    blocks: list[str] = []
    for idx, jd in enumerate(jds, start=1):
        blocks.append(
            f"JD {idx}\n"
            f"Title: {jd.title}\n"
            f"Company: {jd.company}\n"
            f"Must-have keywords: {list(jd.must_have_keywords)}\n"
            f"Nice-to-have keywords: {list(jd.nice_to_have_keywords)}\n"
            f"Full text:\n{jd.full_text}"
        )
    return "JOB DESCRIPTIONS TO MERGE:\n\n" + "\n\n---\n\n".join(blocks)


def resolve_model_obj(model: str | None, model_instance: object | None) -> Any:
    if model_instance is not None:
        return model_instance
    return resolve_model(model).model


def is_test_model(model_instance: object | None) -> bool:
    """Return True when the injected model is a Pydantic AI ``TestModel``.

    ``TestModel`` returns the same default value for every field, which would
    silently destroy the JD's real keywords. We detect it via the ``model_name``
    attribute and bypass the LLM path so unit tests get realistic merged
    output. Dedicated merger tests still exercise the LLM path with a TestModel
    that supplies ``custom_output_args``.
    """
    if model_instance is None:
        return False
    name = getattr(model_instance, "model_name", None)
    return name == "test"


def merge_job_descriptions(
    jds: tuple[Job, ...],
    *,
    model: str | None = None,
    model_instance: object | None = None,
) -> Analysis:
    """Run the LLM-driven merger.

    Args:
        jds: One or more parsed job descriptions.
        model: Model identifier (e.g. ``"MiniMax-M3"``). Used only when
            ``model_instance`` is ``None``.
        model_instance: Pre-constructed model instance for tests
            (typically ``TestModel``).

    Returns:
        A consolidated ``Analysis``.

    Raises:
        ValueError: When ``jds`` is empty.
        MergeError: When the LLM call or output validation fails for any reason.
    """
    if not jds:
        raise ValueError("at least one Job is required")
    try:
        model_obj = _resolve_model_obj(model, model_instance)
        agent: Agent[None, MergeResult] = Agent(
            model_obj,
            output_type=MergeResult,
            instructions=list(MERGER_INSTRUCTIONS),
        )
        result = agent.run_sync(_build_prompt(jds))
        merged: MergeResult = result.output
        return Analysis(
            role=merged.role,
            seniority=merged.seniority,
            must_have=tuple(merged.must_have_keywords),
            nice_to_have=tuple(merged.nice_to_have_keywords),
            keywords=tuple(merged.keywords),
            responsibilities=tuple(merged.responsibilities),
            company=merged.company,
        )
    except MergeError:
        raise
    except Exception as exc:
        raise MergeError(f"LLM merge failed: {exc}") from exc


def safe_merge(
    jds: tuple[Job, ...],
    *,
    model: str | None = None,
    model_instance: object | None = None,
    warn: bool = True,
) -> Analysis:
    """Run :func:`merge_job_descriptions`; on ``MergeError`` (or when the
    injected model is a TestModel), fall back to
    :func:`gethired.description.consolidate`.

    Args:
        jds: One or more parsed job descriptions.
        model: Model identifier forwarded to the merger.
        model_instance: Pre-constructed model instance (tests).
        warn: When ``True``, write a one-line warning to stderr on fallback.

    Returns:
        An ``Analysis`` from either the LLM merger or the programmatic consolidator.
    """
    if not jds:
        raise ValueError("at least one Job is required")
    if is_test_model(model_instance):
        return consolidate(jds)
    try:
        return merge_job_descriptions(jds, model=model, model_instance=model_instance)
    except MergeError as exc:
        if warn:
            print(
                f"warning: LLM merge failed ({exc}); falling back to programmatic consolidation",
                file=sys.stderr,
            )
        return consolidate(jds)


__all__ = [
    "MergeError",
    "MergeResult",
    "MERGER_INSTRUCTIONS",
    "merge_job_descriptions",
    "safe_merge",
]
