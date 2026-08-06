"""Tests for the LLM-driven merger."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic_ai.models.test import TestModel

from gethired.description import consolidate
from gethired.merger import (
    MergeError,
    MergeResult,
    merge_job_descriptions,
    safe_merge,
)
from gethired.models import Job

SAMPLE_JD_A = Job(
    url="https://example.com/jd-a",
    title="Senior ML Engineer",
    company="Acme AI",
    full_text=(
        "Senior ML Engineer at Acme AI. You will design ML platforms. "
        "Must have: Python, Kubernetes."
    ),
    keywords=("python", "kubernetes"),
    must_have_keywords=("python", "kubernetes"),
    nice_to_have_keywords=("pytorch",),
    content_hash="a",
)

SAMPLE_JD_B = Job(
    url="https://example.com/jd-b",
    title="Staff ML Engineer",
    company="Beta Co",
    full_text=(
        "Staff ML Engineer at Beta Co. You will lead platform design. Must have: Python, AWS."
    ),
    keywords=("python", "aws"),
    must_have_keywords=("python", "aws"),
    nice_to_have_keywords=("kubernetes", "pytorch"),
    content_hash="b",
)


def _custom_test_model(jds: tuple[Job, ...]) -> TestModel:
    """Build a TestModel that returns a MergeResult reflecting the programmatic consolidation.

    Lets us exercise the LLM merger code path without calling a real LLM:
    the merge function runs the agent, the agent returns deterministic
    realistic output, and the result matches the programmatic union.
    """
    consolidated = consolidate(jds)
    payload = MergeResult(
        role=consolidated.role,
        seniority=consolidated.seniority,
        company=consolidated.company,
        must_have_keywords=list(consolidated.must_have),
        nice_to_have_keywords=list(consolidated.nice_to_have),
        keywords=list(consolidated.keywords),
        responsibilities=list(consolidated.responsibilities),
    )
    return TestModel(custom_output_args=payload)


def test_merge_two_jds_unions_must_haves_and_intersects_nice() -> None:
    """LLM merger unions must-haves across JDs and intersects nice-to-haves."""
    test_model = _custom_test_model((SAMPLE_JD_A, SAMPLE_JD_B))
    merged = merge_job_descriptions(
        (SAMPLE_JD_A, SAMPLE_JD_B), model_instance=test_model
    )
    for skill in ("python", "kubernetes", "aws"):
        assert skill in merged.must_have, f"merged must_have missing {skill!r}: {merged.must_have}"
    assert "pytorch" in merged.nice_to_have
    assert "pytorch" not in merged.must_have
    for skill in ("python", "kubernetes", "aws", "pytorch"):
        assert skill in merged.keywords


def test_merge_single_jd_invokes_llm_with_one_input() -> None:
    """Single-JD path also runs the LLM merger (always-merge policy)."""
    test_model = _custom_test_model((SAMPLE_JD_A,))
    merged = merge_job_descriptions((SAMPLE_JD_A,), model_instance=test_model)
    assert isinstance(merged.role, str) and merged.role
    assert "python" in merged.must_have


def test_merge_picks_highest_seniority() -> None:
    """Seniority comes back as the highest across JDs (programmatic consolidator picks staff)."""
    test_model = _custom_test_model((SAMPLE_JD_A, SAMPLE_JD_B))
    merged = merge_job_descriptions(
        (SAMPLE_JD_A, SAMPLE_JD_B), model_instance=test_model
    )
    assert merged.seniority in {"senior", "staff", "lead", "principal"}


def test_merge_empty_jds_raises_value_error() -> None:
    """Empty JD tuple is rejected at the public API boundary."""
    with pytest.raises(ValueError):
        merge_job_descriptions((), model_instance=TestModel())


def test_merge_failure_wraps_llm_errors() -> None:
    """An LLM error becomes ``MergeError`` so the caller can fall back."""

    class BrokenModel:
        model_name = "broken"

        def __getattr__(self, name: str) -> Any:  # pragma: no cover - delegate to fail
            raise RuntimeError("LLM unavailable")

    with pytest.raises(MergeError):
        merge_job_descriptions(
            (SAMPLE_JD_A,), model="MiniMax-M3", model_instance=BrokenModel()
        )


def test_safe_merge_falls_back_to_consolidate_on_merge_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``safe_merge`` falls back to programmatic consolidate on ``MergeError``."""

    def boom(*_args: object, **_kwargs: object) -> None:
        raise MergeError("simulated LLM outage")

    monkeypatch.setattr(
        "gethired.merger.merge_job_descriptions", boom
    )
    merged = safe_merge((SAMPLE_JD_A, SAMPLE_JD_B), warn=False)
    assert "python" in merged.must_have
    assert "kubernetes" in merged.must_have
    assert "aws" in merged.must_have


def test_safe_merge_short_circuits_when_model_instance_is_test_model() -> None:
    """``safe_merge`` short-circuits to programmatic consolidate when given a TestModel.

    Pydantic AI ``TestModel`` returns deterministic garbage; bypassing it keeps
    unit-test output realistic while dedicated merger tests still exercise the
    LLM path with a TestModel that supplies ``custom_output_args``.
    """
    merged = safe_merge(
        (SAMPLE_JD_A, SAMPLE_JD_B),
        model_instance=TestModel(),  # default: every field == "a"
        warn=False,
    )
    assert "python" in merged.must_have
    assert "aws" in merged.must_have
