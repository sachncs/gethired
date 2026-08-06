"""Plain-text resume parser.

``plain`` converts a plain-text resume into the same
``Master`` model produced by the TeX parser. The contact block is
mandatory and fails fast with the same message as ``contact``;
every other section (summary, skills, experience, projects, education,
awards) is extracted best-effort from its standard section header.

Sections are parsed line-oriented, so values are cleaned individually and
never before the line structure is consumed.
"""

from __future__ import annotations

import re
from typing import Final

from gethired.models import (
    Award,
    Bullet,
    Contact,
    Education,
    Experience,
Resume,
    Project,
    Skills)
from gethired.text_util import (
    EMAIL_RE,
    GITHUB_BARE_RE,
    LINKEDIN_BARE_RE,
    PHONE_RE,
    clean,
    require_contact)

__all__ = [
    "parse_plain_text",
    "extract_contact",
    "extract_skills",
    "extract_experiences",
    "extract_projects",
    "extract_education",
    "extract_awards",
    "extract_dates",
    "split_blocks",
    "non_empty_lines",
    "extract_heading_text_and_url",
    "split_heading",
    "strip_bullet",
]

SECTION_HEADER_RE: Final[re.Pattern[str]] = re.compile(
    r"(?im)^[\t =_#\-*.\">'()]*("
    r"summary|objective|profile"
    r"|technical skills|skills|technologies"
    r"|work experience|employment history|employment"
    r"|experience"
    r"|selected projects|project experience|projects"
    r"|education"
    r"|awards\s*&?\s*recognition|awards|honours|honors"
    r")[\t =_#\-*.\">'()]*\r?\n"
)

CITY_STATE_RE: Final[re.Pattern[str]] = re.compile(r"([A-Z][A-Za-z .'-]+?)\s*,\s*[A-Za-z]{2,}")

BULLET_PREFIX_RE: Final[re.Pattern[str]] = re.compile(r"^\s*(?:[•\-\*▪·>]|\d{1,2}[.)])\s+")

DATE_RANGE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b("
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}"
    r"|\d{1,2}/\d{4}"
    r"|\d{4})"
    r"\s*(?:–|-|—|to)\s*"
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}"
    r"|\d{1,2}/\d{4}"
    r"|\d{4}|present|current)"
)

SINGLE_YEAR_RE: Final[re.Pattern[str]] = re.compile(r"\b(19|20)\d{2}\b")

GPA_RE: Final[re.Pattern[str]] = re.compile(r"(?:CGPA|GPA)[:\s]+([0-9]+(?:\.[0-9]+)?)")

URL_RE: Final[re.Pattern[str]] = re.compile(
    r"https?://[^\s]+|(?:www\.)?[\w-]+\.(?:com|org|net|io|dev)[^\s]*"
)

HEADING_SEPARATOR_RE: Final[re.Pattern[str]] = re.compile(r"\s+(?:—|–|—|\||·|at)\s+")

TITLE_LINE_RE: Final[re.Pattern[str]] = re.compile(r"^(?:resume|curriculum vitae|cv)$", re.I)

INSTITUTION_START_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:University|College|Institute|Institut|School|Academy)", re.I
)


def parse_plain_text(text: str) -> Master:
    """Parse a plain-text resume into a ``Master``.

    Args:
        text: Plain-text resume content.

    Returns:
        The parsed ``Master``.

    Raises:
        ParseError: When a required contact field is missing.
    """
    sections_dict = extract_sections(text)
    header_block = text[: first_header_position(text)]

    contact_info = extract_contact(text, header_block)
    summary_text = clean(sections_dict.get("summary", ""))
    skills_data = extract_skills(sections_dict.get("skills", ""))
    experience_data = extract_experiences(sections_dict.get("experience", ""))
    project_data = extract_projects(sections_dict.get("projects", ""))
    education_data = extract_education(sections_dict.get("education", ""))
    award_data = extract_awards(sections_dict.get("awards", ""))

    return Master(
        contact=contact_info,
        summary=summary_text,
        skills=skills_data,
        experience=experience_data,
        projects=project_data,
        education=education_data,
        awards=award_data)


def first_header_position(text: str) -> int:
    match = SECTION_HEADER_RE.search(text)
    return match.start() if match else len(text)


