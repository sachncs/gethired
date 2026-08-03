"""Tests for the cover-letter module."""

from __future__ import annotations

from gethired.cover_letter import (
    markdown,
    compose,
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
    assert result.cover_letter.salutation.startswith("Dear ")
    assert len(result.cover_letter.paragraphs) == 3
    assert result.cover_letter.paragraphs[0].opening is True
    assert result.cover_letter.paragraphs[-1].closing is True
    assert "Senior ML Engineer" in result.cover_letter.paragraphs[0].text


def test_tailor_cover_letter_mirrors_keywords(master_resume) -> None:
    """The cover letter opening includes must-have keywords from the analysis."""
    analysis = _sample_analysis()
    voice = build_profile(master_resume)
    result = compose(master_resume, analysis, voice)
    opening = result.cover_letter.paragraphs[0].text
    assert "python" in opening.lower() or "kubernetes" in opening.lower()


def test_render_cover_letter_markdown_includes_salutation(master_resume) -> None:
    """markdown emits salutation, paragraphs, signoff."""
    analysis = _sample_analysis()
    voice = build_profile(master_resume)
    result = compose(master_resume, analysis, voice)
    md = markdown(result.cover_letter)
    assert "Dear " in md
    assert "Sincerely" in md
    assert result.cover_letter.sender_name in md


def test_tailor_cover_letter_honours_recipient(master_resume) -> None:
    """Passing recipient overrides the default 'Hiring Team' salutation."""
    analysis = _sample_analysis()
    voice = build_profile(master_resume)
    result = compose(master_resume, analysis, voice, recipient="Hiring Manager")
    assert "Hiring Manager" in result.cover_letter.salutation
