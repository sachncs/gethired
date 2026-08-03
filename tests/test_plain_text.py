from pathlib import Path

import pytest

from gethired.exceptions import ParseError
from gethired.parser import parse_tex as tex
from gethired.parser import parse_text as text

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_plain_text_contact_is_extracted() -> None:
    resume = text(fixture("plain_text_resume.txt"))
    assert resume.contact.name == "Jane Smith"
    assert resume.contact.city == "Austin"
    assert resume.contact.phone == "(512) 555-0142"
    assert resume.contact.email == "jane.smith@example.com"
    assert resume.contact.github_url == "github.com/janesmith"
    assert resume.contact.linkedin_url == "linkedin.com/in/janesmith"


def test_plain_text_summary_is_extracted() -> None:
    resume = text(fixture("plain_text_resume.txt"))
    assert resume.summary == "Full-stack engineer with 8 years building web platforms at scale."


def test_plain_text_skills_are_categorised() -> None:
    resume = text(fixture("plain_text_resume.txt"))
    assert resume.skills.categories == {
        "Languages": ("Python", "TypeScript", "SQL"),
        "Frameworks": ("Django", "React", "FastAPI"),
        "DevOps": ("Docker", "Kubernetes", "AWS"),
    }


def test_plain_text_experiences_are_extracted() -> None:
    resume = text(fixture("plain_text_resume.txt"))
    assert len(resume.experiences) == 2
    first, second = resume.experiences
    assert first.role == "Senior Software Engineer"
    assert first.company == "Acme Corp"
    assert first.start_date == "May 2021"
    assert first.end_date == "Present"
    assert [bullet.text for bullet in first.bullets] == [
        "Led a team of six building the payments platform.",
        "Cut p95 latency by 40% via caching.",
    ]
    assert second.role == "Software Engineer"
    assert second.company == "Beta Labs"
    assert second.start_date == "Jun 2018"
    assert second.end_date == "Apr 2021"


def test_plain_text_projects_are_extracted() -> None:
    resume = text(fixture("plain_text_resume.txt"))
    assert len(resume.projects) == 1
    assert resume.projects[0].name == "gethired — resume linter"
    assert resume.projects[0].url == "https://github.com/janesmith/gethired"
    assert [bullet.text for bullet in resume.projects[0].bullets] == [
        "Lints LaTeX resumes against ATS rules."
    ]


def test_plain_text_education_is_extracted() -> None:
    resume = text(fixture("plain_text_resume.txt"))
    assert len(resume.education) == 1
    entry = resume.education[0]
    assert entry.degree == "BSc in Computer Science"
    assert entry.institution == "University of Texas"
    assert entry.graduation == "May 2018"
    assert entry.gpa == "3.8"


def test_plain_text_awards_are_extracted() -> None:
    resume = text(fixture("plain_text_resume.txt"))
    assert len(resume.awards) == 2
    first, second = resume.awards
    assert first.title == "Employee of the Year"
    assert first.organization == "Acme Corp"
    assert first.date == "2023"
    assert first.description == "Recognized for the payments migration."
    assert second.title == "Best Hackathon Project"
    assert second.organization == "Local Hack Night"
    assert second.date == "2019"


def test_plain_text_missing_contact_fails_fast() -> None:
    with pytest.raises(ParseError) as exc:
        text("Some Person\nNo city or contact info here.")
    assert "missing required contact fields" in str(exc.value)


def test_plain_text_title_line_is_skipped() -> None:
    payload = (
        "RESUME\n"
        "Bob Jones\n"
        "Paris, France | 33 6 12 34 56 78 | bob@example.com\n"
        "\n"
        "SUMMARY\nGreat engineer.\n"
    )
    resume = text(payload)
    assert resume.contact.name == "Bob Jones"
    assert resume.contact.city == "Paris"


def test_plain_text_education_major_split() -> None:
    payload = (
        "Alex Doe\n"
        "London, UK | 444 555 6666 | alex@example.com\n"
        "\n"
        "EDUCATION\n\n"
        "MSc, Data Science — University College London\n"
        "2020\n"
    )
    resume = text(payload)
    entry = resume.education[0]
    assert entry.degree == "MSc"
    assert entry.major == "Data Science"
    assert entry.institution == "University College London"
    assert entry.graduation == "2020"


def test_parse_text_routes_tex_to_parse_tex() -> None:
    with pytest.raises(ParseError):
        tex("\\documentclass{article}\n\\begin{document}\n\\end{document}")
