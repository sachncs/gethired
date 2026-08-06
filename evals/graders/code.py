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
from pathlib import Path
from typing import Any

from gethired.models import (
    Resume,
    Tailored,
)
from gethired.normalize import (
    ngrams,
    numbers,
    tokenize)
from gethired.renderer import text
from gethired.serialize import render_json


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
    name: str, resume: Resume | Tailored, path: str
) -> GraderResult:
    """Assert that a dotted path on the resume resolves to a truthy value."""
    value = resolve_path(resume, path)
    passed = bool(value)
    detail = f"{path}={'<missing>' if value is None else value!r}"
    return GraderResult(name=name, passed=passed, detail=detail)


def code_field_length(
    name: str, resume: Resume | Tailored, path: str, expected: int
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
    technical_allowlist: frozenset[str] = frozenset()) -> GraderResult:
    """Assert that no n-gram from the JD appears verbatim in the tailored text.

    Excludes any n-gram in ``technical_allowlist`` (per the project's
    ANTI_AI + ALLOWLIST rubric).
    """
    tailored_tokens = tokenize(tailored_text)
    jd_tokens = tokenize(jd_text)
    tailored_ngrams = set(ngrams(tailored_tokens, ngram_size))
    jd_ngrams = set(ngrams(jd_tokens, ngram_size))
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
    name: str, tailored_text: str, master: Resume
) -> GraderResult:
    """Assert that any number in the tailored text is also in the master."""
    tailored_numbers = numbers(tailored_text)
    master_numbers = numbers(master.to_markdown())
    invented = sorted(tailored_numbers - master_numbers)
    passed = not invented
    detail = (
        "all numbers present in master"
        if passed
        else f"invented numbers: {invented}"
    )
    return GraderResult(name=name, passed=passed, detail=detail)


def code_json_round_trip(name: str, tailored: Tailored) -> GraderResult:
    """Serialise via the renderer and confirm round-trip equality."""
    json_text = render_json(tailored)
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as exc:
        return GraderResult(
            name=name, passed=False, detail=f"JSON dispatch failed: {exc}"
        )
    text_source = text(tailored)
    passed = bool(data.get("summary")) and bool(text_source)
    detail = (
        "JSON round-trip succeeded"
        if passed
        else "JSON round-trip missing fields"
    )
    return GraderResult(name=name, passed=passed, detail=detail)


# ---------------------------------------------------------------------------
# Agent-evaluation graders (deepeval-style component + reasoning + execution)
# ---------------------------------------------------------------------------

# Names of the Writer agent's read-only tools. Used by component-level graders
# to assert that the agent picked the right tool for the right job.
WRITER_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "experience",
        "project",
        "skills",
        "projects",
        "education",
        "awards",
        "jd",
    }
)


def code_tool_correctness(
    name: str,
    trace_path: str,
    expected_tools: tuple[str, ...] = ()) -> GraderResult:
    """Component-level grader (deepeval ``ToolCorrectnessMetric``).

    Compares the set of tool names the Writer agent actually invoked
    (recorded in ``tailored/<run-id>/trace.jsonl`` as ``tool`` spans)
    against the expected tool sequence. Passes iff the multisets match.
    """
    actual = _read_tool_names(trace_path)
    expected_set = set(expected_tools)
    if not actual:
        return GraderResult(
            name=name,
            passed=False,
            detail=f"no tool spans recorded; expected {sorted(expected_set)}")
    if not expected_set:
        return GraderResult(
            name=name,
            passed=True,
            detail=f"agent invoked {sorted(actual)}; no expected set declared",
            score=1.0)
    missing = expected_set - actual
    extra = actual - expected_set
    passed = not missing
    detail_parts: list[str] = []
    if missing:
        detail_parts.append(f"missing tools: {sorted(missing)}")
    if extra:
        detail_parts.append(f"extra tools: {sorted(extra)}")
    if passed:
        detail_parts.append("agent tool selection matches expected set")
    expected_size = len(expected_set)
    score = (
        len(expected_set & actual) / expected_size if expected_size else 1.0
    )
    return GraderResult(
        name=name,
        passed=passed,
        detail="; ".join(detail_parts) if detail_parts else "tools match",
        score=score)


def code_argument_correctness(
    name: str,
    trace_path: str,
    zero_arg_tools: frozenset[str] = frozenset(
        {"skills", "projects", "education", "awards", "jd"}
    )) -> GraderResult:
    """Component-level grader (deepeval ``ArgumentCorrectnessMetric``).

    Verifies that every ``tool`` span in the trace that requires
    arguments actually carries at least one attribute. Tools that
    legitimately take no arguments (``skills`` etc.) are exempt.
    """
    spans = _read_spans(trace_path, kind="tool")
    if not spans:
        return GraderResult(
            name=name,
            passed=False,
            detail="no tool spans in trace")
    bad = [
        span["name"]
        for span in spans
        if span["name"] not in zero_arg_tools and not span["attributes"]
    ]
    passed = not bad
    detail = (
        f"all {len(spans)} tool spans carry arguments"
        if passed
        else f"{len(bad)}/{len(spans)} tool spans missing arguments: {bad}"
    )
    return GraderResult(
        name=name, passed=passed, detail=detail,
        score=1.0 if passed else (len(spans) - len(bad)) / len(spans))


