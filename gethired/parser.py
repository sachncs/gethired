"""Parser for the master resume.

Supports four input formats, all yielding the same ``MasterResume``:

* ``parse_tex(text)`` — deterministic TeX parser for the existing resume style
* ``parse_text(text)`` — plain-text fallback
* ``parse_pdf(path)`` — extracts text via PyMuPDF, then routes through TeX-style parser
* ``parse_image(path)`` — uses a vision-capable model to extract text, then parses

The TeX parser handles the macros in the existing resume (``\\resumeSubheading``,
``\\resumeItem``, ``\\resumeProjectHeading``, ``\\href``, ``\\textbf``, ``R\\&D``,
``$O(1)$``).
"""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Final

import pymupdf
from pydantic_ai import Agent

from gethired.exceptions import MasterParsingError
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
from gethired.provider import resolve_model

__all__ = [
    "parse",
    "parse_image",
    "parse_pdf",
    "parse_text",
    "parse_tex",
]


COMMENT_RE: Final[re.Pattern[str]] = re.compile(r"(?m)^\s*%.*$")
BEGIN_DOCUMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"\\begin\{document\}(.*?)\\end\{document\}", re.DOTALL
)

HUGE_NAME_RE: Final[re.Pattern[str]] = re.compile(
    r"\{\\Huge\s+\\scshape\s+([^}]+?)\s*\}", re.DOTALL
)
PHONE_RE: Final[re.Pattern[str]] = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
EMAIL_RE: Final[re.Pattern[str]] = re.compile(
    r"\\href\{mailto:([^}]+)\}\{[^}]*\}|(?<![\w@.])([\w.+-]+@[\w-]+\.[\w.-]+)"
)
GITHUB_RE: Final[re.Pattern[str]] = re.compile(
    r"\\href\{(https?://github\.com/[^}]+)\}\{[^}]*\}"
)
LINKEDIN_RE: Final[re.Pattern[str]] = re.compile(
    r"\\href\{(https?://(?:www\.)?linkedin\.com/[^}]+)\}\{[^}]*\}"
)

SECTION_RE: Final[re.Pattern[str]] = re.compile(
    r"\\section\{([^}]+)\}(.*?)(?=\\section\{|\\end\{document\}|$)", re.DOTALL
)

SKILL_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"\\textbf\{\s*([^}]+?):\s*\}([^\\]*)", re.DOTALL
)
SKILL_VSPACE_RE: Final[re.Pattern[str]] = re.compile(r"\\vspace\{[^}]*\}")

BRACED_GROUP_RE: Final[re.Pattern[str]] = re.compile(r"\{((?:[^{}]|\{[^{}]*\})*)\}")

RESUME_SUBHEADING_RE: Final[re.Pattern[str]] = re.compile(
    r"\\resumeSubheading\s*"
    r"\{((?:[^{}]|\{[^{}]*\})*)\}"
    r"\s*\{((?:[^{}]|\{[^{}]*\})*)\}"
    r"\s*\{((?:[^{}]|\{[^{}]*\})*)\}",
    re.DOTALL,
)
RESUME_PROJECT_HEADING_RE: Final[re.Pattern[str]] = re.compile(
    r"\\resumeProjectHeading\s*"
    r"\{((?:[^{}]|\{[^{}]*\})*)\}"
    r"\s*\{((?:[^{}]|\{[^{}]*\})*)\}",
    re.DOTALL,
)
BULLET_RE: Final[re.Pattern[str]] = re.compile(
    r"\\resumeItem\{((?:[^{}]|\{[^}]*\})*)\}", re.DOTALL
)
HREF_RE: Final[re.Pattern[str]] = re.compile(
    r"\\href\{([^}]+)\}\{((?:[^{}]|\{[^}]*\})*)\}"
)


def strip_comments(body: str) -> str:
    return COMMENT_RE.sub("", body)


def extract_body(source: str) -> str:
    match = BEGIN_DOCUMENT_RE.search(source)
    if match is None:
        return source
    return match.group(1)


def find_balanced_args(text: str, pos: int, count: int) -> tuple[tuple[str, ...], int]:
    """Consume ``count`` brace-delimited argument groups starting at ``pos``.

    Returns the contents of each group and the position after the last group.
    """
    args: list[str] = []
    for _ in range(count):
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text) or text[pos] != "{":
            break
        depth = 0
        start = pos
        pos += 1
        while pos < len(text):
            char = text[pos]
            if char == "{":
                depth += 1
            elif char == "}":
                if depth == 0:
                    args.append(text[start + 1 : pos])
                    pos += 1
                    break
                depth -= 1
            pos += 1
        else:
            break
    return tuple(args), pos


