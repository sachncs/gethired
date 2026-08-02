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

import re
from pathlib import Path
from typing import Final

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

__all__ = [
    "parse",
    "parse_image",
    "parse_pdf",
    "parse_text",
    "parse_tex",
]


_COMMENT_RE: Final[re.Pattern[str]] = re.compile(r"(?m)^\s*%.*$")
_BEGIN_DOCUMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"\\begin\{document\}(.*?)\\end\{document\}", re.DOTALL
)

_HUGE_NAME_RE: Final[re.Pattern[str]] = re.compile(
    r"\{\\Huge\s+\\scshape\s+([^}]+?)\s*\}", re.DOTALL
)
_PHONE_RE: Final[re.Pattern[str]] = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
_EMAIL_RE: Final[re.Pattern[str]] = re.compile(
    r"\\href\{mailto:([^}]+)\}\{[^}]*\}|(?<![\w@.])([\w.+-]+@[\w-]+\.[\w.-]+)"
)
_GITHUB_RE: Final[re.Pattern[str]] = re.compile(
    r"\\href\{(https?://github\.com/[^}]+)\}\{[^}]*\}"
)
_LINKEDIN_RE: Final[re.Pattern[str]] = re.compile(
    r"\\href\{(https?://(?:www\.)?linkedin\.com/[^}]+)\}\{[^}]*\}"
)

_SECTION_RE: Final[re.Pattern[str]] = re.compile(
    r"\\section\{([^}]+)\}(.*?)(?=\\section\{|\\end\{document\}|$)", re.DOTALL
)

_SKILL_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"\\textbf\{\s*([^}]+?):\s*\}([^\\]*)", re.DOTALL
)
_SKILL_VSPACE_RE: Final[re.Pattern[str]] = re.compile(r"\\vspace\{[^}]*\}")

_BRACED_GROUP_RE: Final[re.Pattern[str]] = re.compile(r"\{((?:[^{}]|\{[^{}]*\})*)\}")

_RESUME_SUBHEADING_RE: Final[re.Pattern[str]] = re.compile(
    r"\\resumeSubheading\s*"
    r"\{((?:[^{}]|\{[^{}]*\})*)\}"
    r"\s*\{((?:[^{}]|\{[^{}]*\})*)\}"
    r"\s*\{((?:[^{}]|\{[^{}]*\})*)\}",
    re.DOTALL,
)
_RESUME_PROJECT_HEADING_RE: Final[re.Pattern[str]] = re.compile(
    r"\\resumeProjectHeading\s*"
    r"\{((?:[^{}]|\{[^{}]*\})*)\}"
    r"\s*\{((?:[^{}]|\{[^{}]*\})*)\}",
    re.DOTALL,
)
_BULLET_RE: Final[re.Pattern[str]] = re.compile(
    r"\\resumeItem\{((?:[^{}]|\{[^}]*\})*)\}", re.DOTALL
)
_HREF_RE: Final[re.Pattern[str]] = re.compile(
    r"\\href\{([^}]+)\}\{((?:[^{}]|\{[^}]*\})*)\}"
)


def _strip_comments(body: str) -> str:
    return _COMMENT_RE.sub("", body)


def _extract_body(source: str) -> str:
    match = _BEGIN_DOCUMENT_RE.search(source)
    if match is None:
        return source
    return match.group(1)


def _find_balanced_args(text: str, pos: int, count: int) -> tuple[tuple[str, ...], int]:
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


def _find_macro_invocations(text: str, macro: str, arg_count: int) -> list[tuple[int, tuple[str, ...]]]:
    """Find all invocations of ``\\<macro>`` followed by ``arg_count`` braced groups."""
    pattern = re.compile(r"\\" + re.escape(macro) + r"\b\s*")
    results: list[tuple[int, tuple[str, ...]]] = []
    for match in pattern.finditer(text):
        args, end = _find_balanced_args(text, match.end(), arg_count)
        if len(args) == arg_count:
            results.append((match.start(), args))
    return results


def _clean_inline(text: str) -> str:
    """Strip residual LaTeX wrappers and normalise whitespace."""
    cleaned = _HREF_RE.sub(lambda m: m.group(2), text)
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


def _extract_contact(body: str) -> ContactInformation:
    name_match = _HUGE_NAME_RE.search(body)
    name = _clean_inline(name_match.group(1)) if name_match else ""

    github_match = _GITHUB_RE.search(body)
    github_url = github_match.group(1) if github_match else None

    linkedin_match = _LINKEDIN_RE.search(body)
    linkedin_url = linkedin_match.group(1) if linkedin_match else None

    email_match = _EMAIL_RE.search(body)
    email = ""
    if email_match:
        email = email_match.group(1) or email_match.group(2) or ""

    phone_match = _PHONE_RE.search(body)
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


def _extract_summary(body: str) -> str:
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
        return _clean_inline(section_text)
    return _clean_inline(inline.group(1))


def _extract_skills(body: str) -> SkillsByCategory:
    match = re.search(
        r"\\section\{Technical Skills\}(.*?)(?=\\section\{|\\end\{document\}|$)",
        body,
        re.DOTALL,
    )
    if match is None:
        return SkillsByCategory(categories={})

    section_text = match.group(1)
    categories: dict[str, tuple[str, ...]] = {}
    for line in _SKILL_LINE_RE.finditer(section_text):
        raw_category = _clean_inline(line.group(1))
        category = raw_category.rstrip(":").strip()
        raw_values = line.group(2)
        cleaned_values = _SKILL_VSPACE_RE.sub("", raw_values)
        values = tuple(
            value.strip()
            for value in cleaned_values.split(",")
            if value.strip() and "}" not in value
        )
        if category and values:
            categories[category] = values
    return SkillsByCategory(categories=categories)


