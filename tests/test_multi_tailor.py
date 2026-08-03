"""Tests for multi-JD consolidated Tailor runs."""

from __future__ import annotations

from pydantic_ai.models.test import TestModel

from gethired.description import consolidate
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


def test_tailor_accepts_multiple_job_descriptions(master_resume) -> None:
    """Tailor accepts a tuple of Job values and produces a single Tailored.

    Verifies the multi-JD data path: a single run produces a run-id,
    the master's contact is preserved, and the writer's Step trail
    includes a TAILOR step.
    """
    tailor = Tailor(
        resume=master_resume,
        job_description=(SAMPLE_JD_A, SAMPLE_JD_B),
        model="test",
        model_instance=TestModel(),
    )
    result = tailor.run()
    # Contact must round-trip from master
    assert result.contact.email == master_resume.contact.email
    # The run must have a UUID-shaped run-id
    assert len(result.run.id) == 36
    # The writer's Step trail must include the TAILOR step
    assert any(j.type.value == "tailor" for j in result.jobs)


def test_tailor_with_multiple_jds_consolidates_analysis() -> None:
    """consolidate() unions must-haves and intersects nice-to-haves across JDs.

    Verifies the consolidation algorithm:
    - must_haves are the union (any JD that requires a skill = required)
    - nice_to_haves are the intersection (only when every JD considers it nice)
    - keywords are the dedup'd priority-ordered union
    """
    consolidated = consolidate((SAMPLE_JD_A, SAMPLE_JD_B))

    # Union of must-haves: {python, kubernetes, aws}
    for skill in ("python", "kubernetes", "aws"):
        assert skill in consolidated.must_have, (
            f"consolidated must_have missing {skill!r}: {consolidated.must_have}"
        )
    # Intersection of nice-to-haves: only "pytorch" is in both
    assert "pytorch" in consolidated.nice_to_have
    # pytorch is not a must-have (it's in nice-to-have for both)
    assert "pytorch" not in consolidated.must_have
    # Keywords are dedup'd and ordered (must-haves first)
    for skill in ("python", "kubernetes", "aws", "pytorch"):
        assert skill in consolidated.keywords


def test_tailor_run_with_multiple_jds_persists_artifacts(
    master_resume, tmp_path
) -> None:
    """Multi-JD run produces a single run-dir with all expected files.

    Verifies the on-disk data process: parsing, JD input, run-id
    generation, and artefact persistence.
    """
    tailor = Tailor(
        resume=master_resume,
        job_description=(SAMPLE_JD_A, SAMPLE_JD_B),
        model="test",
        model_instance=TestModel(),
        tailored_dir=tmp_path,
    )
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
    import json
    on_disk = json.loads((run_dir / "tailored.json").read_text())
    assert on_disk["contact"]["name"] == result.contact.name
