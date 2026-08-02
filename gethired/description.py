"""Description analysis.

Takes a ``JobDescription`` and produces structured requirements that the
writer agent consumes.
"""

from __future__ import annotations

from dataclasses import dataclass

from gethired.models import JobDescription


@dataclass(frozen=True, slots=True)
class DescriptionAnalysis:
    """Structured analysis of a job description."""

    role: str
    seniority: str
    must_have_skills: tuple[str, ...]
    nice_to_have_skills: tuple[str, ...]
    keywords_to_mirror: tuple[str, ...]
    responsibilities: tuple[str, ...]
    company_context: str


def analyze(description: JobDescription) -> DescriptionAnalysis:
    """Produce a structured analysis from a job description.

    Pure heuristic: keyword tiering, sentence segmentation for responsibilities.

    Args:
        description: The structured job description.

    Returns:
        A ``DescriptionAnalysis`` consumable by the writer agent.
    """
    sentences = _split_sentences(description.full_text)
    return DescriptionAnalysis(
        role=description.title or "Unknown role",
        seniority=_infer_seniority(description.full_text),
        must_have_skills=description.must_have_keywords,
        nice_to_have_skills=description.nice_to_have_keywords,
        keywords_to_mirror=description.must_have_keywords + description.nice_to_have_keywords[:5],
        responsibilities=tuple(s for s in sentences if _looks_like_responsibility(s)),
        company_context=description.company,
    )


def _split_sentences(text: str) -> tuple[str, ...]:
    parts = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
    return tuple(parts)


_RESPONSIBILITY_MARKERS = (
    "you will",
    "responsibilities",
    "you'll",
    "you are expected",
    "your role",
    "what you'll do",
    "key responsibilities",
    "the role involves",
)


def _looks_like_responsibility(sentence: str) -> bool:
    lowered = sentence.lower()
    return any(marker in lowered for marker in _RESPONSIBILITY_MARKERS)


_SENIORITY_KEYWORDS = (
    ("principal", "principal"),
    ("staff", "staff"),
    ("senior", "senior"),
    ("lead", "lead"),
    ("junior", "junior"),
    ("intern", "intern"),
)


def _infer_seniority(text: str) -> str:
    lowered = text.lower()
    for keyword, label in _SENIORITY_KEYWORDS:
        if keyword in lowered:
            return label
    return "unspecified"


__all__ = ["DescriptionAnalysis", "analyze"]
