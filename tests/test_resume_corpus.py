"""Tests over the corpus of valid resume.tex fixtures.

The corpus exercises realistic variation in contact formatting, skill
categories, role counts, project counts, education, and awards. Every
fixture must parse into a fully-populated ``MasterResume`` and the full
tailoring pipeline must run against it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.models.test import TestModel

from gethired.models import JobDescription
from gethired.parser import parse_tex
from gethired.tailor import Tailor

FIXTURES_DIR = Path(__file__).parent / "fixtures"

CORPUS_DIR = FIXTURES_DIR / "resumes"
CANONICAL = FIXTURES_DIR / "resume.tex"


def corpus_paths() -> list[Path]:
    paths = sorted(CORPUS_DIR.glob("*.tex"))
    return [CANONICAL, *paths]


CORPUS_IDS = [
    f"canonical:{path.name}" if path == CANONICAL else path.name
    for path in corpus_paths()
]

SAMPLE_JD = JobDescription(
    url="https://example.com/jd",
    title="Senior Machine Learning Engineer",
    company="Acme AI",
    full_text=(
        "Senior Machine Learning Engineer — Acme AI. "
        "We need Python, Kubernetes, Docker, AWS, distributed systems, "
        "PyTorch, TensorFlow. 5+ years experience. "
        "Must have: machine learning engineering, production Kubernetes."
    ),
    keywords=("python", "kubernetes", "docker", "aws", "pytorch", "tensorflow"),
    must_have_keywords=("python", "kubernetes"),
    nice_to_have_keywords=("pytorch", "tensorflow"),
    content_hash="sample",
)


@pytest.mark.parametrize("fixture_path", corpus_paths(), ids=CORPUS_IDS)
def test_corpus_fixture_parses_to_populated_resume(fixture_path: Path) -> None:
    resume = parse_tex(fixture_path)

    assert resume.contact.name, "contact.name must be non-empty"
    assert resume.contact.city, "contact.city must be non-empty"
    assert resume.contact.phone, "contact.phone must be non-empty"
    assert resume.contact.email, "contact.email must be non-empty"
    assert resume.summary, "summary must be non-empty"
    assert resume.skills.categories, "skills must contain at least one category"
    assert resume.experiences, "at least one experience is required"
    for experience in resume.experiences:
        assert experience.role, "experience role must be non-empty"
        assert experience.company, "experience company must be non-empty"
        assert experience.start_date, "experience start_date must be non-empty"
        assert experience.end_date, "experience end_date must be non-empty"
    assert resume.education, "at least one education entry is required"
    for education in resume.education:
        assert education.institution, "education institution must be non-empty"
        assert education.degree, "education degree must be non-empty"
        assert education.major, "education major must be non-empty"


@pytest.mark.parametrize("fixture_path", corpus_paths(), ids=CORPUS_IDS)
def test_corpus_fixture_hash_is_deterministic(fixture_path: Path) -> None:
    first = parse_tex(fixture_path)
    second = parse_tex(fixture_path)
    assert first.content_hash() == second.content_hash()


@pytest.mark.parametrize("fixture_path", corpus_paths(), ids=CORPUS_IDS)
def test_corpus_fixture_runs_tailor_pipeline(fixture_path: Path) -> None:
    tailor = Tailor(
        resume=fixture_path,
        job_description=SAMPLE_JD,
        debug=False,
        model="test",
        model_instance=TestModel(),
    )
    result = tailor.run()
    assert result.run.id
    assert result.contact is not None
    assert result.summary
    assert result.experiences
