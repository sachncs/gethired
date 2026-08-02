"""Tests for the writer agent (LLM path with TestModel)."""

from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from gethired.description import DescriptionAnalysis
from gethired.exceptions import ConfigurationError
from gethired.profiler import build as build_profile
from gethired.tailor import Tailor
from gethired.writer import Writer


def _sample_analysis() -> DescriptionAnalysis:
    return DescriptionAnalysis(
        role="Senior ML Engineer",
        seniority="senior",
        must_have_skills=("python", "kubernetes"),
        nice_to_have_skills=("distributed",),
        keywords_to_mirror=("python", "kubernetes"),
        responsibilities=("design ML platforms",),
        company_context="Acme",
    )


def test_writer_with_test_model_produces_tailored_resume(master_resume) -> None:
    """The writer can produce a TailoredResume when given a TestModel.

    Uses pydantic-ai's TestModel which returns structured data matching
    the output type without making an actual API call.
    """
    analysis = _sample_analysis()
    voice = build_profile(master_resume)

    test_model = TestModel()
    writer = Writer(model="test", model_instance=test_model)
    tailored, jobs = writer.tailor(
        master=master_resume,
        analysis=analysis,
        voice=voice,
    )

    assert tailored.contact is not None
    assert isinstance(tailored.summary, str)
    assert isinstance(tailored.skills.categories, dict)
    assert len(jobs) > 0
    assert any(j.type.value == "tailor" for j in jobs)


def test_writer_raises_configuration_error_when_model_missing(
    monkeypatch: pytest.MonkeyPatch, master_resume
) -> None:
    """Writer.tailor raises ConfigurationError when neither model nor model_instance."""
    monkeypatch.delenv("MODEL", raising=False)
    analysis = _sample_analysis()
    voice = build_profile(master_resume)
    writer = Writer(model=None)
    with pytest.raises(ConfigurationError, match="MODEL is required"):
        writer.tailor(master=master_resume, analysis=analysis, voice=voice)


def test_tailor_raises_configuration_error_when_model_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tailor raises ConfigurationError at construction when MODEL is unset."""
    monkeypatch.delenv("MODEL", raising=False)
    with pytest.raises(ConfigurationError, match="MODEL is required"):
        Tailor(
            resume="resume.tex",
            job_description="https://example.com/jd",
            debug=False,
        )


def test_writer_with_model_instance_runs_without_model_env_var(
    monkeypatch: pytest.MonkeyPatch, master_resume
) -> None:
    """TestModel injected via model_instance allows offline runs."""
    monkeypatch.delenv("MODEL", raising=False)
    analysis = _sample_analysis()
    voice = build_profile(master_resume)
    writer = Writer(model=None, model_instance=TestModel())
    tailored, jobs = writer.tailor(
        master=master_resume, analysis=analysis, voice=voice
    )
    assert tailored.contact is not None
    assert len(jobs) > 0