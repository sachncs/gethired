"""Parser for the master resume.

Supports four input formats, all yielding the same ``Master``:

* ``tex(text)`` — deterministic TeX parser for the existing resume style
* ``text(text)`` — plain-text fallback
* ``pdf(path)`` — extracts text via PyMuPDF, then routes through TeX-style parser
* ``image(path)`` — uses a vision-capable model to extract text, then parses

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
from pydantic_ai import Agent, BinaryContent

from gethired.exceptions import ParseError
from gethired.models import (
    Award,
    Bullet,
    Contact,
    Education,
    Experience,
    Master,
    Project,
    Skills,
)
from gethired.plain_text import parse_plain_text as plain
from gethired.provider import resolve_model
from gethired.text_util import (
    EMAIL_RE,
    GITHUB_BARE_RE,
    GITHUB_RE,
    HREF_RE,
    LINKEDIN_BARE_RE,
    LINKEDIN_RE,
    PHONE_RE,
    clean,
    require_contact,
)

__all__ = [
    "parse",
    "image",
    "pdf",
    "text",
    "tex",
]


COMMENT_RE: Final[re.Pattern[str]] = re.compile(r"(?m)^\s*%.*$")
BEGIN_DOCUMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"\\begin\{document\}(.*?)\\end\{document\}", re.DOTALL
)

HUGE_NAME_RE: Final[re.Pattern[str]] = re.compile(
    r"\{\\Huge\s+\\scshape\s+([^}]+?)\s*\}", re.DOTALL
)

SECTION_RE: Final[re.Pattern[str]] = re.compile(
    r"\\section\{([^}]+)\}(.*?)(?=\\section\{|\\end\{document\}|$)", re.DOTALL
)

SKILL_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"\\textbf\{\s*([^}]+?):\s*\}((?:(?!\\textbf\{|\\end\{).)*)",
    re.DOTALL,
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
BULLET_RE: Final[re.Pattern[str]] = re.compile(r"\\resumeItem\{((?:[^{}]|\{[^}]*\})*)\}", re.DOTALL)


def strip_comments(body: str) -> str:
    return COMMENT_RE.sub("", body)


def extract_body(source: str) -> str:
    match = BEGIN_DOCUMENT_RE.search(source)
    if match is None:
        raise ParseError("Could not locate \\begin{document} ... \\end{document} body")
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


def extract_contact(body: str) -> Contact:
    name_match = HUGE_NAME_RE.search(body)
    name = clean(name_match.group(1)) if name_match else ""

    github_match = GITHUB_RE.search(body)
    if github_match is None:
        bare_github = GITHUB_BARE_RE.search(body)
        github_url = bare_github.group(0) if bare_github else None
    else:
        github_url = github_match.group(1)

    linkedin_match = LINKEDIN_RE.search(body)
    if linkedin_match is None:
        bare_linkedin = LINKEDIN_BARE_RE.search(body)
        linkedin_url = bare_linkedin.group(0) if bare_linkedin else None
    else:
        linkedin_url = linkedin_match.group(1)

    email_match = EMAIL_RE.search(body)
    email = ""
    if email_match:
        email = email_match.group(1) or email_match.group(2) or ""

    phone_match = PHONE_RE.search(body)
    phone = phone_match.group(1).strip() if phone_match else ""

    city_match = re.search(
        r"\\small\s+([A-Za-z](?:[A-Za-z .'-]|\\[`'^~=.][A-Za-z])*?)\s*\$\\cdot\$",
        body,
    )
    city = clean(city_match.group(1)) if city_match else ""

    require_contact(name, city, phone, email)

    return Contact(
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
        return clean(section_text)
    return clean(inline.group(1))


def extract_skills(body: str) -> Skills:
    match = re.search(
        r"\\section\{Technical Skills\}(.*?)(?=\\section\{|\\end\{document\}|$)",
        body,
        re.DOTALL,
    )
    if match is None:
        return Skills(categories={})

    section_text = match.group(1)
    categories: dict[str, tuple[str, ...]] = {}
    for line in SKILL_LINE_RE.finditer(section_text):
        raw_category = clean(line.group(1))
        category = raw_category.rstrip(":").strip()
        raw_values = SKILL_VSPACE_RE.sub("", line.group(2))
        values = tuple(value for raw_value in raw_values.split(",") if (value := clean(raw_value)))
        if category and values:
            categories[category] = values
    return Skills(categories=categories)


def extract_bullets(section_text: str, start: int) -> tuple[Bullet, ...]:
    next_idx = next_subheading_or_project(section_text, start)
    bullet_section = section_text[start:next_idx]
    return tuple(Bullet(text=clean(m.group(1))) for m in BULLET_RE.finditer(bullet_section))


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
        role = clean(args[0])
        company = clean(args[1])
        dates = clean(args[2])
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
            section_bullets = extract_bullets(section_text, after)
        else:
            section_bullets = ()
        experiences.append(
            Experience(
                role=role,
                company=company,
                start_date=start_date.strip(),
                end_date=end_date.strip(),
                bullets=section_bullets,
            )
        )
    return tuple(experiences)


def extract_heading_text_and_url(heading: str) -> tuple[str, str]:
    """Parse ``\\href{URL}{\\textbf{Name}}`` or plain text from a heading."""
    href_match = HREF_RE.search(heading)
    if href_match is not None:
        url = href_match.group(1)
        name = clean(href_match.group(2))
        return name, url
    return clean(heading), ""


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
            section_bullets = extract_bullets(section_text, after)
        else:
            section_bullets = ()
        projects.append(Project(name=name, url=url, bullets=section_bullets))
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

    education: list[Education] = []
    for index in range(0, len(headings) - 1, 2):
        institution_args = headings[index][1]
        degree_args = headings[index + 1][1]

        gpa_full = clean(degree_args[2])
        gpa: str | None = None
        gpa_match = re.match(r"CGPA:\s*(\S+)", gpa_full)
        if gpa_match:
            gpa = gpa_match.group(1)

        education.append(
            Education(
                institution=clean(institution_args[0]),
                location=clean(institution_args[1]),
                graduation=clean(institution_args[2]),
                degree=clean(degree_args[0]),
                major=clean(degree_args[1]),
                gpa=gpa,
            )
        )

    return tuple(education)


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
        date = clean(args[1])
        title, _ = extract_heading_text_and_url(heading_raw)

        macro_matches = list(pattern.finditer(section_text))
        if idx < len(macro_matches):
            _, after = find_balanced_args(section_text, macro_matches[idx].end(), 2)
            section_bullets = extract_bullets(section_text, after)
        else:
            section_bullets = ()
        description = section_bullets[0].text if section_bullets else ""
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


def tex(source: str | Path) -> Master:
    """Parse a TeX source resume into a ``Master``.

    Args:
        source: Either the raw TeX text or a path to a ``.tex`` file.

    Returns:
        The parsed ``Master``.

    Raises:
        ParseError: If the source cannot be parsed into a resume.
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
        raise ParseError(f"TeX source not found: {source}") from exc
    body_text = extract_body(strip_comments(text))
    if not body_text.strip():
        raise ParseError("Could not locate \\begin{document} ... \\end{document} body")

    contact_info = extract_contact(body_text)
    summary_text = extract_summary(body_text)
    skills_data = extract_skills(body_text)
    experience_data = extract_experiences(body_text)
    project_data = extract_projects(body_text)
    education_data = extract_education(body_text)
    award_data = extract_awards(body_text)

    return Master(
        contact=contact_info,
        summary=summary_text,
        skills=skills_data,
        experiences=experience_data,
        projects=project_data,
        education=education_data,
        awards=award_data,
    )


