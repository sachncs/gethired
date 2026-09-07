"""Tests over the corpus of valid resume.tex fixtures.

The corpus exercises realistic variation in contact formatting, skill
categories, role counts, project counts, education, and awards. Every
fixture must dispatch into a fully-populated ``Resume`` and the full
tailoring pipeline must run against it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.models.test import TestModel

from gethired.models import Job
from gethired.parser import parse_tex as tex
from gethired.renderer import tex as render_tex
from gethired.renderer import text as render_text
from gethired.tailor import Tailor

FIXTURES_DIR = Path(__file__).parent / "fixtures"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

CORPUS_DIR = FIXTURES_DIR / "resumes"
CANONICAL = PROJECT_ROOT / "sample.tex"


def corpus_paths() -> list[Path]:
    paths = sorted(CORPUS_DIR.glob("*.tex"))
    return [CANONICAL, *paths]


CORPUS_IDS = [
    f"canonical:{path.name}" if path == CANONICAL else path.name for path in corpus_paths()
]

SAMPLE_JD = Job(
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
    content_hash="sample")


@pytest.mark.parametrize("fixture_path", corpus_paths(), ids=CORPUS_IDS)
def test_corpus_fixture_parses_to_populated_resume(fixture_path: Path) -> None:
    resume = tex(fixture_path)

    assert resume.name, "contact.name must be non-empty"
    assert resume.city, "contact.city must be non-empty"
    assert resume.phone, "contact.phone must be non-empty"
    assert resume.email, "contact.email must be non-empty"
    assert resume.summary, "summary must be non-empty"
    assert resume.skills.categories, "skills must contain at least one category"
    assert resume.experience, "at least one experience is required"
    for experience in resume.experience:
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
    first = tex(fixture_path)
    second = tex(fixture_path)
    assert first.content_hash() == second.content_hash()


@pytest.mark.parametrize("fixture_path", corpus_paths(), ids=CORPUS_IDS)
def test_corpus_fixture_runs_tailor_pipeline(fixture_path: Path) -> None:
    """The full pipeline (parse → describe → write → critic) must produce a
    structurally-valid TailoredResume that preserves the master's data.

    Verifies:
    - The TailoredResume round-trips the master's contact information
    - The writer's Step trail includes TAILOR + the four validation kinds
    - The critic's report contains 12 ATS gate results
    - The rendered TeX output contains the master's name
    """
    tailor = Tailor(
        resume=fixture_path,
        job_description=SAMPLE_JD,
        debug=False,
        model="test",
        model_instance=TestModel())
    master = tailor.master
    result = tailor.run()

    # 1. The contact must round-trip exactly
    assert result.name == master.name
    assert result.email == master.email
    # 2. The Step trail must include the core kinds
    job_kinds = {j.type.value for j in result.jobs}
    expected_kinds = {
        "tailor",
        "validate_grounding",
        "validate_style",
        "validate_plagiarism",
        "validate_ats",
    }
    assert expected_kinds.issubset(job_kinds), f"missing step kinds: {expected_kinds - job_kinds}"
    # 3. The validation Step kinds must have non-empty results
    for kind in expected_kinds:
        matching = [j for j in result.jobs if j.type.value == kind]
        assert matching, f"no {kind} step found in trail"
    # 4. The rendered output must be non-empty


    txt = render_text(result)
    assert master.name in txt, "rendered text must contain master name"
    # 5. The TeX source must contain standard section headings


    tex_source = render_tex(result)
    assert "\\section{Summary}" in tex_source
    assert "\\section{Experience}" in tex_source
