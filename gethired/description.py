"""Description analysis.

Takes a ``Job`` and produces structured requirements that the
writer agent consumes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from gethired.models import Job

MARKERS: Final[tuple[str, ...]] = (
    "you will",
    "responsibilities",
    "you'll",
    "you are expected",
    "your role",
    "what you'll do",
    "key responsibilities",
    "the role involves",
)
"""Sentence prefixes that signal a job-description responsibility statement."""

SENIORITY_KEYWORDS: Final[tuple[tuple[str, str], ...]] = (
    ("principal", "principal"),
    ("staff", "staff"),
    ("senior", "senior"),
    ("lead", "lead"),
    ("junior", "junior"),
    ("intern", "intern"),
)
"""(search_keyword, label) pairs used to infer seniority from JD text."""

SENIORITY_RANK: Final[dict[str, int]] = {
    "principal": 4,
    "staff": 4,
    "senior": 3,
    "lead": 3,
    "junior": 1,
    "intern": 0,
    "unspecified": 0,
}
"""Numeric rank used to pick the highest seniority across multiple JDs."""

UNKNOWN_ROLE: Final[str] = "Unknown role"
"""Sentinel role title when the JD has no parsed title."""

UNSPECIFIED: Final[str] = "unspecified"
"""Sentinel seniority when no keyword matches in the JD text."""


@dataclass(frozen=True, slots=True)
class Analysis:
    """Structured analysis of a job description."""

    role: str
    seniority: str
    must_have: tuple[str, ...]
    nice_to_have: tuple[str, ...]
    keywords: tuple[str, ...]
    responsibilities: tuple[str, ...]
    company: str


def analyze(description: Job) -> Analysis:
    """Produce a structured analysis from a job description.

    Pure heuristic: keyword tiering, sentence segmentation for responsibilities.

    Args:
        description: The structured job description.

    Returns:
        An ``Analysis`` consumable by the writer agent.
    """
    sentences = split_sentences(description.full_text)
    return Analysis(
        role=description.title or UNKNOWN_ROLE,
        seniority=infer_seniority(description.full_text),
        must_have=description.must_have_keywords,
        nice_to_have=description.nice_to_have_keywords,
        keywords=description.must_have_keywords + description.nice_to_have_keywords[:5],
        responsibilities=tuple(s for s in sentences if looks_like_responsibility(s)),
        company=description.company,
    )


def union_skills(analyses: tuple[Analysis, ...]) -> list[str]:
    """Union of must-have skills across all JDs (preserves first-seen order)."""
    seen: set[str] = set()
    result: list[str] = []
    for analysis in analyses:
        for skill in analysis.must_have:
            if skill not in seen:
                result.append(skill)
                seen.add(skill)
    return result


def intersect_skills(analyses: tuple[Analysis, ...]) -> tuple[str, ...]:
    """Nice-to-have skills common to all JDs (intersection)."""
    if not analyses:
        return ()
    counts: dict[str, int] = {}
    for analysis in analyses:
        for skill in analysis.nice_to_have:
            counts[skill] = counts.get(skill, 0) + 1
    return tuple(skill for skill, count in counts.items() if count == len(analyses))


def merged_keywords(analyses: tuple[Analysis, ...]) -> tuple[str, ...]:
    """Deduplicated union of must-haves (first) then nice-to-haves (after)."""
    must_have = _union_skills(analyses)
    seen: set[str] = set(must_have)
    extras: list[str] = []
    for analysis in analyses:
        for skill in analysis.nice_to_have:
            if skill not in seen:
                extras.append(skill)
                seen.add(skill)
    return tuple(must_have + extras)


def union_responsibilities(analyses: tuple[Analysis, ...]) -> tuple[str, ...]:
    """Union of responsibility sentences across all JDs (preserves first-seen order)."""
    seen: set[str] = set()
    result: list[str] = []
    for analysis in analyses:
        for sentence in analysis.responsibilities:
            if sentence not in seen:
                result.append(sentence)
                seen.add(sentence)
    return tuple(result)


def consolidate(descriptions: tuple[Job, ...]) -> Analysis:
    """Consolidate analyses across multiple job descriptions.

    Rules:
    - must_have: union (a JD considers something required if any JD does).
    - nice_to_have: intersection (only when every JD considers it nice).
    - keywords: must-haves (highest priority) followed by nice-to-haves,
      deduplicated by order of appearance.
    - responsibilities: union of all per-JD responsibility sentences.
    - role: title of the first JD; seniority: highest across JDs.
    - company: comma-joined unique companies.

    Args:
        descriptions: One or more Job value objects.

    Returns:
        A single ``Analysis`` representing the consolidated requirements.
    """
    if not descriptions:
        raise ValueError("at least one Job is required")
    analyses = tuple(analyze_description(jd) for jd in descriptions)
    top_seniority = max(
        analyses,
        key=lambda a: SENIORITY_RANK.get(a.seniority, 0),
    ).seniority
    companies = tuple(dict.fromkeys(jd.company for jd in descriptions if jd.company))
    return Analysis(
        role=descriptions[0].title or UNKNOWN_ROLE,
        seniority=top_seniority,
        must_have=tuple(_union_skills(analyses)),
        nice_to_have=_intersect_skills(analyses),
        keywords=_merged_keywords(analyses),
        responsibilities=_union_responsibilities(analyses),
        company=", ".join(companies),
    )


# Re-exported under the original multi-word names for backwards compatibility.
analyze_description = analyze
analyze_description_multiple = consolidate


def overlay_for_jd(merged: Analysis, jd: Job) -> Analysis:
    """Build a per-JD analysis by overlaying the JD's own fields on top of the merged keyword set.

    Useful for cover-letter production: the keyword universe stays merged (so
    every letter reflects every JD's must-haves), but role / seniority /
    company / responsibilities come from the specific JD so each letter
    addresses its own posting rather than a generic blended role.

    Args:
        merged: The LLM-merged analysis (used for must_have / nice_to_have /
            keywords).
        jd: The single JD whose role/seniority/company/responsibilities
            should drive the per-letter output.

    Returns:
        A new ``Analysis`` with the JD-specific fields overlaid on the
        merged keyword set.
    """
    per_jd = analyze(jd)
    role = per_jd.role if per_jd.role != UNKNOWN_ROLE else merged.role
    seniority = (
        per_jd.seniority if per_jd.seniority != UNSPECIFIED else merged.seniority
    )
    company = per_jd.company if per_jd.company else merged.company
    responsibilities = (
        per_jd.responsibilities if per_jd.responsibilities else merged.responsibilities
    )
    return Analysis(
        role=role,
        seniority=seniority,
        must_have=merged.must_have,
        nice_to_have=merged.nice_to_have,
        keywords=merged.keywords,
        responsibilities=responsibilities,
        company=company,
    )


def split_sentences(text: str) -> tuple[str, ...]:
    parts = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
    return tuple(parts)


def looks_like_responsibility(sentence: str) -> bool:
    lowered = sentence.lower()
    return any(marker in lowered for marker in MARKERS)


def infer_seniority(text: str) -> str:
    lowered = text.lower()
    for keyword, label in SENIORITY_KEYWORDS:
        if keyword in lowered:
            return label
    return UNSPECIFIED


__all__ = [
    "Analysis",
    "MARKERS",
    "SENIORITY_KEYWORDS",
    "SENIORITY_RANK",
    "UNKNOWN_ROLE",
    "UNSPECIFIED",
    "analyze",
    "consolidate",
    "overlay_for_jd",
]