def extract_sections(text: str) -> dict[str, str]:
    matches = list(SECTION_HEADER_RE.finditer(text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        kind = section_kind(match.group(1))
        body_start = match.end()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[kind] = text[body_start:body_end]
    return sections


def section_kind(header: str) -> str:
    normalized = header.lower()
    if normalized in {"summary", "objective", "profile"}:
        return "summary"
    if normalized in {"technical skills", "skills", "technologies"}:
        return "skills"
    if normalized in {"experience", "work experience", "employment", "employment history"}:
        return "experience"
    if normalized in {"projects", "project experience", "selected projects"}:
        return "projects"
    if normalized == "education":
        return "education"
    return "awards"


def extract_contact(text: str, header_block: str) -> Contact:
    name = extract_name(text)
    email_match = EMAIL_RE.search(text)
    email = ""
    if email_match:
        email = email_match.group(1) or email_match.group(2) or ""

    phone_match = PHONE_RE.search(text)
    phone = phone_match.group(1) if phone_match else ""

    github_match = GITHUB_BARE_RE.search(text)
    github_url = github_match.group(0) if github_match else None

    linkedin_match = LINKEDIN_BARE_RE.search(text)
    linkedin_url = linkedin_match.group(0) if linkedin_match else None

    city_match = CITY_STATE_RE.search(header_block)
    city = clean(city_match.group(1)) if city_match else ""

    require_contact(name, city, phone, email)

    return Resume(name=name, city=city, phone=phone, email=email, github=github_url, linkedin=linkedin_url, summary="", skills=Skills(categories={}), experience=(), projects=(), education=(), awards=())


def extract_name(text: str) -> str:
    for line in text.splitlines():
        candidate = line
        if candidate and not TITLE_LINE_RE.match(candidate):
            return clean(candidate)
    return ""


def extract_skills(body: str) -> Skills:
    categories: dict[str, list[str]] = {}
    for raw_line in body.splitlines():
        line = strip_bullet(raw_line)
        if not line:
            continue
        category, _, values_text = split_category(line)
        for raw_value in re.split(r"[,;|•·]+", values_text):
            value = clean(raw_value)
            if value:
                categories.setdefault(category, []).append(value)
    return Skills(categories={name: tuple(values) for name, values in categories.items()})


def split_category(line: str) -> tuple[str, str, str]:
    category, separator, values = line.partition(":")
    if separator and len(category) <= 40 and values:
        return category, separator, values
    return "Skills", ":", line


def extract_experiences(body: str) -> tuple[Experience, ...]:
    experiences: list[Experience] = []
    for block in split_blocks(body):
        lines = non_empty_lines(block)
        heading_index = extract_heading_text_and_url(lines)
        if heading_index is None:
            continue
        heading_text = lines[heading_index]
        start_date, end_date = extract_dates(lines)
        role, company = split_heading(heading_text)
        bullets = tuple(
            Bullet(text=clean(strip_bullet(line))) for line in lines if BULLET_PREFIX_RE.match(line)
        )
        experiences.append(
            Experience(
                role=role,
                company=company,
                start_date=start_date,
                end_date=end_date,
                bullets=bullets)
        )
    return tuple(experiences)


def extract_projects(body: str) -> tuple[Project, ...]:
    projects: list[Project] = []
    for block in split_blocks(body):
        lines = non_empty_lines(block)
        heading_index = extract_heading_text_and_url(lines)
        if heading_index is None:
            continue
        name = clean(lines[heading_index])
        url_match = next((URL_RE.search(line) for line in lines if URL_RE.search(line)), None)
        url = clean(url_match.group(0)) if url_match else ""
        bullets = tuple(
            Bullet(text=clean(strip_bullet(line))) for line in lines if BULLET_PREFIX_RE.match(line)
        )
        projects.append(Project(name=name, url=url, bullets=bullets))
    return tuple(projects)


def extract_education(body: str) -> tuple[Education, ...]:
    education: list[Education] = []
    for block in split_blocks(body):
        lines = non_empty_lines(block)
        heading_index = extract_heading_text_and_url(lines)
        if heading_index is None:
            continue
        heading_text = lines[heading_index]
        degree, institution = split_heading(heading_text)
        major = ""
        if "," in degree:
            degree, _, rest = degree.partition(",")
            rest = rest.strip()
            if INSTITUTION_START_RE.match(rest):
                institution = rest
            else:
                major = rest
        _, end_date = extract_dates(lines)
        graduation = end_date
        if not graduation:
            year_match = SINGLE_YEAR_RE.search(block)
            graduation = year_match.group(0) if year_match else ""
        gpa_match = GPA_RE.search(block)
        gpa = gpa_match.group(1) if gpa_match else None
        education.append(
            Education(
                institution=clean(institution),
                location="",
                degree=clean(degree),
                major=clean(major),
                graduation=graduation,
                gpa=gpa)
        )
    return tuple(education)


def extract_awards(body: str) -> tuple[Award, ...]:
    awards: list[Award] = []
    for block in split_blocks(body):
        lines = non_empty_lines(block)
        heading_index = extract_heading_text_and_url(lines)
        if heading_index is None:
            continue
        heading_text = lines[heading_index]
        title, organization = split_heading(heading_text)
        start_date, end_date = extract_dates(lines)
        date = start_date or end_date
        if not date:
            year_match = SINGLE_YEAR_RE.search(organization)
            if year_match:
                date = year_match.group(0)
                organization = organization[: year_match.start()].rstrip(" ,-")
        if not date:
            year_match = SINGLE_YEAR_RE.search(block)
            date = year_match.group(0) if year_match else ""
        description_lines = [
            clean(strip_bullet(line)) for line in lines if BULLET_PREFIX_RE.match(line)
        ]
        awards.append(
            Award(
                title=clean(title),
                organization=clean(organization),
                date=date,
                description=" ".join(description_lines))
        )
    return tuple(awards)


def split_blocks(body: str) -> list[str]:
    return [block for block in re.split(r"\n\s*\n", body) if block]


def non_empty_lines(block: str) -> list[str]:
    return [line for line in block.splitlines() if line]


def extract_heading_text_and_url(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if not BULLET_PREFIX_RE.match(line) and not DATE_RANGE_RE.search(line):
            return index
    return None


def extract_dates(lines: list[str]) -> tuple[str, str]:
    for line in lines:
        match = DATE_RANGE_RE.search(line)
        if match:
            return clean(match.group(1)), clean(match.group(2))
    return "", ""


def split_heading(heading: str) -> tuple[str, str]:
    match = HEADING_SEPARATOR_RE.search(heading)
    if match:
        return heading[: match.start()], heading[match.end() :]
    return heading, ""


def strip_bullet(line: str) -> str:
    return BULLET_PREFIX_RE.sub("", line)