def text(text: str) -> Master:
    """Parse a plain-text resume into a ``Master``.

    Routes to ``tex`` when the text contains TeX markers. Otherwise
    the text is parsed as a plain-text resume: the contact block is
    mandatory (same fail-fast error as ``contact``) and every other
    section is extracted best-effort.

    Args:
        text: Plain-text resume content.

    Returns:
        The parsed ``Master``.

    Raises:
        ParseError: When a required contact field is missing.
    """
    if "\\documentclass" in text or "\\begin{document}" in text:
        return tex(text)
    return plain(text)


def pdf(path: Path) -> Master:
    """Extract text from a PDF and route through the TeX-style parser."""
    with pymupdf.open(path) as document:
        raw_text = "\n".join(document[i].get_text() for i in range(len(document)))

    if not raw_text.strip():
        raise ParseError(f"No text extracted from {path}")
    return tex(raw_text)


def image(path: Path) -> Master:
    """Extract text from an image via a vision-capable model.

    Requires a multimodal model identifier in ``IMAGE_MODEL`` (or the same
    value as ``MODEL``). Reads the file at ``path``, sends it to the vision
    model, and pipes the extracted text through the TeX parser.

    Args:
        path: Path to the image file (PNG, JPEG, WEBP, PDF-as-image).

    Returns:
        The parsed ``Master``.

    Raises:
        ParseError: If the file is missing or the model returns no text.
    """
    if not path.exists():
        raise ParseError(f"Image not found: {path}")

    image_model = os.environ.get("IMAGE_MODEL") or os.environ.get("MODEL", "")
    if not image_model:
        raise ParseError(
            "Image parsing requires IMAGE_MODEL or MODEL env var pointing to a multimodal model."
        )
    resolved = resolve_model(image_model)

    agent: Agent[None, str] = Agent(  # type: ignore[call-overload]
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
        extracted = asyncio.run(
            agent.run([prompt, BinaryContent(data=image_bytes, media_type="image/png")])
        )
        raw_text = extracted.output
    except Exception as exc:
        raise ParseError(f"Vision model extraction failed for {path}: {exc}") from exc

    if not raw_text or not raw_text.strip():
        raise ParseError(f"No text extracted from image {path}")
    return tex(raw_text)


def dispatch(source: str | Path) -> Master:
    """Route to the appropriate parser based on file extension.

    Detects whether ``source`` is a file path (by attempting ``Path.exists()``
    cheaply) or raw text. For raw text without a TeX preamble, the plain-text
    parser is used.
    """
    if isinstance(source, Path):
        path = source
    else:
        path = Path(source)
        # Skip path checks for long strings (likely resume text, not a path)
        if len(source) > 4096 or "\n" in source:
            return tex(source)
        if not path.exists():
            return tex(source)

    suffix = path.suffix.lower()
    if suffix == ".tex":
        return tex(path)
    if suffix == ".pdf":
        return pdf(path)
    if suffix in {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}:
        return image(path)
    return tex(path.read_text())


# Backward-compat alias.
parse = dispatch


# Backward-compat aliases for the original public parser function names.
parse_tex = tex
parse_text = text
parse_pdf = pdf
parse_image = image
parse = lambda source: __dispatch(source)


def __dispatch(source: str | Path) -> Master:
    """Backwards-compatible dispatcher; prefer :func:`dispatch`."""
    if isinstance(source, str) and "\\" in source:
        return tex(source)
    path = Path(source)
    if path.exists():
        suffix = path.suffix.lower()
        if suffix == ".tex":
            return tex(path)
        if suffix == ".pdf":
            return pdf(path)
        if suffix in {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}:
            return image(path)
    return plain(str(source))


__all__ = [
    "tex",
    "text",
    "pdf",
    "image",
    "dispatch",
    "parse_tex",
    "parse_text",
    "parse_pdf",
    "parse_image",
    "parse",
    "extract_body",
    "find_balanced_args",
    "find_macro_invocations",
    "extract_contact",
    "extract_summary",
    "extract_skills",
    "extract_bullets",
    "next_subheading_or_project",
    "extract_experiences",
    "extract_heading_text_and_url",
    "extract_projects",
    "extract_education",
    "extract_awards",
    "strip_comments",
    "plain",
]
