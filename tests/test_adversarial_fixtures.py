"""Tests over the adversarial resume fixtures.

Each fixture probes a failure mode of the parser. Tests encode the
desired behaviour: valid-but-awkward resumes must parse faithfully, and
genuinely invalid resumes must fail fast with ``MasterParsingError``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gethired.exceptions import MasterParsingError
from gethired.parser import parse_tex

ADVERSARIAL_DIR = Path(__file__).parent / "fixtures" / "adversarial"


def fixture(name: str) -> Path:
    return ADVERSARIAL_DIR / f"{name}.tex"


def test_empty_body_raises_master_parsing_error() -> None:
    with pytest.raises(MasterParsingError):
        parse_tex(fixture("empty_body"))


def test_missing_contact_fields_raise_master_parsing_error() -> None:
    with pytest.raises(MasterParsingError):
        parse_tex(fixture("minimal_contact"))


def test_contact_variants_parse_faithfully() -> None:
    resume = parse_tex(fixture("contact_variants"))
    assert resume.contact.name == "Sam Lee"
    assert resume.contact.city == "San Francisco"
    assert resume.contact.phone == "+1 415 555 0132"
    assert resume.contact.email == "sam.lee@example.com"
    assert resume.contact.github_url == "github.com/sam-lee"
    assert resume.contact.linkedin_url == "linkedin.com/in/sam-lee"


def test_missing_sections_parse_with_empty_optional_fields() -> None:
    resume = parse_tex(fixture("missing_sections"))
    assert resume.contact.name == "Alex Kim"
    assert resume.summary
    assert resume.skills.categories == {}
    assert resume.experiences == ()
    assert resume.projects == ()
    assert resume.education == ()


def test_empty_skill_categories_are_dropped() -> None:
    resume = parse_tex(fixture("empty_skills"))
    assert resume.skills.categories == {"Languages": ("Python", "R")}


def test_nested_braces_and_font_commands_are_cleaned() -> None:
    resume = parse_tex(fixture("nested_braces"))
    bullets = resume.experiences[0].bullets
    assert len(bullets) == 2
    assert "Designed a control plane that orchestrates" in bullets[0].text
    assert "under 30 seconds" in bullets[0].text
    assert bullets[1].text == (
        "Operated a platform handling 99.99% availability across 3 regions."
    )


def test_multi_line_bullets_are_collected() -> None:
    resume = parse_tex(fixture("multi_line_bullets"))
    bullets = resume.experiences[0].bullets
    assert len(bullets) == 2
    assert "reduces release time by 40%" in bullets[0].text
    assert "VS Code, JetBrains, and Neovim" in bullets[1].text


def test_multiple_education_entries_are_extracted() -> None:
    resume = parse_tex(fixture("education_variants"))
    assert len(resume.education) == 2
    first, second = resume.education
    assert first.institution == "University of Tokyo"
    assert first.degree == "Master of Science"
    assert first.major == "Computer Science"
    assert first.gpa == "9.0"
    assert second.institution == "Kyoto University"
    assert second.degree == "Bachelor of Engineering"
    assert second.major == "Information Systems"
    assert second.gpa == "8.7"


def test_single_date_experience_parses() -> None:
    resume = parse_tex(fixture("experience_variants"))
    assert len(resume.experiences) == 3
    first = resume.experiences[0]
    assert first.start_date == "Summer 2019"
    assert first.end_date == ""
    assert first.role == "Developer"


def test_unicode_and_math_escapes_are_cleaned() -> None:
    resume = parse_tex(fixture("unicode_latex"))
    assert resume.contact.name == "Evariste Regnault"
    assert resume.contact.city == "Montreal"
    assert "O(1)" in resume.summary
    assert "O(n log n)" in resume.summary
    assert "elision rate by 12%" in resume.experiences[0].bullets[0].text
    assert "Ü" in resume.experiences[0].bullets[0].text


def test_long_resume_parses_all_experiences() -> None:
    resume = parse_tex(fixture("long_resume"))
    assert len(resume.experiences) == 10
    total_bullets = sum(len(experience.bullets) for experience in resume.experiences)
    assert total_bullets == 40
    assert resume.contact.name == "Erin Walsh"