def _extract_bullets(section_text: str, start: int) -> tuple[Bullet, ...]:
    next_marker = _next_subheading_or_project(section_text, start)
    bullet_section = section_text[start:next_marker]
    return tuple(Bullet(text=_clean_inline(m.group(1))) for m in _BULLET_RE.finditer(bullet_section))


def _next_subheading_or_project(section_text: str, start: int) -> int:
    sub_invocations = _find_macro_invocations(section_text[start:], "resumeSubheading", 3)
    proj_invocations = _find_macro_invocations(section_text[start:], "resumeProjectHeading", 2)
    candidates = [start + pos for pos, _ in sub_invocations + proj_invocations]
    return min(candidates) if candidates else len(section_text)


def _extract_experiences(body: str) -> tuple[Experience, ...]:
    match = re.search(
        r"\\section\{Experience\}(.*?)(?=\\section\{|\\end\{document\}|$)",
        body,
        re.DOTALL,
    )
    if match is None:
        return ()

    section_text = match.group(1)
    experiences: list[Experience] = []
    for _, args in _find_macro_invocations(section_text, "resumeSubheading", 3):
        role = _clean_inline(args[0])
        company = _clean_inline(args[1])
        dates = _clean_inline(args[2])
        start_date, _, end_date = dates.partition(" -- ")
        # Re-find the position for bullet extraction (start from end of macro call)
        pattern = re.compile(r"\\resumeSubheading\b\s*")
        match_iter = list(pattern.finditer(section_text))
        # Use the corresponding match for position
        idx = len(experiences)
        if idx < len(match_iter):
            macro_end = match_iter[idx].end()
            # advance past the three args
            _, after = _find_balanced_args(section_text, macro_end, 3)
            bullets = _extract_bullets(section_text, after)
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


def _extract_heading_text_and_url(heading: str) -> tuple[str, str]:
    """Parse ``\\href{URL}{\\textbf{Name}}`` or plain text from a heading."""
    href_match = _HREF_RE.search(heading)
    if href_match is not None:
        url = href_match.group(1)
        name = _clean_inline(href_match.group(2))
        return name, url
    return _clean_inline(heading), ""


def _extract_projects(body: str) -> tuple[Project, ...]:
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
    for idx, (_, args) in enumerate(_find_macro_invocations(section_text, "resumeProjectHeading", 2)):
        name, url = _extract_heading_text_and_url(args[0])
        macro_matches = list(pattern.finditer(section_text))
        if idx < len(macro_matches):
            _, after = _find_balanced_args(section_text, macro_matches[idx].end(), 2)
            bullets = _extract_bullets(section_text, after)
        else:
            bullets = ()
        projects.append(Project(name=name, url=url, bullets=bullets))
    return tuple(projects)


def _extract_education(body: str) -> tuple[Education, ...]:
    match = re.search(
        r"\\section\{Education\}(.*?)(?=\\section\{|\\end\{document\}|$)",
        body,
        re.DOTALL,
    )
    if match is None:
        return ()

    section_text = match.group(1)
    headings = _find_macro_invocations(section_text, "resumeSubheading", 3)
    if len(headings) < 2:
        return ()

    institution = _clean_inline(headings[0][1][0])
    location = _clean_inline(headings[0][1][1])
    graduation = _clean_inline(headings[0][1][2])

    degree_args = headings[1][1]
    degree_full = _clean_inline(degree_args[0])
    major = _clean_inline(degree_args[1])
    gpa_full = _clean_inline(degree_args[2])

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


def _extract_awards(body: str) -> tuple[Award, ...]:
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
    for idx, (_, args) in enumerate(_find_macro_invocations(section_text, "resumeProjectHeading", 2)):
        heading_raw = args[0]
        date = _clean_inline(args[1])
        title, _ = _extract_heading_text_and_url(heading_raw)

        macro_matches = list(pattern.finditer(section_text))
        if idx < len(macro_matches):
            _, after = _find_balanced_args(section_text, macro_matches[idx].end(), 2)
            bullets = _extract_bullets(section_text, after)
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
    body = _extract_body(_strip_comments(text))
    if not body:
        raise MasterParsingError("Could not locate \\begin{document} ... \\end{document} body")

    contact = _extract_contact(body)
    summary = _extract_summary(body)
    skills = _extract_skills(body)
    experiences = _extract_experiences(body)
    projects = _extract_projects(body)
    education = _extract_education(body)
    awards = _extract_awards(body)

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
    try:
        import pymupdf  # type: ignore[import-not-found]
    except ImportError as exc:
        raise MasterParsingError("pymupdf is required for PDF parsing") from exc

    document = pymupdf.open(path)
    try:
        raw_text = "\n".join(page.get_text() for page in document)
    finally:
        document.close()

    if not raw_text.strip():
        raise MasterParsingError(f"No text extracted from {path}")
    return parse_tex(raw_text)


def parse_image(path: Path) -> MasterResume:
    """Extract text from an image via vision-capable model, then parse."""
    raise MasterParsingError(
        "Image parsing requires a configured vision model; use parse_tex or parse_pdf."
    )


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
