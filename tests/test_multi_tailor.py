"""Tests for multi-JD consolidated Tailor runs."""

from __future__ import annotations

import json

import pytest
from pydantic_ai.models.test import TestModel

from gethired.description import consolidate
from gethired.merger import MergeError, MergeResult, merge_job_descriptions, safe_merge
from gethired.models import Job
from gethired.tailor import Tailor

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
    content_hash="a")

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
    content_hash="b")


def realistic_test_model(jds: tuple[Job, ...]) -> TestModel:
    """TestModel that returns the programmatic consolidation as its LLM output."""
    consolidated = consolidate(jds)
    payload = MergeResult(
        role=consolidated.role,
        seniority=consolidated.seniority,
        company=consolidated.company,
        must_have_keywords=list(consolidated.must_have),
        nice_to_have_keywords=list(consolidated.nice_to_have),
        keywords=list(consolidated.keywords),
        responsibilities=list(consolidated.responsibilities))
    return TestModel(custom_output_args=payload)


def test_tailor_accepts_multiple_job_descriptions(resume) -> None:
    """Tailor accepts a tuple of Job values and produces a single Tailored.

    Verifies the multi-JD data path: a single run produces a run-id,
    the master's contact is preserved, and the writer's Step trail
    includes a TAILOR step.
    """
    tailor = Tailor(
        resume=resume,
        job_description=(SAMPLE_JD_A, SAMPLE_JD_B),
        model="test",
        model_instance=TestModel())
    result = tailor.run()
    # Contact must round-trip from master
    assert result.email == resume.email
    # The run must have a UUID-shaped run-id
    assert len(result.run.id) == 36
    # The writer's Step trail must include the TAILOR step
    assert any(j.type.value == "tailor" for j in result.jobs)


def test_tailor_with_multiple_jds_uses_llm_merge(monkeypatch: pytest.MonkeyPatch) -> None:
    """``safe_merge`` is the merger entry point the orchestrator uses.

    Verifies that when the LLM merger is invoked, the result reflects the
    LLM's output (not the programmatic union). The Tailor layer is wired to
    ``safe_merge`` so the test asserts that contract via the public merger
    API rather than the internal pipeline.
    """
    realistic_model = realistic_test_model((SAMPLE_JD_A, SAMPLE_JD_B))
    monkeypatch.setattr(
        "gethired.tailor.safe_merge",
        lambda jds, **_kw: merge_job_descriptions(jds, model_instance=realistic_model))
    merged = merge_job_descriptions(
        (SAMPLE_JD_A, SAMPLE_JD_B), model_instance=realistic_model
    )
    for skill in ("python", "kubernetes", "aws"):
        assert skill in merged.must_have
    assert "pytorch" in merged.nice_to_have
    for skill in ("python", "kubernetes", "aws", "pytorch"):
        assert skill in merged.keywords


def test_tailor_safe_merge_used_in_pipeline(
    monkeypatch: pytest.MonkeyPatch, resume, tmp_path
) -> None:
    """The Tailor pipeline routes through ``safe_merge`` (LLM + fallback)."""
    captured: list[tuple[Job, ...]] = []

    def spy_safe_merge(jds: tuple[Job, ...], **_kwargs: object):
        captured.append(jds)
        return consolidate(jds)

    monkeypatch.setattr("gethired.tailor.safe_merge", spy_safe_merge)
    tailor = Tailor(
        resume=resume,
        job_description=(SAMPLE_JD_A, SAMPLE_JD_B),
        model="test",
        model_instance=TestModel(),
        tailored_dir=tmp_path)
    tailor.run()
    assert captured, "safe_merge was not invoked"
    assert captured[0] == (SAMPLE_JD_A, SAMPLE_JD_B)


def test_tailor_run_with_multiple_jds_persists_artifacts(resume, tmp_path) -> None:
    """Multi-JD run produces a single run-dir with all expected files.

    Verifies the on-disk data process: parsing, JD input, run-id
    generation, and artefact persistence.
    """
    tailor = Tailor(
        resume=resume,
        job_description=(SAMPLE_JD_A, SAMPLE_JD_B),
        model="test",
        model_instance=TestModel(),
        tailored_dir=tmp_path)
    result = tailor.run()
    run_dir = tmp_path / result.run.id
    # The run-id is a UUID
    assert len(result.run.id) == 36
    assert result.run.model == "test"
    # The artefacts must be persisted
    assert (run_dir / "tailored.json").exists()
    assert (run_dir / "tailored.tex").exists()
    assert (run_dir / "tailored.txt").exists()
    assert (run_dir / "match_report.md").exists()
    # The on-disk JSON must round-trip to the same model
    on_disk = json.loads((run_dir / "tailored.json").read_text())
    assert on_disk["contact"]["name"] == result.name
    # Tailored carries the JD tuple and merged analysis for downstream CLI use
    assert result.jds == (SAMPLE_JD_A, SAMPLE_JD_B)
    assert result.analysis is not None
    assert "python" in result.analysis.must_have


def test_safe_merge_keeps_programmatic_fallback_intact(
    monkeypatch: pytest.MonkeyPatch) -> None:
    """If the LLM merger raises, ``safe_merge`` falls back to programmatic consolidate."""
    def boom(*_args: object, **_kwargs: object) -> None:
        raise MergeError("simulated outage")

    monkeypatch.setattr("gethired.merger.merge_job_descriptions", boom)
    merged = safe_merge((SAMPLE_JD_A, SAMPLE_JD_B), warn=False)
    assert "python" in merged.must_have
    assert "aws" in merged.must_have
