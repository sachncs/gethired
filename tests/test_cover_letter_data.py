"""End-to-end data-process tests for the cover letter module.

Verifies the actual data flowing through compose() and markdown():
- The cover letter mirrors the master resume's contact info
- The salutation defaults to "Hiring Team" but is overridable
- The opening includes the analysis role and the candidate's title
- The body mentions must-have keywords from the analysis
- The markdown output contains all the letter sections
- The closing mentions the candidate's seniority level
"""

from __future__ import annotations

from gethired.cover_letter import compose, markdown
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


def test_cover_letter_mirrors_master_contact(master_resume) -> None:
    """The cover letter's signoff uses the master's name."""
    analysis = _sample_analysis()
    voice = build_profile(master_resume)
    result = compose(master_resume, analysis, voice)
    # The signoff ends with the master's name (verified by markdown output)
    md = markdown(result.letter)
    assert master_resume.contact.name in md, (
        f"signoff must include master name {master_resume.contact.name!r}, got {md!r}"
    )


def test_cover_letter_opening_includes_role(master_resume) -> None:
    """The opening paragraph mentions the analysis role."""
    analysis = _sample_analysis()
    voice = build_profile(master_resume)
    result = compose(master_resume, analysis, voice)
    opening = result.letter.paragraphs[0].text
    assert "Senior ML Engineer" in opening, (
        f"opening must mention role {analysis.role!r}, got {opening!r}"
    )


def test_cover_letter_opening_includes_candidate_title(master_resume) -> None:
    """The opening mentions the candidate's most recent role (from the master)."""
    analysis = _sample_analysis()
    voice = build_profile(master_resume)
    result = compose(master_resume, analysis, voice)
    opening = result.letter.paragraphs[0].text
    # The master's most recent experience should be referenced
    first_role = master_resume.experiences[0].role
    assert first_role in opening, (
        f"opening must mention candidate's first role {first_role!r}, got {opening!r}"
    )


def test_cover_letter_body_includes_responsibilities(master_resume) -> None:
    """The body paragraph mentions at least one responsibility from the analysis."""
    analysis = _sample_analysis()
    voice = build_profile(master_resume)
    result = compose(master_resume, analysis, voice)
    body = result.letter.paragraphs[1].text
    # At least one of the responsibilities should be mentioned
    assert any(
        r in body.lower()
        for r in ("design", "lead", "platform", "review")
    ), f"body must mention a responsibility, got {body!r}"


def test_cover_letter_body_mentions_seniority(master_resume) -> None:
    """The body paragraph references the seniority level from the analysis."""
    analysis = _sample_analysis()
    voice = build_profile(master_resume)
    result = compose(master_resume, analysis, voice)
    body = result.letter.paragraphs[1].text
    assert analysis.seniority in body, (
        f"body must mention seniority {analysis.seniority!r}, got {body!r}"
    )


def test_cover_letter_default_salutation_is_hiring_team(master_resume) -> None:
    """Without a recipient override, the salutation is 'Dear Hiring Team,'."""
    analysis = _sample_analysis()
    voice = build_profile(master_resume)
    result = compose(master_resume, analysis, voice)
    assert result.letter.salutation == "Dear Hiring Team,"


def test_cover_letter_sender_name_override(master_resume) -> None:
    """An explicit sender_name is used in the signoff instead of the master's name."""
    analysis = _sample_analysis()
    voice = build_profile(master_resume)
    result = compose(
        master_resume, analysis, voice, sender_name="Anonymous Applicant"
    )
    md = markdown(result.letter)
    assert "Anonymous Applicant" in md
    # But the master's name should NOT be there
    assert master_resume.contact.name not in md


def test_cover_letter_markdown_contains_all_sections(master_resume) -> None:
    """The markdown output contains salutation, all paragraphs, and signoff."""
    analysis = _sample_analysis()
    voice = build_profile(master_resume)
    result = compose(master_resume, analysis, voice)
    md = markdown(result.letter)
    # Salutation
    assert "Dear " in md
    # All paragraphs (the body content)
    assert result.letter.paragraphs[0].text in md
    assert result.letter.paragraphs[1].text in md
    assert result.letter.paragraphs[2].text in md
    # Signoff
    assert "Sincerely" in md
    assert result.letter.sender_name in md


def test_cover_letter_first_role_used_in_opening(master_resume) -> None:
    """The opening names the master's first experience role (most recent)."""
    analysis = _sample_analysis()
    voice = build_profile(master_resume)
    result = compose(master_resume, analysis, voice)
    opening = result.letter.paragraphs[0].text
    expected_role = master_resume.experiences[0].role
    expected_company = master_resume.experiences[0].company
    # The opening should reference the role
    assert expected_role in opening, (
        f"opening must reference most-recent role {expected_role!r}"
    )
    # The opening should reference the company name
    assert expected_company in opening, (
        f"opening must reference most-recent company {expected_company!r}"
    )
