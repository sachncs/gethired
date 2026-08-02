"""Code-based (deterministic) graders for the gethired eval framework.

Per Anthropic's "Demystifying evals for AI agents": deterministic graders
are fast, cheap, objective, and reproducible. Use them whenever the
behaviour under test has a clear pass/fail signal.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass

from gethired.models import MasterResume, TailoredResume
from gethired.normalize import (
    canonicalize_numeric,
    extract_ngrams,
    tokenize_for_overlap,
)
from gethired.renderer import render_json, render_text


@dataclass(frozen=True, slots=True)
class GraderResult:
    """Outcome of running a single grader against a single trial output."""

    name: str
    passed: bool
    detail: str
    score: float = 1.0


def code_equal(name: str, actual: object, expected: object) -> GraderResult:
    """Assert that ``actual == expected``."""
    passed = actual == expected
    detail = (
        f"expected {expected!r}, got {actual!r}" if not passed else "values match"
    )
    return GraderResult(name=name, passed=passed, detail=detail)


def code_field_present(
    name: str, resume: MasterResume | TailoredResume, path: str
) -> GraderResult:
    """Assert that a dotted path on the resume resolves to a truthy value."""
    value = resolve_path(resume, path)
    passed = bool(value)
    detail = f"{path}={'<missing>' if value is None else value!r}"
    return GraderResult(name=name, passed=passed, detail=detail)


def code_field_length(
    name: str, resume: MasterResume | TailoredResume, path: str, expected: int
) -> GraderResult:
    """Assert that a list path has the expected length."""
    value = resolve_path(resume, path)
    if not hasattr(value, "__len__"):
        return GraderResult(
            name=name, passed=False, detail=f"{path} is not sized"
        )
    actual_length = len(value)
    passed = actual_length == expected
    detail = f"{path} has length {actual_length}, expected {expected}"
    return GraderResult(name=name, passed=passed, detail=detail)


def code_text_contains(
    name: str, text: str, substring: str, case_insensitive: bool = True
) -> GraderResult:
    """Assert that ``text`` contains ``substring``."""
    haystack = text.lower() if case_insensitive else text
    needle = substring.lower() if case_insensitive else substring
    passed = needle in haystack
    detail = (
        f"substring {substring!r} found" if passed else f"substring {substring!r} missing"
    )
    return GraderResult(name=name, passed=passed, detail=detail)


def code_text_not_contains(
    name: str, text: str, forbidden: str, case_insensitive: bool = True
) -> GraderResult:
    """Assert that ``text`` does NOT contain ``forbidden``."""
    haystack = text.lower() if case_insensitive else text
    needle = forbidden.lower() if case_insensitive else forbidden
    passed = needle not in haystack
    detail = (
        f"forbidden {forbidden!r} absent"
        if passed
        else f"forbidden {forbidden!r} present"
    )
    return GraderResult(name=name, passed=passed, detail=detail)


def code_no_banned_words(
    name: str, text: str, banned: frozenset[str]
) -> GraderResult:
    """Assert that ``text`` contains none of the ``banned`` words."""
    lowered = text.lower()
    found = sorted(word for word in banned if word in lowered)
    passed = not found
    detail = (
        "no banned words present"
        if passed
        else f"banned words present: {found}"
    )
    return GraderResult(name=name, passed=passed, detail=detail)


def code_no_jd_plagiarism(
    name: str,
    tailored_text: str,
    jd_text: str,
    ngram_size: int = 5,
    technical_allowlist: frozenset[str] = frozenset(),
) -> GraderResult:
    """Assert that no n-gram from the JD appears verbatim in the tailored text.

    Excludes any n-gram in ``technical_allowlist`` (per the project's
    ANTI_AI_RULES + TECHNICAL_NGRAMS_ALLOWLIST rubric).
    """
    tailored_tokens = tokenize_for_overlap(tailored_text)
    jd_tokens = tokenize_for_overlap(jd_text)
    tailored_ngrams = set(extract_ngrams(tailored_tokens, ngram_size))
    jd_ngrams = set(extract_ngrams(jd_tokens, ngram_size))
    overlap = (tailored_ngrams & jd_ngrams) - set(technical_allowlist)
    passed = not overlap
    sample = sorted(overlap)[:3]
    detail = (
        "no n-gram overlap"
        if passed
        else f"{len(overlap)} overlapping n-grams (sample: {sample})"
    )
    return GraderResult(name=name, passed=passed, detail=detail)


def code_numbers_in_master(
    name: str, tailored_text: str, master: MasterResume
) -> GraderResult:
    """Assert that any number in the tailored text is also in the master."""
    tailored_numbers = canonicalize_numeric(tailored_text)
    master_numbers = canonicalize_numeric(master.to_markdown())
    invented = sorted(tailored_numbers - master_numbers)
    passed = not invented
    detail = (
        "all numbers present in master"
        if passed
        else f"invented numbers: {invented}"
    )
    return GraderResult(name=name, passed=passed, detail=detail)


def code_json_round_trip(name: str, tailored: TailoredResume) -> GraderResult:
    """Serialise via the renderer and confirm round-trip equality."""
    json_text = render_json(tailored)
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as exc:
        return GraderResult(
            name=name, passed=False, detail=f"JSON parse failed: {exc}"
        )
    text_source = render_text(tailored)
    passed = bool(data.get("summary")) and bool(text_source)
    detail = (
        "JSON round-trip succeeded"
        if passed
        else "JSON round-trip missing fields"
    )
    return GraderResult(name=name, passed=passed, detail=detail)


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def resolve_path(obj: object, dotted: str) -> object:
    """Resolve a dotted path like ``experiences[0].company`` on a dataclass
    or dict (mixed access supported).
    """
    tokens = re.findall(r"[^.\[\]]+|\[\d+\]", dotted)
    current: object = obj
    for token in tokens:
        if token.startswith("[") and token.endswith("]"):
            index = int(token[1:-1])
            if isinstance(current, (tuple, list)) or isinstance(current, dict) or hasattr(current, "__getitem__"):
                current = current[index]
            else:
                return None
        else:
            if isinstance(current, dict):
                current = current.get(token)
            else:
                current = getattr(current, token, None)
            if current is None:
                return None
    return current


CodeGrader = Callable[..., GraderResult]


__all__ = [
    "GraderResult",
    "code_equal",
    "code_field_length",
    "code_field_present",
    "code_json_round_trip",
    "code_no_banned_words",
    "code_no_jd_plagiarism",
    "code_numbers_in_master",
    "code_text_contains",
    "code_text_not_contains",
]
