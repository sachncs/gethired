"""Cover-letter tailoring agent.

Produces a structured ``CoverLetter`` against a ``DescriptionAnalysis`` while
preserving the candidate's voice profile. Pure deterministic; intended to be
called by ``Tailor`` when ``produce_cover_letter=True``.
"""

from __future__ import annotations

from dataclasses import dataclass

from gethired.description import DescriptionAnalysis
from gethired.models import (
    ContactInformation,
    CoverLetter,
    CoverLetterParagraph,
    MasterResume,
    VoiceProfile,
)


@dataclass(frozen=True, slots=True)
class CoverLetterResult:
    """Result of a cover-letter tailoring pass."""

    cover_letter: CoverLetter
    rationale: str


def tailor_cover_letter(
    master: MasterResume,
    analysis: DescriptionAnalysis,
    voice: VoiceProfile,
    sender_name: str | None = None,
    recipient: str | None = None,
) -> CoverLetterResult:
    """Produce a cover letter for ``master`` against ``analysis``.

    Args:
        master: The canonical master resume.
        analysis: Structured JD analysis.
        voice: Voice profile for fingerprint preservation.
        sender_name: Optional override for the closing sign-off name.
        recipient: Optional recipient line (e.g. "Hiring Manager").

    Returns:
        ``CoverLetterResult`` containing the letter and a one-sentence rationale.
    """
    name = sender_name or master.contact.name
    salutation = f"Dear {recipient or 'Hiring Team'},"
    keyword_blob = ", ".join(analysis.must_have_skills[:3]) or "your domain"
    opening_verb = voice.opening_verbs[0] if voice.opening_verbs else "Built"
    top_role = master.experiences[0].role if master.experiences else "engineer"
    top_company = master.experiences[0].company if master.experiences else "a previous team"
    opening = (
        f"I am excited to apply for the {analysis.role} role. "
        f"With a track record spanning {top_role} at {top_company}, "
        f"my work focuses on {keyword_blob}."
    )
    body = (
        f"In my recent role, I {opening_verb.lower()} systems that align with the "
        f"responsibilities you describe — including "
        f"{', '.join(analysis.responsibilities[:2]) or 'cross-functional collaboration'}. "
        f"My approach balances pragmatism with rigour, and I thrive in teams where "
        f"{analysis.seniority} ownership is expected."
    )
    closing = (
        f"I would welcome the chance to discuss how my background maps to your "
        f"needs. Thank you for considering my application."
    )
    signoff = f"Sincerely,\n{name}"
    paragraphs = (
        CoverLetterParagraph(text=opening, opening=True),
        CoverLetterParagraph(text=body),
        CoverLetterParagraph(text=closing, closing=True),
    )
    letter = CoverLetter(
        salutation=salutation,
        paragraphs=paragraphs,
        signoff=signoff,
        sender_name=name,
        recipient=recipient,
    )
    rationale = (
        f"Cover letter tailored for {analysis.role}; "
        f"mirrored {len(analysis.must_have_skills)} must-have keywords."
    )
    return CoverLetterResult(cover_letter=letter, rationale=rationale)


def render_cover_letter_markdown(letter: CoverLetter) -> str:
    """Render the cover letter as a Markdown document.

    Default renderer per v0.4.0 plan (Markdown first; TeX optional later).
    """
    lines: list[str] = []
    lines.append(letter.salutation)
    lines.append("")
    for paragraph in letter.paragraphs:
        lines.append(paragraph.text)
        lines.append("")
    lines.append(letter.signoff)
    return "\n".join(lines).rstrip() + "\n"


__all__ = ["CoverLetterResult", "render_cover_letter_markdown", "tailor_cover_letter"]