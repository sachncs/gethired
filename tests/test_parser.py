"""Tests for the parser against the real sample.tex fixture."""

from __future__ import annotations

from gethired.exceptions import ParseError
from gethired.parser import parse_tex as tex


def test_contact_information_is_extracted(resume) -> None:
    assert resume.name == "Placeholder Name"
    assert resume.email == "placeholder@example.com"
    assert resume.phone == "5555550100"
    assert resume.city == "Test City"
    assert resume.github == "https://github.com/gethired"
    assert resume.linkedin == "https://linkedin.com/in/gethired"


def test_summary_is_extracted(resume) -> None:
    assert resume.summary
    assert "machine learning" in resume.summary.lower()


def test_skills_are_categorised(resume) -> None:
    categories = resume.skills.categories
    assert "Programming Languages" in categories
    assert "Python" in categories["Programming Languages"]
    assert "Machine Learning & AI" in categories
    assert "PyTorch" in categories["Machine Learning & AI"]
    assert "Cloud & Infrastructure" in categories
    assert "Kubernetes" in categories["Cloud & Infrastructure"]


def test_all_ten_experiences_extracted(resume) -> None:
    assert len(resume.experience) == 10


def test_first_experience_is_founder_at_promptsheon(resume) -> None:
    first = resume.experience[0]
    assert first.role == "Founder"
    assert first.company == "Promptsheon"
    assert first.start_date == "June 2025"
    assert first.end_date == "May 2026"
    assert len(first.bullets) >= 3


def test_experiences_are_reverse_chronological(resume) -> None:
    """Most recent first per the resume critique checklist."""
    first_year = resume.experience[0].end_date
    last_year = resume.experience[-1].end_date
    assert first_year >= last_year


def test_all_three_projects_extracted(resume) -> None:
    assert len(resume.projects) == 3


def test_project_urls_extracted(resume) -> None:
    urls = [project.url for project in resume.projects]
    assert "https://github.com/gethired/promptsheon" in urls
    assert "https://github.com/gethired/underwrite" in urls
    assert "https://github.com/gethired/vehicle-routing-problem-with-resource-constraints" in urls


def test_education_extracted(resume) -> None:
    assert len(resume.education) == 1
    edu = resume.education[0]
    assert "Engineering" in edu.degree or "Bachelor" in edu.degree
    assert "Electronics" in edu.major
    assert "Ramaiah" in edu.institution
    assert edu.gpa == "8.32"


def test_awards_extracted(resume) -> None:
    assert len(resume.awards) == 2
    titles = [award.title for award in resume.awards]
    assert any("Winner" in t for t in titles)
    assert any("Finalist" in t for t in titles)


def test_award_dates_extracted(resume) -> None:
    dates = [award.date for award in resume.awards]
    assert "September 2019" in dates
    assert "February 2020" in dates


def test_content_hash_is_deterministic(resume) -> None:
    """Same content must yield same hash for grounding checks."""
    assert resume.content_hash() == resume.content_hash()


def test_parse_tex_with_string_input(resume, resume_tex_text) -> None:
    """Passing raw TeX text should work too."""
    parsed = tex(resume_tex_text)
    assert parsed.name == resume.name


def test_parse_tex_with_invalid_source_raises(tmp_path) -> None:
    bad_path = tmp_path / "nonexistent.tex"
    with __import__("pytest").raises(ParseError):
        tex(bad_path)