def code_plan_adherence(
    name: str,
    trace_path: str) -> GraderResult:
    """Reasoning-layer grader (deepeval ``PlanAdherenceMetric``).

    Flags the agent for repeated invocations of the same tool with
    identical attributes — a sign that the agent deviated from its
    own plan by re-asking the same question.
    """
    spans = _read_spans(trace_path, kind="tool")
    seen: dict[tuple[str, str], int] = {}
    for span in spans:
        key = (span["name"], json.dumps(span["attributes"], sort_keys=True, default=str))
        seen[key] = seen.get(key, 0) + 1
    repeats = {key: count for key, count in seen.items() if count > 1}
    passed = not repeats
    detail = (
        "no duplicate tool invocations"
        if passed
        else f"{len(repeats)} tool invocations repeated: {sorted(repeats)}"
    )
    return GraderResult(name=name, passed=passed, detail=detail)


def code_plan_quality(
    name: str,
    trace_path: str,
    expected_first_tool: str = "skills") -> GraderResult:
    """Reasoning-layer grader (deepeval ``PlanQualityMetric``).

    Asserts the agent's first tool call is a survey tool
    (``skills`` by default) rather than a deep lookup. Surveying
    before diving is the documented plan; flunking this grader
    indicates the agent jumped to detail without context.
    """
    spans = _read_spans(trace_path, kind="tool")
    if not spans:
        return GraderResult(
            name=name, passed=False, detail="no tool spans in trace"
        )
    first = spans[0]["name"]
    passed = first == expected_first_tool
    detail = (
        f"first tool was {first} (matches expected {expected_first_tool})"
        if passed
        else f"first tool was {first}, expected survey tool {expected_first_tool}"
    )
    return GraderResult(name=name, passed=passed, detail=detail)


def code_step_efficiency(
    name: str,
    trace_path: str,
    max_tool_calls: int = 6) -> GraderResult:
    """Overall-execution grader (deepeval ``StepEfficiencyMetric``).

    Flags a run when the agent invokes more than ``max_tool_calls``
    read-only tools. Exceeding the budget is a sign of inefficient
    planning or repeated probing for already-known information.
    """
    spans = _read_spans(trace_path, kind="tool")
    n = len(spans)
    passed = n <= max_tool_calls
    detail = (
        f"{n} tool calls within budget {max_tool_calls}"
        if passed
        else f"{n} tool calls exceed budget {max_tool_calls}"
    )
    return GraderResult(
        name=name, passed=passed, detail=detail,
        score=min(1.0, max_tool_calls / n) if n else 1.0)


def code_task_completion(
    name: str,
    trace_path: str,
    tailored: Tailored) -> GraderResult:
    """Overall-execution grader (deepeval ``TaskCompletionMetric``).

    Combines the agent-trace presence (the agent must have produced
    at least one TAILOR span) with structural completeness of the
    tailored resume. Passes iff the trace records a TAILOR and the
    resume is well-formed.
    """
    spans = _read_spans(trace_path, kind="agent")
    has_tailor_span = any(s["name"] == "tailor.run" for s in spans)
    summary_present = bool(tailored.summary and tailored.summary.strip())
    experiences_present = bool(tailored.experience)
    passed = has_tailor_span and summary_present and experiences_present
    detail = (
        "tailor.run span present, summary + experiences populated"
        if passed
        else (
            f"missing: "
            f"{[] if has_tailor_span else ['tailor.run']}"
            f"{[] if summary_present else ['summary']}"
            f"{[] if experiences_present else ['experiences']}"
        )
    )
    return GraderResult(name=name, passed=passed, detail=detail)


# ---------------------------------------------------------------------------
# Helpers (private)
# ---------------------------------------------------------------------------


def _read_spans(trace_path: str, kind: str | None = None) -> list[dict[str, Any]]:
    """Read span records from a trace.jsonl file."""
    path = Path(trace_path)
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if kind is None or record.get("kind") == kind:
            records.append(record)
    return records


def _read_tool_names(trace_path: str) -> set[str]:
    """Return the set of tool names invoked (one per span, deduplicated)."""
    return {span["name"] for span in _read_spans(trace_path, kind="tool")}


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
            if (
                isinstance(current, (tuple, list, dict))
                or hasattr(current, "__getitem__")
            ):
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
