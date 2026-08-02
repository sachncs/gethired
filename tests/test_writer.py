"""Tests for the writer agent (LLM path with TestModel)."""

from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from gethired.description import DescriptionAnalysis
from gethired.profiler import build as build_profile
from gethired.writer import Writer


def test_writer_with_test_model_produces_tailored_resume(master_resume) -> None:
    """The writer can produce a TailoredResume when given a TestModel.

    Uses pydantic-ai's TestModel which returns structured data matching
    the output type without making an actual API call.
    """
    analysis = DescriptionAnalysis(
        role="Senior ML Engineer",
        seniority="senior",
        must_have_skills=("python", "kubernetes"),
        nice_to_have_skills=("distributed",),
        keywords_to_mirror=("python", "kubernetes"),
        responsibilities=("design ML platforms",),
        company_context="Acme",
    )
    voice = build_profile(master_resume)

    test_model = TestModel()
    writer = Writer(model="test", model_instance=test_model)
    tailored, jobs = writer.tailor(
        master=master_resume,
        analysis=analysis,
        voice=voice,
    )

    # TestModel emits minimal valid structured output, so we only assert
    # the pipeline runs end-to-end without raising.
    assert tailored.contact is not None
    assert isinstance(tailored.summary, str)
    assert isinstance(tailored.skills.categories, dict)
    assert len(jobs) > 0
    assert any(j.type.value == "tailor" for j in jobs)


def test_writer_without_model_falls_back_to_deterministic(master_resume) -> None:
    """Without any model, writer produces deterministic output."""
    import os

    os.environ.pop("MODEL", None)
    analysis = DescriptionAnalysis(
        role="Senior ML Engineer",
        seniority="senior",
        must_have_skills=("python", "kubernetes"),
        nice_to_have_skills=("distributed",),
        keywords_to_mirror=("python", "kubernetes"),
        responsibilities=(),
        company_context="Acme",
    )
    voice = build_profile(master_resume)

    writer = Writer(model=None)
    tailored, jobs = writer.tailor(master=master_resume, analysis=analysis, voice=voice)

    assert tailored.contact == master_resume.contact
    assert len(tailored.experiences) == len(master_resume.experiences)
    assert "python" in tailored.summary.lower() or "kubernetes" in tailored.summary.lower()
    assert len(jobs) >= 3
