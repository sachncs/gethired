"""Tests for multi-JD consolidated Tailor runs."""

from __future__ import annotations

from pydantic_ai.models.test import TestModel

from gethired.description import analyze_multiple
from gethired.models import JobDescription
from gethired.tailor import Tailor

SAMPLE_JD_A = JobDescription(
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

SAMPLE_JD_B = JobDescription(
    url="https://example.com/jd-b",
    title="Staff ML Engineer",
    company="Beta Co",
    full_text=(
        "Staff ML Engineer at Beta Co. You will lead platform design. "
        "Must have: Python, AWS."
    ),
    keywords=("python", "aws"),
    must_have_keywords=("python", "aws"),
    nice_to_have_keywords=("kubernetes", "pytorch"),
    content_hash="b",
)


def test_tailor_accepts_multiple_job_descriptions(master_resume) -> None:
    """Tailor accepts a tuple of JobDescription values."""
    tailor = Tailor(
        resume=master_resume,
        job_description=(SAMPLE_JD_A, SAMPLE_JD_B),
        model="test",
        model_instance=TestModel(),
    )
    result = tailor.run()
    assert result.contact is not None


def test_tailor_with_multiple_jds_consolidates_analysis() -> None:
    """analyze_multiple unions must-haves and intersects nice-to-haves."""
    consolidated = analyze_multiple((SAMPLE_JD_A, SAMPLE_JD_B))
    assert "python" in consolidated.must_have_skills
    assert "kubernetes" in consolidated.must_have_skills
    assert "aws" in consolidated.must_have_skills
    assert "pytorch" in consolidated.nice_to_have_skills


def test_tailor_run_with_multiple_jds_persists_artifacts(master_resume) -> None:
    """Multi-JD run produces a single run-id with all expected files."""
    tailor = Tailor(
        resume=master_resume,
        job_description=(SAMPLE_JD_A, SAMPLE_JD_B),
        model="test",
        model_instance=TestModel(),
        tailored_dir="tailored",
    )
    result = tailor.run()
    assert result.run.id
    assert result.run.model == "test"
