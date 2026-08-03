"""Validator: grounding, style, plagiarism, ATS gates.

Deterministic checks. The critic agent wraps these in a Job-emitting pipeline.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from gethired.constants import PAGES, QUANTIFY
from gethired.models import (
    AtsGate,
    Bullet,
    GateStatus,
    GateTier,
    Job,
    Master,
    Tailored,
)
from gethired.normalize import (
    numbers,
    ngrams,
    verb,
    tokenize,
    flatten as normalize_flatten,
)
from gethired.rubric import (
    ALLOWLIST,
    BANNED,
    CONSTRUCTIONS,
    SECTIONS,
)


@dataclass(frozen=True, slots=True)
class GroundingFault:
    path: str
    detail: str


@dataclass(frozen=True, slots=True)
class StyleFault:
    path: str
    detail: str


@dataclass(frozen=True, slots=True)
class PlagiarismFault:
    path: str
    ngram: str


@dataclass(frozen=True, slots=True)
class AtsResult:
    gate: AtsGate
    status: GateStatus
    detail: str

    @property
    def passed(self) -> bool:
        """Backward-compatible view: True only when the gate evaluated to PASS."""
        return self.status is GateStatus.PASS


@dataclass(frozen=True, slots=True)
class AtsReport:
    results: tuple[AtsResult, ...]

    @property
    def all_passed(self) -> bool:
        """True when no gate evaluated to FAIL (SKIP is tolerated)."""
        return all(result.status is not GateStatus.FAIL for result in self.results)

    @property
    def failed_gates(self) -> tuple[AtsGate, ...]:
        return tuple(result.gate for result in self.results if result.status is GateStatus.FAIL)

    @property
    def hard_failed_gates(self) -> tuple[AtsGate, ...]:
        return tuple(
            result.gate
            for result in self.results
            if result.status is GateStatus.FAIL and result.gate.tier is GateTier.HARD
        )

    @property
    def advisory_failed_gates(self) -> tuple[AtsGate, ...]:
        return tuple(
            result.gate
            for result in self.results
            if result.status is GateStatus.FAIL and result.gate.tier is GateTier.ADVISORY
        )

    @property
    def skipped_gates(self) -> tuple[AtsGate, ...]:
        return tuple(result.gate for result in self.results if result.status is GateStatus.SKIP)


# ---------------------------------------------------------------------------
# Grounding
# ---------------------------------------------------------------------------


def grounding(
    tailored: Tailored,
    master: Master,
) -> tuple[GroundingFault, ...]:
    """Verify every concrete claim in the tailored resume traces back to master.

    Checks:
    - All skills appear in master.skills or master bullets
    - All numeric values appear in master
    - All cited verbatim spans appear in master
    - All company names / employers appear in master
    """
    violations: list[GroundingFault] = []

    master_text = master.to_markdown().lower()
    master_numbers = numbers(master.to_markdown())

    for skill_category, skills in tailored.skills.categories.items():
        for skill in skills:
            if skill.lower() not in master_text:
                violations.append(
                    GroundingFault(
                        path=f"skills.categories[{skill_category}]",
                        detail=f"Skill {skill!r} not found in master",
                    )
                )

    for citation in tailored.grounding:
        if citation.verbatim_span.lower() not in master_text:
            violations.append(
                GroundingFault(
                    path=citation.tailored_path,
                    detail=f"Cited span {citation.verbatim_span!r} not in master",
                )
            )

    tailored_numbers = numbers(flatten(tailored))
    for number in tailored_numbers - master_numbers:
        violations.append(
            GroundingFault(
                path="tailored",
                detail=f"Numeric value {number} not found in master",
            )
        )

    master_companies = {exp.company.lower() for exp in master.experiences}
    for exp in tailored.experiences:
        if exp.company.lower() not in master_companies and master_companies:
            violations.append(
                GroundingFault(
                    path=f"experiences[{exp.company}]",
                    detail=f"Company {exp.company!r} not in master",
                )
            )

    return tuple(violations)


def flatten(tailored: Tailored) -> str:
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


def style(
    tailored: Tailored,
    threshold_ratio: float = QUANTIFY,
) -> tuple[StyleFault, ...]:
    """Check for banned words, parallelism, length variance, and quantification."""
    violations: list[StyleFault] = []

    full_text = flatten(tailored).lower()
    for word in BANNED:
        pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
        for match in pattern.finditer(full_text):
            violations.append(
                StyleFault(
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
                StyleFault(
                    path="tailored",
                    detail=(
                        f"Banned word stem {word!r} matched {token!r} at position {match.start()}"
                    ),
                )
            )

    for construction in CONSTRUCTIONS:
        if construction.lower() in full_text:
            violations.append(
                StyleFault(
                    path="tailored",
                    detail=f"Banned construction {construction!r}",
                )
            )

    for experience in tailored.experiences:
        violations.extend(parallelism(experience.role, experience.bullets))
        if experience.bullets:
            quantified = sum(
                1 for bullet in experience.bullets if numbers(bullet.text)
            )
            ratio = quantified / len(experience.bullets)
            if ratio < threshold_ratio:
                violations.append(
                    StyleFault(
                        path=f"experiences[{experience.role}]",
                        detail=(
                            f"Only {ratio:.0%} of bullets quantified; "
                            f"threshold {threshold_ratio:.0%}"
                        ),
                    )
                )

    if tailored.summary and not verb(tailored.summary.split(maxsplit=1)[0]):
        violations.append(
            StyleFault(
                path="summary",
                detail=f"Summary does not start with an action verb: {tailored.summary[:60]!r}",
            )
        )

    return tuple(violations)


def parallelism(role: str, bullets: tuple[Bullet, ...]) -> tuple[StyleFault, ...]:
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
            StyleFault(
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


def plagiarism(
    tailored: Tailored,
    jds: tuple[Job, ...],
    ngram_size: int = 5,
) -> tuple[PlagiarismFault, ...]:
    """Check for verbatim n-gram overlap between tailored resume and JDs.

    Excludes n-grams in ``ALLOWLIST``.
    """
    tailored_tokens = tokenize(flatten(tailored))
    tailored_ngrams = set(ngrams(tailored_tokens, ngram_size))
    tailored_ngrams -= ALLOWLIST

    violations: list[PlagiarismFault] = []

    for jd in jds:
        jd_tokens = tokenize(jd.full_text)
        jd_ngrams = set(ngrams(jd_tokens, ngram_size))
        jd_ngrams -= ALLOWLIST
        overlap = tailored_ngrams & jd_ngrams
        for ngram in overlap:
            violations.append(PlagiarismFault(path="tailored", ngram=ngram))

    return tuple(violations)


# ---------------------------------------------------------------------------
# ATS gates
# ---------------------------------------------------------------------------


def ats(
    tailored: Tailored,
    tex_source: str,
    pdf_path: Path | None,
    txt_source: str,
    jds: tuple[Job, ...],
    quantification_threshold: float = QUANTIFY,
) -> AtsReport:
    """Run all 12 ATS gates (9 hard-blocking, 3 advisory).

    Args:
        tailored: The tailored resume model.
        tex_source: The rendered TeX source.
        pdf_path: Optional path to the compiled PDF (None if not compiled).
        txt_source: The plain-text ATS version.
        jds: The job descriptions for keyword coverage.
        quantification_threshold: Bullet quantification threshold.

    Returns:
        An ``AtsReport`` with per-gate results.
    """
    results: list[AtsResult] = []

    results.append(gate_pdf(pdf_path))
    results.append(gate_text(pdf_path))
    results.append(gate_match(pdf_path, txt_source))
    results.append(gate_sections(tex_source))
    results.append(gate_tables(tex_source))
    results.append(gate_images(tex_source))
    results.append(gate_colors(tex_source))
    results.append(gate_font(tex_source))
    results.append(gate_length(pdf_path))
    results.append(gate_keywords(tailored, jds))
    results.append(gate_quantify(tailored, quantification_threshold))
    results.append(gate_verbs(tailored))

    return AtsReport(results=tuple(results))


def pdf_guard(
    pdf_path: Path | None,
    gate: AtsGate,
    skip_detail: str = "PDF not compiled (skipped)",
    missing_detail: str | None = None,
) -> AtsResult | None:
    """Return the ``SKIP`` / ``FAIL`` result for a PDF-dependent gate.

    PDF-dependent gates share a two-step guard: skip when no PDF was
    produced (``LATEX_ENGINE=none`` or compilation was not attempted), and
    fail when the path was provided but the file is missing. This helper
    consolidates the guard so each gate can focus on its real check.

    Args:
        pdf_path: The compiled PDF path (or ``None``).
        gate: The gate being evaluated.
        skip_detail: The detail string when ``pdf_path is None``.
        missing_detail: The detail string when the path is set but missing.
            Defaults to ``f"PDF missing: {pdf_path}"``.

    Returns:
        The ``SKIP`` or ``FAIL`` result when the guard fires; otherwise
        ``None`` (caller should run the actual gate logic).
    """
    if pdf_path is None:
        return AtsResult(gate, GateStatus.SKIP, detail=skip_detail)
    if not pdf_path.exists():
        return AtsResult(
            gate,
            GateStatus.FAIL,
            detail=missing_detail or f"PDF missing: {pdf_path}",
        )
    return None


def gate_pdf(pdf_path: Path | None) -> AtsResult:
    blocked = pdf_guard(pdf_path, AtsGate.PDF_COMPILES)
    if blocked is not None:
        return blocked
    return AtsResult(
        AtsGate.PDF_COMPILES, GateStatus.PASS, detail=f"PDF compiled at {pdf_path}"
    )


def gate_text(pdf_path: Path | None) -> AtsResult:
    blocked = pdf_guard(pdf_path, AtsGate.PDF_TEXT_EXTRACTABLE)
    if blocked is not None:
        return blocked
    with pymupdf.open(pdf_path) as document:
        text = "\n".join(document[i].get_text() for i in range(len(document)))
    if not text.strip():
        return AtsResult(
            AtsGate.PDF_TEXT_EXTRACTABLE,
            GateStatus.FAIL,
            detail="No text extractable from PDF",
        )
    return AtsResult(AtsGate.PDF_TEXT_EXTRACTABLE, GateStatus.PASS, detail="OK")


def gate_match(pdf_path: Path | None, txt_source: str) -> AtsResult:
    blocked = pdf_guard(pdf_path, AtsGate.PDF_TEXT_MATCHES_TXT)
    if blocked is not None:
        return blocked
    with pymupdf.open(pdf_path) as document:
        pdf_text = "\n".join(document[i].get_text() for i in range(len(document)))
    pdf_normalised = normalize_flatten(pdf_text)
    txt_normalised = normalize_flatten(txt_source)
    if pdf_normalised == txt_normalised:
        return AtsResult(AtsGate.PDF_TEXT_MATCHES_TXT, GateStatus.PASS, detail="OK")
    return AtsResult(
        AtsGate.PDF_TEXT_MATCHES_TXT,
        GateStatus.FAIL,
        detail="PDF text and tailored.txt differ after normalisation",
    )


def gate_sections(tex_source: str) -> AtsResult:
    found = set(re.findall(r"\\section\{([^}]+)\}", tex_source))
    required = set(SECTIONS)
    missing = required - found
    if missing:
        return AtsResult(
            AtsGate.SECTION_HEADINGS_STANDARD,
            GateStatus.FAIL,
            detail=f"Missing sections: {sorted(missing)}",
        )
    return AtsResult(
        AtsGate.SECTION_HEADINGS_STANDARD, GateStatus.PASS, detail="All required sections present"
    )


def gate_tables(tex_source: str) -> AtsResult:
    layout_patterns = [
        r"\\begin\{tabularx\}\s*\{\s*\d?\.\d+\\textwidth",
        r"\\begin\{multicols\}",
        r"\\begin\{wrapfigure\}",
    ]
    for pattern in layout_patterns:
        if re.search(pattern, tex_source):
            return AtsResult(
                AtsGate.NO_TABLES_FOR_LAYOUT,
                GateStatus.FAIL,
                detail=f"Layout table detected: {pattern}",
            )
    return AtsResult(AtsGate.NO_TABLES_FOR_LAYOUT, GateStatus.PASS, detail="OK")


def gate_images(tex_source: str) -> AtsResult:
    if re.search(r"\\includegraphics|\\graphic", tex_source):
        return AtsResult(AtsGate.NO_IMAGES, GateStatus.FAIL, detail="Image macro detected")
    return AtsResult(AtsGate.NO_IMAGES, GateStatus.PASS, detail="OK")


def gate_colors(tex_source: str) -> AtsResult:
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
        return AtsResult(
            AtsGate.NO_COLORS,
            GateStatus.FAIL,
            detail=f"Non-link color usage: {non_link_colors[:3]}",
        )
    return AtsResult(AtsGate.NO_COLORS, GateStatus.PASS, detail="OK")


def gate_font(tex_source: str) -> AtsResult:
    match = re.search(r"\\documentclass\[(?:[^]]*,)?(\d+)pt(?:,[^]]*)?\]", tex_source)
    if match is None:
        return AtsResult(
            AtsGate.FONT_SIZE_10_12,
            GateStatus.FAIL,
            detail="No font size directive found",
        )
    size = int(match.group(1))
    if 10 <= size <= 12:
        return AtsResult(AtsGate.FONT_SIZE_10_12, GateStatus.PASS, detail=f"{size}pt OK")
    return AtsResult(
        AtsGate.FONT_SIZE_10_12,
        GateStatus.FAIL,
        detail=f"Font size {size}pt out of range [10,12]",
    )


def gate_length(pdf_path: Path | None) -> AtsResult:
    """Measure the compiled PDF's actual page count against ``PAGES``.

    The page count is read from the compiled PDF rather than estimated from
    the TeX source, so the gate reflects what an ATS would actually receive.
    """
    blocked = pdf_guard(pdf_path, AtsGate.LENGTH_WITHIN_LIMIT)
    if blocked is not None:
        return blocked
    with pymupdf.open(pdf_path) as document:
        page_count = document.page_count
    if page_count <= PAGES:
        return AtsResult(
            AtsGate.LENGTH_WITHIN_LIMIT,
            GateStatus.PASS,
            detail=f"{page_count} page(s), within limit of {PAGES}",
        )
    return AtsResult(
        AtsGate.LENGTH_WITHIN_LIMIT,
        GateStatus.FAIL,
        detail=f"{page_count} page(s) exceeds limit of {PAGES}",
    )


def gate_keywords(
    tailored: Tailored, jds: tuple[Job, ...]
) -> AtsResult:
    must_have: set[str] = set()
    for jd in jds:
        must_have.update(k.lower() for k in jd.must_have_keywords)

    if not must_have:
        return AtsResult(
            AtsGate.KEYWORDS_COVERED, GateStatus.PASS, detail="No must-have keywords"
        )

    tailored_text = flatten(tailored).lower()
    missing = sorted(word for word in must_have if word not in tailored_text)
    if not missing:
        return AtsResult(
            AtsGate.KEYWORDS_COVERED, GateStatus.PASS, detail="All keywords covered"
        )
    return AtsResult(
        AtsGate.KEYWORDS_COVERED,
        GateStatus.FAIL,
        detail=f"Missing must-have keywords: {missing[:10]}",
    )


def gate_quantify(tailored: Tailored, threshold: float) -> AtsResult:
    all_bullets: list[Bullet] = []
    for exp in tailored.experiences:
        all_bullets.extend(exp.bullets)
    for project in tailored.projects:
        all_bullets.extend(project.bullets)
    if not all_bullets:
        return AtsResult(AtsGate.BULLETS_QUANTIFIED, GateStatus.PASS, detail="No bullets")
    quantified = sum(1 for b in all_bullets if numbers(b.text))
    ratio = quantified / len(all_bullets)
    if ratio >= threshold:
        return AtsResult(
            AtsGate.BULLETS_QUANTIFIED,
            GateStatus.PASS,
            detail=f"{ratio:.0%} quantified (>= {threshold:.0%})",
        )
    return AtsResult(
        AtsGate.BULLETS_QUANTIFIED,
        GateStatus.FAIL,
        detail=f"{ratio:.0%} quantified (< {threshold:.0%})",
    )


def gate_verbs(tailored: Tailored) -> AtsResult:
    bad: list[str] = []
    for exp in tailored.experiences:
        for bullet in exp.bullets:
            first_word = bullet.text.split(maxsplit=1)[0].lower().rstrip(".,;:")
            if first_word and not verb(first_word):
                bad.append(f"{exp.role}: {bullet.text[:50]!r}")
    for project in tailored.projects:
        for bullet in project.bullets:
            first_word = bullet.text.split(maxsplit=1)[0].lower().rstrip(".,;:")
            if first_word and not verb(first_word):
                bad.append(f"{project.name}: {bullet.text[:50]!r}")
    if not bad:
        return AtsResult(AtsGate.ACTION_VERBS_FIRST, GateStatus.PASS, detail="OK")
    return AtsResult(
        AtsGate.ACTION_VERBS_FIRST,
        GateStatus.FAIL,
        detail=f"{len(bad)} bullets don't start with action verbs",
    )


__all__ = [
    "AtsReport",
    "AtsResult",
    "GateStatus",
    "GateTier",
    "GroundingFault",
    "PlagiarismFault",
    "StyleFault",
    "ats",
    "grounding",
    "pdf_guard",
    "plagiarism",
    "style",
]