def find_macro_invocations(
    text: str, macro: str, arg_count: int
) -> list[tuple[int, tuple[str, ...]]]:
    """Find all invocations of ``\\<macro>`` followed by ``arg_count`` braced groups."""
    pattern = re.compile(r"\\" + re.escape(macro) + r"\b\s*")
    results: list[tuple[int, tuple[str, ...]]] = []
    for match in pattern.finditer(text):
        args, end = find_balanced_args(text, match.end(), arg_count)
        if len(args) == arg_count:
            results.append((match.start(), args))
    return results


def clean_inline(text: str) -> str:
    """Strip residual LaTeX wrappers and normalise whitespace."""
    cleaned = HREF_RE.sub(lambda m: m.group(2), text)
    cleaned = re.sub(r"\\textbf\{([^}]*)\}", r"\1", cleaned)
    cleaned = re.sub(r"\\textsc\{([^}]*)\}", r"\1", cleaned)
    cleaned = re.sub(r"\\emph\{([^}]*)\}", r"\1", cleaned)
    cleaned = re.sub(r"\$([^$]*)\$", r"\1", cleaned)
    cleaned = re.sub(r"\\&", "&", cleaned)
    cleaned = re.sub(r"\\([\"%$#_{}~^])", r"\1", cleaned)
    cleaned = re.sub(r'\\"', '"', cleaned)
    cleaned = re.sub(r"\\vspace\{[^}]*\}", "", cleaned)
    cleaned = re.sub(r"\\,", " ", cleaned)
    cleaned = re.sub(r"\\cdot", "·", cleaned)
    cleaned = re.sub(r"~", " ", cleaned)
    cleaned = re.sub(r"\\\\", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def extract_contact(body: str) -> ContactInformation:
    name_match = HUGE_NAME_RE.search(body)
    name = clean_inline(name_match.group(1)) if name_match else ""

    github_match = GITHUB_RE.search(body)
    github_url = github_match.group(1) if github_match else None

    linkedin_match = LINKEDIN_RE.search(body)
    linkedin_url = linkedin_match.group(1) if linkedin_match else None

    email_match = EMAIL_RE.search(body)
    email = ""
    if email_match:
        email = email_match.group(1) or email_match.group(2) or ""

    phone_match = PHONE_RE.search(body)
    phone = phone_match.group(1).strip() if phone_match else ""

    city_match = re.search(r"\\small\s+([A-Za-z][A-Za-z .'-]*?)\s*\$\\cdot\$", body)
    city = city_match.group(1).strip() if city_match else ""

    return ContactInformation(
        name=name,
        city=city,
        phone=phone,
        email=email,
        github_url=github_url,
        linkedin_url=linkedin_url,
    )


def extract_summary(body: str) -> str:
    match = re.search(
        r"\\section\{Summary\}(.*?)(?=\\section\{|\\end\{document\}|$)",
        body,
        re.DOTALL,
    )
    if match is None:
        return ""
    section_text = match.group(1)
    inline = re.search(r"\{\\small\s+(.*?)\}", section_text, re.DOTALL)
    if inline is None:
        return clean_inline(section_text)
    return clean_inline(inline.group(1))


def extract_skills(body: str) -> SkillsByCategory:
    match = re.search(
        r"\\section\{Technical Skills\}(.*?)(?=\\section\{|\\end\{document\}|$)",
        body,
        re.DOTALL,
    )
    if match is None:
        return SkillsByCategory(categories={})

    section_text = match.group(1)
    categories: dict[str, tuple[str, ...]] = {}
    for line in SKILL_LINE_RE.finditer(section_text):
        raw_category = clean_inline(line.group(1))
        category = raw_category.rstrip(":").strip()
        raw_values = line.group(2)
        cleaned_values = SKILL_VSPACE_RE.sub("", raw_values)
        values = tuple(
            value.strip()
            for value in cleaned_values.split(",")
            if value.strip() and "}" not in value
        )
        if category and values:
            categories[category] = values
    return SkillsByCategory(categories=categories)


def extract_bullets(section_text: str, start: int) -> tuple[Bullet, ...]:
    next_marker = next_subheading_or_project(section_text, start)
    bullet_section = section_text[start:next_marker]
    return tuple(Bullet(text=clean_inline(m.group(1))) for m in BULLET_RE.finditer(bullet_section))


def next_subheading_or_project(section_text: str, start: int) -> int:
    sub_invocations = find_macro_invocations(section_text[start:], "resumeSubheading", 3)
    proj_invocations = find_macro_invocations(section_text[start:], "resumeProjectHeading", 2)
    candidates = [start + pos for pos, _ in sub_invocations + proj_invocations]
    return min(candidates) if candidates else len(section_text)


def extract_experiences(body: str) -> tuple[Experience, ...]:
    match = re.search(
        r"\\section\{Experience\}(.*?)(?=\\section\{|\\end\{document\}|$)",
        body,
        re.DOTALL,
    )
    if match is None:
        return ()

    section_text = match.group(1)
    experiences: list[Experience] = []
    for _, args in find_macro_invocations(section_text, "resumeSubheading", 3):
        role = clean_inline(args[0])
        company = clean_inline(args[1])
        dates = clean_inline(args[2])
        start_date, _, end_date = dates.partition(" -- ")
        # Re-find the position for bullet extraction (start from end of macro call)
        pattern = re.compile(r"\\resumeSubheading\b\s*")
        match_iter = list(pattern.finditer(section_text))
        # Use the corresponding match for position
        idx = len(experiences)
        if idx < len(match_iter):
            macro_end = match_iter[idx].end()
            # advance past the three args
            _, after = find_balanced_args(section_text, macro_end, 3)
            bullets = extract_bullets(section_text, after)
        else:
            bullets = ()
        experiences.append(
            Experience(
                role=role,
                company=company,
                start_date=start_date.strip(),
                end_date=end_date.strip(),
                bullets=bullets,
            )
        )
    return tuple(experiences)


def extract_heading_text_and_url(heading: str) -> tuple[str, str]:
    """Parse ``\\href{URL}{\\textbf{Name}}`` or plain text from a heading."""
    href_match = HREF_RE.search(heading)
    if href_match is not None:
        url = href_match.group(1)
        name = clean_inline(href_match.group(2))
        return name, url
    return clean_inline(heading), ""


def extract_projects(body: str) -> tuple[Project, ...]:
    match = re.search(
        r"\\section\{Selected Projects\}(.*?)(?=\\section\{|\\end\{document\}|$)",
        body,
        re.DOTALL,
    )
    if match is None:
        return ()

    section_text = match.group(1)
    projects: list[Project] = []
    pattern = re.compile(r"\\resumeProjectHeading\b\s*")
    for idx, (_, args) in enumerate(
        find_macro_invocations(section_text, "resumeProjectHeading", 2)
    ):
        name, url = extract_heading_text_and_url(args[0])
        macro_matches = list(pattern.finditer(section_text))
        if idx < len(macro_matches):
            _, after = find_balanced_args(section_text, macro_matches[idx].end(), 2)
            bullets = extract_bullets(section_text, after)
        else:
            bullets = ()
        projects.append(Project(name=name, url=url, bullets=bullets))
    return tuple(projects)


def extract_education(body: str) -> tuple[Education, ...]:
    match = re.search(
        r"\\section\{Education\}(.*?)(?=\\section\{|\\end\{document\}|$)",
        body,
        re.DOTALL,
    )
    if match is None:
        return ()

    section_text = match.group(1)
    headings = find_macro_invocations(section_text, "resumeSubheading", 3)
    if len(headings) < 2:
        return ()

    institution = clean_inline(headings[0][1][0])
    location = clean_inline(headings[0][1][1])
    graduation = clean_inline(headings[0][1][2])

    degree_args = headings[1][1]
    degree_full = clean_inline(degree_args[0])
    major = clean_inline(degree_args[1])
    gpa_full = clean_inline(degree_args[2])

    gpa: str | None = None
    gpa_match = re.match(r"CGPA:\s*(\S+)", gpa_full)
    if gpa_match:
        gpa = gpa_match.group(1)

    return (
        Education(
            institution=institution,
            location=location,
            degree=degree_full,
            major=major,
            graduation=graduation,
            gpa=gpa,
        ),
    )


def extract_awards(body: str) -> tuple[Award, ...]:
    match = re.search(
        r"\\section\{Awards\s*(?:\\&|&|and)\s*Recognition\}(.*?)(?=\\section\{|\\end\{document\}|$)",
        body,
        re.DOTALL,
    )
    if match is None:
        return ()

    section_text = match.group(1)
    awards: list[Award] = []
    pattern = re.compile(r"\\resumeProjectHeading\b\s*")
    for idx, (_, args) in enumerate(
        find_macro_invocations(section_text, "resumeProjectHeading", 2)
    ):
        heading_raw = args[0]
        date = clean_inline(args[1])
        title, _ = extract_heading_text_and_url(heading_raw)

        macro_matches = list(pattern.finditer(section_text))
        if idx < len(macro_matches):
            _, after = find_balanced_args(section_text, macro_matches[idx].end(), 2)
            bullets = extract_bullets(section_text, after)
        else:
            bullets = ()
        description = bullets[0].text if bullets else ""
        organization = ""
        organisation_match = re.match(r"(.+?)\s+---\s+(.+)$", title)
        if organisation_match is not None:
            organization = organisation_match.group(1).strip()
            title = organisation_match.group(2).strip()
        awards.append(
            Award(
                title=title,
                organization=organization,
                date=date,
                description=description,
            )
        )
    return tuple(awards)


def parse_tex(source: str | Path) -> MasterResume:
    """Parse a TeX source resume into a ``MasterResume``.

    Args:
        source: Either the raw TeX text or a path to a ``.tex`` file.

    Returns:
        The parsed ``MasterResume``.

    Raises:
        MasterParsingError: If the source cannot be parsed into a resume.
    """
    try:
        if isinstance(source, Path):
            text = source.read_text()
        elif "\\documentclass" in source or "\\begin{document}" in source:
            text = source
        else:
            candidate = Path(source)
            text = candidate.read_text() if candidate.exists() else source
    except FileNotFoundError as exc:
        raise MasterParsingError(f"TeX source not found: {source}") from exc
    body = extract_body(strip_comments(text))
    if not body:
        raise MasterParsingError("Could not locate \\begin{document} ... \\end{document} body")

    contact = extract_contact(body)
    summary = extract_summary(body)
    skills = extract_skills(body)
    experiences = extract_experiences(body)
    projects = extract_projects(body)
    education = extract_education(body)
    awards = extract_awards(body)

    return MasterResume(
        contact=contact,
        summary=summary,
        skills=skills,
        experiences=experiences,
        projects=projects,
        education=education,
        awards=awards,
    )


def parse_text(text: str) -> MasterResume:
    """Parse a plain-text resume.

    Falls through to ``parse_tex`` when the text contains TeX markers.
    """
    if "\\documentclass" in text or "\\begin{document}" in text:
        return parse_tex(text)
    raise MasterParsingError(
        "Plain-text resume parsing not yet implemented; provide .tex source."
    )


def parse_pdf(path: Path) -> MasterResume:
    """Extract text from a PDF and route through the TeX-style parser."""
    with pymupdf.open(path) as document:
        raw_text = "\n".join(
            document[i].get_text() for i in range(len(document))
        )

    if not raw_text.strip():
        raise MasterParsingError(f"No text extracted from {path}")
    return parse_tex(raw_text)


def parse_image(path: Path) -> MasterResume:
    """Extract text from an image via a vision-capable model.

    Requires a multimodal model identifier in ``IMAGE_MODEL`` (or the same
    value as ``MODEL``). Reads the file at ``path``, sends it to the vision
    model, and pipes the extracted text through the TeX parser.

    Args:
        path: Path to the image file (PNG, JPEG, WEBP, PDF-as-image).

    Returns:
        The parsed ``MasterResume``.

    Raises:
        MasterParsingError: If the file is missing or the model returns no text.
    """
    if not path.exists():
        raise MasterParsingError(f"Image not found: {path}")

    image_model = os.environ.get("IMAGE_MODEL") or os.environ.get("MODEL", "")
    if not image_model:
        raise MasterParsingError(
            "Image parsing requires IMAGE_MODEL or MODEL env var pointing "
            "to a multimodal model."
        )
    resolved = resolve_model(image_model)

    agent: Agent[None, str] = Agent(
        resolved.model,
        system_prompt=(
            "Extract every section, bullet, employer, role, date, project, "
            "and skill from the resume image as plain TeX-flavored text. "
            "Preserve \\resumeSubheading and \\resumeItem structure where possible."
        ),
        output_type=str,
    )
    image_bytes = path.read_bytes()
    prompt = (
        "Extract the resume text from this image. "
        "Return plain LaTeX-flavored text ready for the TeX parser."
    )
    try:
        extracted = asyncio.run(agent.run(prompt, images=[image_bytes]))
        raw_text = extracted.output
    except Exception as exc:
        raise MasterParsingError(
            f"Vision model extraction failed for {path}: {exc}"
        ) from exc

    if not raw_text or not raw_text.strip():
        raise MasterParsingError(f"No text extracted from image {path}")
    return parse_tex(raw_text)


def parse(source: str | Path) -> MasterResume:
    """Route to the appropriate parser based on file extension."""
    path = Path(source)
    if not path.exists():
        return parse_tex(source)

    suffix = path.suffix.lower()
    if suffix == ".tex":
        return parse_tex(path)
    if suffix == ".pdf":
        return parse_pdf(path)
    if suffix in {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}:
        return parse_image(path)
    return parse_tex(path.read_text())
