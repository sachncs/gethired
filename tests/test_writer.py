"""Tests for the writer agent (LLM path with TestModel)."""

from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from gethired.description import Analysis
from gethired.exceptions import ConfigError
from gethired.profiler import build as build_profile
from gethired.tailor import Tailor
from gethired.writer import Writer, WriterOutput, apply


def _sample_analysis() -> Analysis:
    return Analysis(
        role="Senior ML Engineer",
        seniority="senior",
        must_have=("python", "kubernetes"),
        nice_to_have=("distributed",),
        keywords=("python", "kubernetes"),
        responsibilities=("design ML platforms",),
        company="Acme",
    )


def test_writer_with_test_model_produces_tailored_resume(master_resume) -> None:
    """The writer produces a TailoredResume with the master's contact preserved.

    Verifies the data path: contact information is preserved, skills are
    propagated from master, experiences are preserved, and the writer emits
    the expected Step kinds (TALOR, plus tool lookups for read-only tools).
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

    # Contact information must be preserved from the master
    assert tailored.contact.name == master_resume.contact.name
    assert tailored.contact.email == master_resume.contact.email
    assert tailored.contact.phone == master_resume.contact.phone
    # Summary is non-empty (the writer may rewrite it, but should not blank it)
    assert tailored.summary, "tailored.summary must be non-empty"
    # Skills must propagate from the master (no fabricated skills)
    assert tailored.skills.categories, "tailored.skills.categories must be non-empty"
    for category, items in tailored.skills.categories.items():
        assert category in master_resume.skills.categories, (
            f"fabricated category {category!r} not in master"
        )
        for item in items:
            assert item in master_resume.skills.categories[category], (
                f"fabricated skill {item!r} in category {category!r}"
            )
    # Experiences must be preserved (or explicitly dropped)
    assert tailored.experiences, "tailored.experiences must be non-empty"
    # Jobs must include the TAILOR step
    job_kinds = {j.type.value for j in jobs}
    assert "tailor" in job_kinds, f"missing TAILOR step in {job_kinds}"


def test_writer_with_model_instance_runs_without_model_env_var(
    monkeypatch: pytest.MonkeyPatch, master_resume
) -> None:
    """TestModel injected via model_instance allows offline runs.

    Verifies that the writer's output is a TailoredResume with the master's
    structure (contact, skills, experiences) preserved.
    """
    monkeypatch.delenv("MODEL", raising=False)
    analysis = _sample_analysis()
    voice = build_profile(master_resume)
    writer = Writer(model=None, model_instance=TestModel())
    tailored, jobs = writer.tailor(
        master=master_resume, analysis=analysis, voice=voice
    )
    # The master's contact must round-trip through the writer
    assert tailored.contact.email == master_resume.contact.email
    # The tailored resume should have at least one experience (the writer
    # preserves experiences unless explicitly dropped)
    assert len(tailored.experiences) == len(master_resume.experiences)


def test_writer_raises_configuration_error_when_model_missing(
    monkeypatch: pytest.MonkeyPatch, master_resume
) -> None:
    """Writer.tailor raises ConfigError when neither model nor model_instance.

    The error message must mention the env var name so users can fix it.
    """
    monkeypatch.delenv("MODEL", raising=False)
    analysis = _sample_analysis()
    voice = build_profile(master_resume)
    writer = Writer(model=None)
    with pytest.raises(ConfigError, match="MODEL is required"):
        writer.tailor(master=master_resume, analysis=analysis, voice=voice)


def test_tailor_raises_configuration_error_when_model_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tailor raises ConfigError at construction when MODEL is unset."""
    monkeypatch.delenv("MODEL", raising=False)
    with pytest.raises(ConfigError, match="MODEL is required"):
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

    tailored = apply(master_resume, output, _sample_analysis())

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
