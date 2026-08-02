"""Tests for Tailor.preflight."""

from __future__ import annotations

from pydantic_ai.models.test import TestModel

from gethired.models import JobDescription, PreflightReport
from gethired.tailor import Tailor


SAMPLE_JD = JobDescription(
    url="https://example.com/jd",
    title="Senior ML Engineer",
    company="Acme AI",
    full_text="Senior ML Engineer role requiring Python and Kubernetes.",
    keywords=("python", "kubernetes"),
    must_have_keywords=("python", "kubernetes"),
    nice_to_have_keywords=(),
    content_hash="sample",
)


def test_preflight_returns_report(master_resume) -> None:
    """preflight returns a PreflightReport with the expected fields."""
    tailor = Tailor(
        resume=master_resume,
        job_description=SAMPLE_JD,
        model="test",
        model_instance=TestModel(),
    )
    report = tailor.preflight()
    assert isinstance(report, PreflightReport)
    assert report.tokens_estimate > 0
    assert "BULLETS_QUANTIFIED" in report.expected_gates
    assert 0.0 <= report.voice_drift_risk <= 1.0


def test_preflight_identifies_missing_must_haves(master_resume) -> None:
    """preflight flags must-have keywords absent from the master."""
    tailor = Tailor(
        resume=master_resume,
        job_description=SAMPLE_JD,
        model="test",
        model_instance=TestModel(),
    )
    report = tailor.preflight()
    coverage = report.jd_keyword_coverage
    assert "python" in coverage
    assert "kubernetes" in coverage