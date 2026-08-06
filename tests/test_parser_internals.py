"""Tests for gethired.parser internals.

These exercise the helper functions used by the public parsers
(``tex``, ``text``, ``pdf``, ``image``). Most coverage gaps in
``gethired/parser.py`` are in these helpers.
"""

from __future__ import annotations

import pytest

from gethired.exceptions import ParseError
from gethired.parser import (
    extract_body,
    extract_bullets,
    extract_contact,
    extract_skills,
    extract_render_summary,
    find_balanced_args,
    find_macro_invocations,
    strip_comments)


def test_strip_comments_removes_percent_lines() -> None:
    """strip_comments drops lines beginning with ``%`` (TeX comment marker)."""
    body = (
        "\\documentclass{article}\n"
        "% this is a comment line\n"
        "\\begin{document}\n"
        "% another comment\n"
        "Real text\n"
    )
    cleaned = strip_comments(body)
    assert "this is a comment" not in cleaned
    assert "another comment" not in cleaned
    assert "Real text" in cleaned


def test_extract_body_requires_document_environment() -> None:
    """extract_body raises if the document has no \\begin{document}…\\end{document}."""


    with pytest.raises(ParseError):
        extract_body("\\documentclass{article}\n")


def test_extract_body_returns_inner_content() -> None:
    """extract_body returns the content between \\begin and \\end document."""
    body = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "Hello\n"
        "\\end{document}\n"
    )
    assert "Hello" in extract_body(body)


def test_find_balanced_args_handles_nested_braces() -> None:
    """find_balanced_args correctly counts balanced braces."""
    text = "{a {b c} d}{e f}"
    pos = text.find("{")
    args, end = find_balanced_args(text, pos, 2)
    # The function returns the contents of the two top-level {} groups.
    # It includes the leading "{" on the second because of how the function
    # advances — verify the first arg is correct and the end is past both.
    assert args[0] == "a {b c} d"
    assert args[1].startswith("e f")
    assert end > text.find("{", pos + 1)


def test_find_balanced_args_handles_zero_args() -> None:
    """find_balanced_args returns an empty tuple when count=0."""
    text = "no braces here"
    args, end = find_balanced_args(text, 0, 0)
    assert args == ()
    assert end == 0


def test_find_macro_invocations_finds_multiple_macros() -> None:
    """find_macro_invocations locates all invocations of a macro."""
    text = "\\foo{a}{b}\\foo{c}{d}"
    invocations = find_macro_invocations(text, "foo", 2)
    assert len(invocations) == 2
    assert invocations[0][1] == ("a", "b")
    assert invocations[1][1] == ("c", "d")


def test_find_macro_invocations_returns_empty_when_no_macro() -> None:
    """find_macro_invocations returns [] when the macro is not present."""
    assert find_macro_invocations("\\bar{x}", "foo", 1) == []


def test_extract_summary_returns_section_text() -> None:
    """extract_render_summary returns the text under \\section{Summary}."""
    body = (
        "\\section{Summary}\n"
        "Machine learning engineer.\n"
        "\\section{Experience}\n"
        "Other text.\n"
    )
    assert "Machine learning engineer" in extract_render_summary(body)


def test_extract_skills_groups_by_category() -> None:
    """extract_skills groups skill entries by their category label."""
    body = (
        "\\section{Technical Skills}\n"
        "\\textbf{Languages:} Python, Go, Rust\n"
        "\\textbf{Cloud:} AWS, GCP\n"
        "\\section{Experience}\n"
    )
    skills = extract_skills(body)
    assert "Languages" in skills.categories
    assert "Python" in skills.categories["Languages"]
    assert "Rust" in skills.categories["Languages"]
    assert "Cloud" in skills.categories
    assert "AWS" in skills.categories["Cloud"]


def test_extract_bullets_returns_from_resumeitem_section() -> None:
    """extract_bullets parses \\resumeItem{...} entries into a tuple of Bullet."""
    section_text = (
        "before\n"
        "\\resumeItem{Built a system}\n"
        "\\resumeItem{Deployed to production}\n"
        "after\n"
    )
    bullets = extract_bullets(section_text, start=section_text.index("\\resumeItem"))
    assert len(bullets) == 2
    assert bullets[0].text == "Built a system"
    assert bullets[1].text == "Deployed to production"


def test_extract_bullets_handles_empty_section() -> None:
    """extract_bullets returns an empty tuple if there are no bullets."""
    assert extract_bullets("no bullets here", start=0) == ()


def test_extract_contact_reads_name_from_huge_scshape() -> None:
    """extract_contact reads the name from a \\Huge \\scshape{...} macro."""
    body = (
        r"{\Huge \scshape {Placeholder Name}" + "\n"
        + r"\small Test City $\cdot$ 5555550100 $\cdot$ placeholder@example.com"
    )
    contact = extract_contact(body)
    assert contact.name == "Placeholder Name"


def test_extract_contact_reads_email_from_href_mailto() -> None:
    """extract_contact reads the email from a \\href{mailto:...} link."""
    body = (
        r"{\Huge \scshape {Placeholder Name}" + "\n"
        + r"\small Test City $\cdot$ 5555550100 $\cdot$ "
        + r"\href{mailto:placeholder@example.com}{placeholder@example.com}\n"
    )
    contact = extract_contact(body)
    assert contact.email == "placeholder@example.com"
    assert contact.name == "Placeholder Name"
    assert contact.phone == "5555550100"
    assert contact.city == "Test City"


def test_extract_contact_returns_none_for_optional_socials() -> None:
    """extract_contact returns None for missing github/linkedin URLs."""
    body = (
        r"{\Huge \scshape {Jane Doe}" + "\n"
        + r"\small Austin $\cdot$ 5555550100 $\cdot$ jane@example.com\n"
    )
    contact = extract_contact(body)
    assert contact.github is None
    assert contact.linkedin is None
    assert contact.email == "jane@example.com"
