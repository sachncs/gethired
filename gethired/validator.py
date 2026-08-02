"""Validator: grounding, style, plagiarism, ATS gates.

Deterministic checks. The critic agent wraps these in a Job-emitting pipeline.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from gethired.constants import BULLET_QUANTIFICATION_THRESHOLD
from gethired.models import (
    AtsGate,
    Bullet,
    JobDescription,
    MasterResume,
    TailoredResume,
)
from gethired.normalize import (
    canonicalize_numeric,
    extract_ngrams,
    is_action_verb,
    normalise_whitespace,
    tokenize_for_overlap,
)
from gethired.rubric import (
    BANNED_CONSTRUCTIONS,
    BANNED_WORDS,
    REQUIRED_SECTION_HEADINGS,
    TECHNICAL_NGRAMS_ALLOWLIST,
)


@dataclass(frozen=True, slots=True)
class GroundingViolation:
    path: str
    detail: str


@dataclass(frozen=True, slots=True)
class StyleViolation:
    path: str
    detail: str


@dataclass(frozen=True, slots=True)
class PlagiarismViolation:
    path: str
    ngram: str


@dataclass(frozen=True, slots=True)
class AtsGateResult:
    gate: AtsGate
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class AtsGateReport:
    results: tuple[AtsGateResult, ...]

    @property
    def all_passed(self) -> bool:
        return all(result.passed for result in self.results)

    @property
    def failed_gates(self) -> tuple[AtsGate, ...]:
        return tuple(result.gate for result in self.results if not result.passed)


# ---------------------------------------------------------------------------
# Grounding
# ---------------------------------------------------------------------------


def grounding_check(
    tailored: TailoredResume,
    master: MasterResume,
    quantification_threshold: float = BULLET_QUANTIFICATION_THRESHOLD,
) -> tuple[GroundingViolation, ...]:
    """Verify every concrete claim in the tailored resume traces back to master.

    Checks:
    - All skills appear in master.skills or master bullets
    - All numeric values appear in master
    - All cited verbatim spans appear in master
    - All company names / employers appear in master
    """
    violations: list[GroundingViolation] = []

    master_text = master.to_markdown().lower()
    master_numbers = canonicalize_numeric(master.to_markdown())

    tailored_text = _tailored_to_text(tailored).lower()

    for skill_category, skills in tailored.skills.categories.items():
        for skill in skills:
            if skill.lower() not in master_text:
                violations.append(
                    GroundingViolation(
                        path=f"skills.categories[{skill_category}]",
                        detail=f"Skill {skill!r} not found in master",
                    )
                )

    for citation in tailored.grounding:
        if citation.verbatim_span.lower() not in master_text:
            violations.append(
                GroundingViolation(
                    path=citation.tailored_path,
                    detail=f"Cited span {citation.verbatim_span!r} not in master",
                )
            )

    tailored_numbers = canonicalize_numeric(_tailored_to_text(tailored))
    for number in tailored_numbers - master_numbers:
        violations.append(
            GroundingViolation(
                path="tailored",
                detail=f"Numeric value {number} not found in master",
            )
        )

    master_companies = {exp.company.lower() for exp in master.experiences}
    for exp in tailored.experiences:
        if exp.company.lower() not in master_companies and master_companies:
            violations.append(
                GroundingViolation(
                    path=f"experiences[{exp.company}]",
                    detail=f"Company {exp.company!r} not in master",
                )
            )

    return tuple(violations)


def _tailored_to_text(tailored: TailoredResume) -> str:
    parts = [tailored.summary]
    for exp in tailored.experiences:
        parts.append(f"{exp.role} {exp.company} {exp.start_date} {exp.end_date}")
        parts.extend(b.text for b in exp.bullets)
    for project in tailored.projects:
        parts.append(project.name)
        parts.extend(b.text for b in project.bullets)
    for category, items in tailored.skills.categories.items():
        parts.append(category)
        parts.extend(items)
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------


def style_check(
    tailored: TailoredResume,
    threshold_ratio: float = BULLET_QUANTIFICATION_THRESHOLD,
) -> tuple[StyleViolation, ...]:
    """Check for banned words, parallelism, length variance, and quantification."""
    violations: list[StyleViolation] = []

    full_text = _tailored_to_text(tailored).lower()
    for word in BANNED_WORDS:
        pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
        for match in pattern.finditer(full_text):
            violations.append(
                StyleViolation(
                    path="tailored",
                    detail=f"Banned word {word!r} at position {match.start()}",
                )
            )
        # Stem-like: match word + common verb suffixes (ed, ing, es, s, d)
        stem_pattern = re.compile(rf"\b{re.escape(word)}(?:s|ed|ing|d)?\b", re.IGNORECASE)
        for match in stem_pattern.finditer(full_text):
            token = match.group(0)
            # Avoid double-counting exact matches already captured above
            if token.lower() == word.lower():
                continue
            violations.append(
                StyleViolation(
                    path="tailored",
                    detail=f"Banned word stem {word!r} matched {token!r} at position {match.start()}",
                )
            )

    for construction in BANNED_CONSTRUCTIONS:
        if construction.lower() in full_text:
            violations.append(
                StyleViolation(
                    path="tailored",
                    detail=f"Banned construction {construction!r}",
                )
            )

    for experience in tailored.experiences:
        violations.extend(_parallelism_violations(experience.role, experience.bullets))
        if experience.bullets:
            quantified = sum(
                1 for bullet in experience.bullets if canonicalize_numeric(bullet.text)
            )
            ratio = quantified / len(experience.bullets)
            if ratio < threshold_ratio:
                violations.append(
                    StyleViolation(
                        path=f"experiences[{experience.role}]",
                        detail=(
                            f"Only {ratio:.0%} of bullets quantified; "
                            f"threshold {threshold_ratio:.0%}"
                        ),
                    )
                )

    if tailored.summary and not is_action_verb(tailored.summary.split(maxsplit=1)[0]):
        violations.append(
            StyleViolation(
                path="summary",
                detail=f"Summary does not start with an action verb: {tailored.summary[:60]!r}",
            )
        )

    return tuple(violations)


def _parallelism_violations(role: str, bullets: tuple[Bullet, ...]) -> tuple[StyleViolation, ...]:
    if len(bullets) < 3:
        return ()
    counter: Counter[str] = Counter()
    for bullet in bullets:
        first_word = bullet.text.split(maxsplit=1)[0].lower().rstrip(".,;:")
        if first_word:
            counter[first_word] += 1
    common = counter.most_common(1)
    if common and common[0][1] >= 3:
        return (
            StyleViolation(
                path=f"experiences[{role}]",
                detail=(
                    f"{common[0][1]} bullets open with the same verb "
                    f"{common[0][0]!r}; vary opening verbs"
                ),
            ),
        )
    return ()


# ---------------------------------------------------------------------------
# Plagiarism
# ---------------------------------------------------------------------------


def plagiarism_check(
    tailored: TailoredResume,
    jds: tuple[JobDescription, ...],
    ngram_size: int = 5,
) -> tuple[PlagiarismViolation, ...]:
    """Check for verbatim n-gram overlap between tailored resume and JDs.

    Excludes n-grams in ``TECHNICAL_NGRAMS_ALLOWLIST``.
    """
    tailored_tokens = tokenize_for_overlap(_tailored_to_text(tailored))
    tailored_ngrams = set(extract_ngrams(tailored_tokens, ngram_size))
    tailored_ngrams -= TECHNICAL_NGRAMS_ALLOWLIST

    violations: list[PlagiarismViolation] = []

    for jd in jds:
        jd_tokens = tokenize_for_overlap(jd.full_text)
        jd_ngrams = set(extract_ngrams(jd_tokens, ngram_size))
        jd_ngrams -= TECHNICAL_NGRAMS_ALLOWLIST
        overlap = tailored_ngrams & jd_ngrams
        for ngram in overlap:
            violations.append(
                PlagiarismViolation(path="tailored", ngram=ngram)
            )

    return tuple(violations)


# ---------------------------------------------------------------------------
# ATS gates
# ---------------------------------------------------------------------------


def ats_check(
    tailored: TailoredResume,
    tex_source: str,
    pdf_path: Path | None,
    txt_source: str,
    jds: tuple[JobDescription, ...],
    quantification_threshold: float = BULLET_QUANTIFICATION_THRESHOLD,
) -> AtsGateReport:
    """Run all 11 ATS gates.

    Args:
        tailored: The tailored resume model.
        tex_source: The rendered TeX source.
        pdf_path: Optional path to the compiled PDF (None if not compiled).
        txt_source: The plain-text ATS version.
        jds: The job descriptions for keyword coverage.
        quantification_threshold: Bullet quantification threshold.

    Returns:
        An ``AtsGateReport`` with per-gate results.
    """
    results: list[AtsGateResult] = []

    results.append(_gate_pdf_compiles(pdf_path))
    results.append(_gate_pdf_text_extractable(pdf_path))
    results.append(_gate_pdf_text_matches_txt(pdf_path, txt_source))
    results.append(_gate_section_headings_standard(tex_source))
    results.append(_gate_no_tables_for_layout(tex_source))
    results.append(_gate_no_images(tex_source))
    results.append(_gate_no_colors(tex_source))
    results.append(_gate_font_size_10_12(tex_source))
    results.append(_gate_length_within_limit(tailored, tex_source))
    results.append(_gate_keywords_covered(tailored, jds))
    results.append(_gate_bullets_quantified(tailored, quantification_threshold))
    results.append(_gate_action_verbs_first(tailored))

    return AtsGateReport(results=tuple(results))


def _gate_pdf_compiles(pdf_path: Path | None) -> AtsGateResult:
    if pdf_path is None:
        return AtsGateResult(AtsGate.PDF_COMPILES, passed=False, detail="PDF not compiled")
    if not pdf_path.exists():
        return AtsGateResult(AtsGate.PDF_COMPILES, passed=False, detail=f"PDF missing: {pdf_path}")
    return AtsGateResult(AtsGate.PDF_COMPILES, passed=True, detail=f"PDF compiled at {pdf_path}")


def _gate_pdf_text_extractable(pdf_path: Path | None) -> AtsGateResult:
    if pdf_path is None or not pdf_path.exists():
        return AtsGateResult(AtsGate.PDF_TEXT_EXTRACTABLE, passed=False, detail="PDF missing")
    try:
        import pymupdf  # type: ignore[import-not-found]

        document = pymupdf.open(pdf_path)
        try:
            text = "\n".join(page.get_text() for page in document)
        finally:
            document.close()
        if not text.strip():
            return AtsGateResult(
                AtsGate.PDF_TEXT_EXTRACTABLE,
                passed=False,
                detail="No text extractable from PDF",
            )
        return AtsGateResult(AtsGate.PDF_TEXT_EXTRACTABLE, passed=True, detail="OK")
    except ImportError:
        return AtsGateResult(
            AtsGate.PDF_TEXT_EXTRACTABLE,
            passed=False,
            detail="pymupdf not installed",
        )


def _gate_pdf_text_matches_txt(pdf_path: Path | None, txt_source: str) -> AtsGateResult:
    if pdf_path is None or not pdf_path.exists():
        return AtsGateResult(AtsGate.PDF_TEXT_MATCHES_TXT, passed=False, detail="PDF missing")
    try:
        import pymupdf  # type: ignore[import-not-found]

        document = pymupdf.open(pdf_path)
        try:
            pdf_text = "\n".join(page.get_text() for page in document)
        finally:
            document.close()
        pdf_normalised = normalise_whitespace(pdf_text)
        txt_normalised = normalise_whitespace(txt_source)
        if pdf_normalised == txt_normalised:
            return AtsGateResult(AtsGate.PDF_TEXT_MATCHES_TXT, passed=True, detail="OK")
        return AtsGateResult(
            AtsGate.PDF_TEXT_MATCHES_TXT,
            passed=False,
            detail="PDF text and tailored.txt differ after normalisation",
        )
    except ImportError:
        return AtsGateResult(
            AtsGate.PDF_TEXT_MATCHES_TXT,
            passed=False,
            detail="pymupdf not installed",
        )


def _gate_section_headings_standard(tex_source: str) -> AtsGateResult:
    found = set(re.findall(r"\\section\{([^}]+)\}", tex_source))
    required = set(REQUIRED_SECTION_HEADINGS)
    missing = required - found
    if missing:
        return AtsGateResult(
            AtsGate.SECTION_HEADINGS_STANDARD,
            passed=False,
            detail=f"Missing sections: {sorted(missing)}",
        )
    return AtsGateResult(
        AtsGate.SECTION_HEADINGS_STANDARD, passed=True, detail="All required sections present"
    )


def _gate_no_tables_for_layout(tex_source: str) -> AtsGateResult:
    layout_patterns = [
        r"\\begin\{tabularx\}\s*\{\s*\d?\.\d+\\textwidth",
        r"\\begin\{multicols\}",
        r"\\begin\{wrapfigure\}",
    ]
    for pattern in layout_patterns:
        if re.search(pattern, tex_source):
            return AtsGateResult(
                AtsGate.NO_TABLES_FOR_LAYOUT,
                passed=False,
                detail=f"Layout table detected: {pattern}",
            )
    return AtsGateResult(AtsGate.NO_TABLES_FOR_LAYOUT, passed=True, detail="OK")


def _gate_no_images(tex_source: str) -> AtsGateResult:
    if re.search(r"\\includegraphics|\\graphic", tex_source):
        return AtsGateResult(AtsGate.NO_IMAGES, passed=False, detail="Image macro detected")
    return AtsGateResult(AtsGate.NO_IMAGES, passed=True, detail="OK")


def _gate_no_colors(tex_source: str) -> AtsGateResult:
    """Allow ``LinkColor`` definition and ``\\color{black}``; flag other color usage."""
    non_link_colors = []
    for pattern in (r"\\color\b", r"\\textcolor\b"):
        for match in re.finditer(pattern, tex_source):
            context = tex_source[max(0, match.start() - 30) : match.end() + 30]
            if "LinkColor" in context:
                continue
            if r"\color{black}" in context:
                continue
            non_link_colors.append(match.group(0))
    if non_link_colors:
        return AtsGateResult(
            AtsGate.NO_COLORS,
            passed=False,
            detail=f"Non-link color usage: {non_link_colors[:3]}",
        )
    return AtsGateResult(AtsGate.NO_COLORS, passed=True, detail="OK")


def _gate_font_size_10_12(tex_source: str) -> AtsGateResult:
    match = re.search(r"\\documentclass\[(?:[^]]*,)?(\d+)pt(?:,[^]]*)?\]", tex_source)
    if match is None:
        return AtsGateResult(
            AtsGate.FONT_SIZE_10_12,
            passed=False,
            detail="No font size directive found",
        )
    size = int(match.group(1))
    if 10 <= size <= 12:
        return AtsGateResult(AtsGate.FONT_SIZE_10_12, passed=True, detail=f"{size}pt OK")
    return AtsGateResult(
        AtsGate.FONT_SIZE_10_12, passed=False, detail=f"Font size {size}pt out of range [10,12]"
    )


def _gate_length_within_limit(tailored: TailoredResume, tex_source: str) -> AtsGateResult:
    # Estimate: count the number of \resumeItem invocations
    item_count = len(re.findall(r"\\resumeItem\b", tex_source))
    # ~4 bullets per page is typical for this template; conservative.
    estimated_pages = max(1.0, item_count / 4.0)
    if estimated_pages <= 1.0:
        return AtsGateResult(
            AtsGate.LENGTH_WITHIN_LIMIT,
            passed=True,
            detail=f"~{estimated_pages:.2f} pages estimated",
        )
    return AtsGateResult(
        AtsGate.LENGTH_WITHIN_LIMIT,
        passed=False,
        detail=f"~{estimated_pages:.2f} pages exceeds limit of 1.0 ({item_count} bullets)",
    )


def _gate_keywords_covered(
    tailored: TailoredResume, jds: tuple[JobDescription, ...]
) -> AtsGateResult:
    must_have: set[str] = set()
    for jd in jds:
        must_have.update(k.lower() for k in jd.must_have_keywords)

    if not must_have:
        return AtsGateResult(AtsGate.KEYWORDS_COVERED, passed=True, detail="No must-have keywords")

    tailored_text = _tailored_to_text(tailored).lower()
    missing = sorted(word for word in must_have if word not in tailored_text)
    if not missing:
        return AtsGateResult(AtsGate.KEYWORDS_COVERED, passed=True, detail="All keywords covered")
    return AtsGateResult(
        AtsGate.KEYWORDS_COVERED,
        passed=False,
        detail=f"Missing must-have keywords: {missing[:10]}",
    )


def _gate_bullets_quantified(
    tailored: TailoredResume, threshold: float
) -> AtsGateResult:
    all_bullets: list[Bullet] = []
    for exp in tailored.experiences:
        all_bullets.extend(exp.bullets)
    for project in tailored.projects:
        all_bullets.extend(project.bullets)
    if not all_bullets:
        return AtsGateResult(AtsGate.BULLETS_QUANTIFIED, passed=True, detail="No bullets")
    quantified = sum(1 for b in all_bullets if canonicalize_numeric(b.text))
    ratio = quantified / len(all_bullets)
    if ratio >= threshold:
        return AtsGateResult(
            AtsGate.BULLETS_QUANTIFIED,
            passed=True,
            detail=f"{ratio:.0%} quantified (>= {threshold:.0%})",
        )
    return AtsGateResult(
        AtsGate.BULLETS_QUANTIFIED,
        passed=False,
        detail=f"{ratio:.0%} quantified (< {threshold:.0%})",
    )


def _gate_action_verbs_first(tailored: TailoredResume) -> AtsGateResult:
    bad: list[str] = []
    for exp in tailored.experiences:
        for bullet in exp.bullets:
            first_word = bullet.text.split(maxsplit=1)[0].lower().rstrip(".,;:")
            if first_word and not is_action_verb(first_word):
                bad.append(f"{exp.role}: {bullet.text[:50]!r}")
    for project in tailored.projects:
        for bullet in project.bullets:
            first_word = bullet.text.split(maxsplit=1)[0].lower().rstrip(".,;:")
            if first_word and not is_action_verb(first_word):
                bad.append(f"{project.name}: {bullet.text[:50]!r}")
    if not bad:
        return AtsGateResult(AtsGate.ACTION_VERBS_FIRST, passed=True, detail="OK")
    return AtsGateResult(
        AtsGate.ACTION_VERBS_FIRST, passed=False, detail=f"{len(bad)} bullets don't start with action verbs"
    )


__all__ = [
    "AtsGateReport",
    "AtsGateResult",
    "GroundingViolation",
    "PlagiarismViolation",
    "StyleViolation",
    "ats_check",
    "grounding_check",
    "plagiarism_check",
    "style_check",
]


_FINAL_TAILORED_TO_TEXT = _tailored_to_text
_FINAL_GROUNDING = grounding_check
