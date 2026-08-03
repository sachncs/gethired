"""Plain-text resume parser.

``parse_plain_text`` converts a plain-text resume into the same
``MasterResume`` model produced by the TeX parser. The contact block is
mandatory and fails fast with the same message as ``extract_contact``;
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
    ContactInformation,
    Education,
    Experience,
    MasterResume,
    Project,
    SkillsByCategory,
)
from gethired.text_util import (
    EMAIL_RE,
    GITHUB_BARE_RE,
    LINKEDIN_BARE_RE,
    PHONE_RE,
    clean_inline,
    validate_contact_fields,
)

__all__ = ["parse_plain_text"]

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


def parse_plain_text(text: str) -> MasterResume:
    """Parse a plain-text resume into a ``MasterResume``.

    Args:
        text: Plain-text resume content.

    Returns:
        The parsed ``MasterResume``.

    Raises:
        MasterParsingError: When a required contact field is missing.
    """
    sections = _extract_sections(text)
    header_block = text[: _first_header_position(text)]

    contact = _extract_contact(text, header_block)
    summary = clean_inline(sections.get("summary", ""))
    skills = _extract_skills(sections.get("skills", ""))
    experiences = _extract_experiences(sections.get("experience", ""))
    projects = _extract_projects(sections.get("projects", ""))
    education = _extract_education(sections.get("education", ""))
    awards = _extract_awards(sections.get("awards", ""))

    return MasterResume(
        contact=contact,
        summary=summary,
        skills=skills,
        experiences=experiences,
        projects=projects,
        education=education,
        awards=awards,
    )


def _first_header_position(text: str) -> int:
    match = SECTION_HEADER_RE.search(text)
    return match.start() if match else len(text)


def _extract_sections(text: str) -> dict[str, str]:
    matches = list(SECTION_HEADER_RE.finditer(text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        kind = _section_kind(match.group(1))
        body_start = match.end()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[kind] = text[body_start:body_end].strip()
    return sections


def _section_kind(header: str) -> str:
    normalized = header.strip().lower()
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


def _extract_contact(text: str, header_block: str) -> ContactInformation:
    name = _extract_name(text)
    email_match = EMAIL_RE.search(text)
    email = ""
    if email_match:
        email = email_match.group(1) or email_match.group(2) or ""

    phone_match = PHONE_RE.search(text)
    phone = phone_match.group(1).strip() if phone_match else ""

    github_match = GITHUB_BARE_RE.search(text)
    github_url = github_match.group(0) if github_match else None

    linkedin_match = LINKEDIN_BARE_RE.search(text)
    linkedin_url = linkedin_match.group(0) if linkedin_match else None

    city_match = CITY_STATE_RE.search(header_block)
    city = clean_inline(city_match.group(1)) if city_match else ""

    validate_contact_fields(name, city, phone, email)

    return ContactInformation(
        name=name,
        city=city,
        phone=phone,
        email=email,
        github_url=github_url,
        linkedin_url=linkedin_url,
    )


def _extract_name(text: str) -> str:
    for line in text.splitlines():
        candidate = line.strip()
        if candidate and not TITLE_LINE_RE.match(candidate):
            return clean_inline(candidate)
    return ""


def _extract_skills(body: str) -> SkillsByCategory:
    categories: dict[str, list[str]] = {}
    for raw_line in body.splitlines():
        line = _strip_bullet_prefix(raw_line).strip()
        if not line:
            continue
        category, _, values_text = _split_category(line)
        for raw_value in re.split(r"[,;|•·]+", values_text):
            value = clean_inline(raw_value)
            if value:
                categories.setdefault(category, []).append(value)
    return SkillsByCategory(categories={name: tuple(values) for name, values in categories.items()})


def _split_category(line: str) -> tuple[str, str, str]:
    category, separator, values = line.partition(":")
    if separator and len(category) <= 40 and values.strip():
        return category.strip(), separator, values
    return "Skills", ":", line


def _extract_experiences(body: str) -> tuple[Experience, ...]:
    experiences: list[Experience] = []
    for block in _split_blocks(body):
        lines = _non_empty_lines(block)
        heading_index = _heading_index(lines)
        if heading_index is None:
            continue
        heading = lines[heading_index]
        start_date, end_date = _extract_dates(lines)
        role, company = _split_heading(heading)
        bullets = tuple(
            Bullet(text=clean_inline(_strip_bullet_prefix(line)))
            for line in lines
            if BULLET_PREFIX_RE.match(line)
        )
        experiences.append(
            Experience(
                role=role,
                company=company,
                start_date=start_date,
                end_date=end_date,
                bullets=bullets,
            )
        )
    return tuple(experiences)


def _extract_projects(body: str) -> tuple[Project, ...]:
    projects: list[Project] = []
    for block in _split_blocks(body):
        lines = _non_empty_lines(block)
        heading_index = _heading_index(lines)
        if heading_index is None:
            continue
        name = clean_inline(lines[heading_index])
        url_match = next((URL_RE.search(line) for line in lines if URL_RE.search(line)), None)
        url = clean_inline(url_match.group(0)) if url_match else ""
        bullets = tuple(
            Bullet(text=clean_inline(_strip_bullet_prefix(line)))
            for line in lines
            if BULLET_PREFIX_RE.match(line)
        )
        projects.append(Project(name=name, url=url, bullets=bullets))
    return tuple(projects)


def _extract_education(body: str) -> tuple[Education, ...]:
    education: list[Education] = []
    for block in _split_blocks(body):
        lines = _non_empty_lines(block)
        heading_index = _heading_index(lines)
        if heading_index is None:
            continue
        heading = lines[heading_index]
        degree, institution = _split_heading(heading)
        major = ""
        if "," in degree:
            degree, _, rest = degree.partition(",")
            if INSTITUTION_START_RE.match(rest.strip()):
                institution = rest.strip()
            else:
                major = rest.strip()
        _, end_date = _extract_dates(lines)
        graduation = end_date
        if not graduation:
            year_match = SINGLE_YEAR_RE.search(block)
            graduation = year_match.group(0) if year_match else ""
        gpa_match = GPA_RE.search(block)
        gpa = gpa_match.group(1) if gpa_match else None
        education.append(
            Education(
                institution=clean_inline(institution),
                location="",
                degree=clean_inline(degree),
                major=clean_inline(major),
                graduation=graduation,
                gpa=gpa,
            )
        )
    return tuple(education)


def _extract_awards(body: str) -> tuple[Award, ...]:
    awards: list[Award] = []
    for block in _split_blocks(body):
        lines = _non_empty_lines(block)
        heading_index = _heading_index(lines)
        if heading_index is None:
            continue
        heading = lines[heading_index]
        title, organization = _split_heading(heading)
        start_date, end_date = _extract_dates(lines)
        date = start_date or end_date
        if not date:
            year_match = SINGLE_YEAR_RE.search(organization)
            if year_match:
                date = year_match.group(0)
                organization = organization[: year_match.start()].rstrip(" ,-").strip()
        if not date:
            year_match = SINGLE_YEAR_RE.search(block)
            date = year_match.group(0) if year_match else ""
        description_lines = [
            clean_inline(_strip_bullet_prefix(line))
            for line in lines
            if BULLET_PREFIX_RE.match(line)
        ]
        awards.append(
            Award(
                title=clean_inline(title),
                organization=clean_inline(organization),
                date=date,
                description=" ".join(description_lines),
            )
        )
    return tuple(awards)


def _split_blocks(body: str) -> list[str]:
    return [block.strip() for block in re.split(r"\n\s*\n", body) if block.strip()]


def _non_empty_lines(block: str) -> list[str]:
    return [line.strip() for line in block.splitlines() if line.strip()]


def _heading_index(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if not BULLET_PREFIX_RE.match(line) and not DATE_RANGE_RE.search(line):
            return index
    return None


def _extract_dates(lines: list[str]) -> tuple[str, str]:
    for line in lines:
        match = DATE_RANGE_RE.search(line)
        if match:
            return clean_inline(match.group(1)), clean_inline(match.group(2))
    return "", ""


def _split_heading(heading: str) -> tuple[str, str]:
    match = HEADING_SEPARATOR_RE.search(heading)
    if match:
        return heading[: match.start()].strip(), heading[match.end() :].strip()
    return heading, ""


def _strip_bullet_prefix(line: str) -> str:
    return BULLET_PREFIX_RE.sub("", line)
