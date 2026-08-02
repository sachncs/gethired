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
    sentences = split_sentences(description.full_text)
    return DescriptionAnalysis(
        role=description.title or "Unknown role",
        seniority=infer_seniority(description.full_text),
        must_have_skills=description.must_have_keywords,
        nice_to_have_skills=description.nice_to_have_keywords,
        keywords_to_mirror=description.must_have_keywords + description.nice_to_have_keywords[:5],
        responsibilities=tuple(s for s in sentences if looks_like_responsibility(s)),
        company_context=description.company,
    )


def analyze_multiple(descriptions: tuple[JobDescription, ...]) -> DescriptionAnalysis:
    """Consolidate analyses across multiple job descriptions.

    Rules:
    - must_have_skills: union (a JD considers something required if any JD does).
    - nice_to_have_skills: intersection (only when every JD considers it nice).
    - keywords_to_mirror: must-haves (highest priority) followed by nice-to-haves,
      deduplicated by order of appearance.
    - responsibilities: union of all per-JD responsibility sentences.
    - role: title of the first JD; seniority: highest across JDs.
    - company_context: comma-joined unique companies.

    Args:
        descriptions: One or more JobDescription value objects.

    Returns:
        A single ``DescriptionAnalysis`` representing the consolidated requirements.
    """
    if not descriptions:
        raise ValueError("at least one JobDescription is required")
    analyses = tuple(analyze(jd) for jd in descriptions)
    must_have: list[str] = []
    seen_must: set[str] = set()
    for analysis in analyses:
        for skill in analysis.must_have_skills:
            if skill not in seen_must:
                must_have.append(skill)
                seen_must.add(skill)
    nice_counts: dict[str, int] = {}
    for analysis in analyses:
        for skill in analysis.nice_to_have_skills:
            nice_counts[skill] = nice_counts.get(skill, 0) + 1
    nice_to_have = tuple(
        skill for skill, count in nice_counts.items() if count == len(analyses)
    )
    keywords: list[str] = []
    seen_kw: set[str] = set()
    for skill in list(must_have) + list(nice_to_have):
        if skill not in seen_kw:
            keywords.append(skill)
            seen_kw.add(skill)
    responsibilities: list[str] = []
    seen_resp: set[str] = set()
    for analysis in analyses:
        for sentence in analysis.responsibilities:
            if sentence not in seen_resp:
                responsibilities.append(sentence)
                seen_resp.add(sentence)
    seniority_rank = {
        "principal": 4,
        "staff": 4,
        "senior": 3,
        "lead": 3,
        "junior": 1,
        "intern": 0,
        "unspecified": 0,
    }
    top_seniority = max(
        analyses, key=lambda a: seniority_rank.get(a.seniority, 0)
    ).seniority
    companies = tuple(
        dict.fromkeys(jd.company for jd in descriptions if jd.company)
    )
    return DescriptionAnalysis(
        role=descriptions[0].title or "Unknown role",
        seniority=top_seniority,
        must_have_skills=tuple(must_have),
        nice_to_have_skills=nice_to_have,
        keywords_to_mirror=tuple(keywords),
        responsibilities=tuple(responsibilities),
        company_context=", ".join(companies),
    )


def split_sentences(text: str) -> tuple[str, ...]:
    parts = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
    return tuple(parts)


RESPONSIBILITY_MARKERS = (
    "you will",
    "responsibilities",
    "you'll",
    "you are expected",
    "your role",
    "what you'll do",
    "key responsibilities",
    "the role involves",
)


def looks_like_responsibility(sentence: str) -> bool:
    lowered = sentence.lower()
    return any(marker in lowered for marker in RESPONSIBILITY_MARKERS)


SENIORITY_KEYWORDS = (
    ("principal", "principal"),
    ("staff", "staff"),
    ("senior", "senior"),
    ("lead", "lead"),
    ("junior", "junior"),
    ("intern", "intern"),
)


def infer_seniority(text: str) -> str:
    lowered = text.lower()
    for keyword, label in SENIORITY_KEYWORDS:
        if keyword in lowered:
            return label
    return "unspecified"


__all__ = ["DescriptionAnalysis", "analyze", "analyze_multiple"]
