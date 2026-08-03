"""Tests for the writer agent (LLM path with TestModel)."""

from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from gethired.description import DescriptionAnalysis
from gethired.exceptions import ConfigurationError
from gethired.profiler import build as build_profile
from gethired.tailor import Tailor
from gethired.writer import Writer, WriterOutput, apply_writer_output


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
    tailored, jobs = writer.tailor(master=master_resume, analysis=analysis, voice=voice)
    assert tailored.contact is not None


def test_apply_writer_output_removes_dropped_entries(master_resume) -> None:
    """Dropped master paths are actually removed from the tailored resume."""
    dropped_experience = "experiences[0]"
    dropped_bullet = "experiences[1].bullets[1]"
    dropped_project = "projects[0]"
    dropped_project_bullet = "projects[1].bullets[0]"

    output = WriterOutput(
        summary="Summary",
        tailored_bullets={
            "experiences[1].bullets[0]": ["Rewritten first bullet"],
        },
        dropped=[
            dropped_experience,
            dropped_bullet,
            dropped_project,
            dropped_project_bullet,
        ],
        rationale="Drop irrelevant experience and project entries.",
    )

    tailored = apply_writer_output(master_resume, output, _sample_analysis())

    assert len(tailored.experiences) == len(master_resume.experiences) - 1
    assert tailored.experiences[0].role == master_resume.experiences[1].role
    assert [b.text for b in tailored.experiences[0].bullets] == [
        "Rewritten first bullet",
        *[b.text for b in master_resume.experiences[1].bullets[2:]],
    ]

    assert len(tailored.projects) == len(master_resume.projects) - 1
    assert tailored.projects[0].name == master_resume.projects[1].name
    assert [b.text for b in tailored.projects[0].bullets] == [
        b.text for b in master_resume.projects[1].bullets[1:]
    ]

    dropped_ids = [drop.item_id for drop in tailored.dropped]
    assert dropped_ids == [
        dropped_experience,
        dropped_bullet,
        dropped_project,
        dropped_project_bullet,
    ]
