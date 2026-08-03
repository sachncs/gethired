"""Tests for the cover-letter module."""

from __future__ import annotations

import re

from gethired.cover_letter import (
    compose,
    markdown,
)
from gethired.description import Analysis
from gethired.profiler import build as build_profile


def _sample_analysis() -> Analysis:
    return Analysis(
        role="Senior ML Engineer",
        seniority="senior",
        must_have=("python", "kubernetes"),
        nice_to_have=("pytorch",),
        keywords=("python", "kubernetes"),
        responsibilities=("design ML platforms", "lead reviews"),
        company="Acme",
    )


def test_tailor_cover_letter_returns_structured_letter(master_resume) -> None:
    """compose returns a CoverLetter with opening, body, closing."""
    analysis = _sample_analysis()
    voice = build_profile(master_resume)
    result = compose(master_resume, analysis, voice)
    assert result.letter.salutation.startswith("Dear ")
    assert len(result.letter.paragraphs) == 3
    assert result.letter.paragraphs[0].opening is True
    assert result.letter.paragraphs[-1].closing is True
    assert "Senior ML Engineer" in result.letter.paragraphs[0].text


def test_tailor_cover_letter_mirrors_keywords(master_resume) -> None:
    """The cover letter opening must include a real keyword from the analysis.

    The 'or' in the original assertion allowed one keyword OR the other,
    which doesn't verify the actual data process. A proper cover letter
    must include at least one must-have keyword so it passes ATS keyword
    matching. We also verify that the keyword appears as a distinct word
    (not as a substring of another word).
    """
    analysis = _sample_analysis()
    voice = build_profile(master_resume)
    result = compose(master_resume, analysis, voice)
    opening = result.letter.paragraphs[0].text.lower()
    # Use word boundaries so 'python' doesn't match 'pythonic'
    has_python = bool(re.search(r"\bpython\b", opening))
    has_kubernetes = bool(re.search(r"\bkubernetes\b", opening))
    assert has_python or has_kubernetes, (
        f"cover letter opening must mention 'python' or 'kubernetes' as a word, got: {opening!r}"
    )


def test_render_cover_letter_markdown_includes_salutation(master_resume) -> None:
    """markdown emits salutation, paragraphs, signoff."""
    analysis = _sample_analysis()
    voice = build_profile(master_resume)
    result = compose(master_resume, analysis, voice)
    md = markdown(result.letter)
    assert "Dear " in md
    assert "Sincerely" in md
    assert result.letter.sender_name in md


def test_tailor_cover_letter_honours_recipient(master_resume) -> None:
    """Passing recipient overrides the default 'Hiring Team' salutation."""
    analysis = _sample_analysis()
    voice = build_profile(master_resume)
    result = compose(master_resume, analysis, voice, recipient="Hiring Manager")
    assert "Hiring Manager" in result.letter.salutation
