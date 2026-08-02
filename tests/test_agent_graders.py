"""Tests for the deepeval-style agent-evaluation graders."""

from __future__ import annotations

import json
from pathlib import Path

from evals.graders.code import (
    WRITER_TOOL_NAMES,
    GraderResult,
    code_argument_correctness,
    code_plan_adherence,
    code_plan_quality,
    code_step_efficiency,
    code_task_completion,
    code_tool_correctness,
)
from gethired.models import (
    ContactInformation,
    Experience,
    SkillsByCategory,
    TailoredResume,
)


def _write_trace(path: Path, spans: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for span in spans:
            f.write(json.dumps(span) + "\n")


def _tool_span(name: str, attributes: dict | None = None) -> dict:
    return {
        "name": name,
        "kind": "tool",
        "started_at": "2026-01-01T00:00:00Z",
        "ended_at": "2026-01-01T00:00:00Z",
        "duration_ms": 1.0,
        "attributes": attributes or {},
        "parent_id": None,
        "span_id": f"id-{name}",
    }


def _agent_span(name: str) -> dict:
    return {
        "name": name,
        "kind": "agent",
        "started_at": "2026-01-01T00:00:00Z",
        "ended_at": "2026-01-01T00:00:00Z",
        "duration_ms": 1.0,
        "attributes": {},
        "parent_id": None,
        "span_id": f"id-{name}",
    }


def test_writer_tool_names_includes_all_seven_tools() -> None:
    """The documented set covers every tool registered on the Writer agent."""
    assert frozenset(
        {
            "lookup_experience",
            "lookup_project",
            "list_skills",
            "list_projects",
            "list_education",
            "list_awards",
            "read_jd_summary",
        }
    ) == WRITER_TOOL_NAMES


def test_code_tool_correctness_passes_when_expected_subset(tmp_path: Path) -> None:
    """ToolCorrectness: agent's tools cover the expected set."""
    trace = tmp_path / "trace.jsonl"
    _write_trace(
        trace,
        [
            _tool_span("list_skills", {}),
            _tool_span("list_education", {}),
            _tool_span("read_jd_summary", {}),
        ],
    )
    result = code_tool_correctness(
        "t", str(trace), expected_tools=("list_skills", "read_jd_summary")
    )
    assert result.passed is True
    assert result.score == 1.0


def test_code_tool_correctness_fails_when_missing(tmp_path: Path) -> None:
    """ToolCorrectness: missing expected tool is a fail."""
    trace = tmp_path / "trace.jsonl"
    _write_trace(trace, [_tool_span("list_skills", {})])
    result = code_tool_correctness(
        "t", str(trace), expected_tools=("list_skills", "list_education")
    )
    assert result.passed is False
    assert "list_education" in result.detail


def test_code_tool_correctness_handles_missing_trace(tmp_path: Path) -> None:
    """ToolCorrectness: missing trace file fails."""
    result = code_tool_correctness(
        "t", str(tmp_path / "nope.jsonl"), expected_tools=("list_skills",)
    )
    assert result.passed is False


def test_code_argument_correctness_passes_with_attributes(tmp_path: Path) -> None:
    """ArgumentCorrectness: tools with attributes are well-formed."""
    trace = tmp_path / "trace.jsonl"
    _write_trace(
        trace,
        [
            _tool_span("lookup_experience", {"role_or_company": "acme"}),
            _tool_span("list_skills", {}),
        ],
    )
    result = code_argument_correctness("a", str(trace))
    assert result.passed is True


def test_code_argument_correctness_fails_on_empty_attributes(tmp_path: Path) -> None:
    """ArgumentCorrectness: a tool span with no attributes is suspicious."""
    trace = tmp_path / "trace.jsonl"
    # Patch the lookup span to have empty attributes
    span = _tool_span("lookup_experience", {})
    _write_trace(trace, [span])
    code_argument_correctness("a", str(trace))
    # list_skills with no args is legitimate (returns full skills); the lookup
    # span with no args would be a fail, but here we only have list_skills
    # which is acceptable. Test with a lookup span instead.
    trace2 = tmp_path / "trace2.jsonl"
    _write_trace(trace2, [_tool_span("lookup_project", {})])
    result2 = code_argument_correctness("a", str(trace2))
    assert result2.passed is False
    assert "lookup_project" in result2.detail


def test_code_plan_adherence_flags_repeats(tmp_path: Path) -> None:
    """PlanAdherence: calling the same tool twice with the same args is a fail."""
    trace = tmp_path / "trace.jsonl"
    _write_trace(
        trace,
        [
            _tool_span("lookup_experience", {"role_or_company": "acme"}),
            _tool_span("lookup_experience", {"role_or_company": "acme"}),
        ],
    )
    result = code_plan_adherence("p", str(trace))
    assert result.passed is False
    assert "repeats" in result.detail.lower() or "repeated" in result.detail.lower()


def test_code_plan_quality_validates_first_tool(tmp_path: Path) -> None:
    """PlanQuality: agent's first tool should be a survey tool."""
    trace = tmp_path / "trace.jsonl"
    _write_trace(trace, [_tool_span("list_skills", {}), _tool_span("list_education", {})])
    result = code_plan_quality("q", str(trace), expected_first_tool="list_skills")
    assert result.passed is True


def test_code_plan_quality_fails_when_first_tool_is_deep_dive(tmp_path: Path) -> None:
    """PlanQuality: jumping straight to a deep-lookup tool is a fail."""
    trace = tmp_path / "trace.jsonl"
    _write_trace(trace, [_tool_span("lookup_experience", {"role_or_company": "acme"})])
    result = code_plan_quality("q", str(trace), expected_first_tool="list_skills")
    assert result.passed is False


def test_code_step_efficiency_counts_tool_calls(tmp_path: Path) -> None:
    """StepEfficiency: agent is over-budget if it makes too many tool calls."""
    trace = tmp_path / "trace.jsonl"
    _write_trace(trace, [_tool_span(f"tool_{i}", {}) for i in range(8)])
    result = code_step_efficiency("s", str(trace), max_tool_calls=3)
    assert result.passed is False
    assert result.score < 1.0


def test_code_step_efficiency_passes_within_budget(tmp_path: Path) -> None:
    """StepEfficiency: within-budget run is a pass with score 1.0."""
    trace = tmp_path / "trace.jsonl"
    _write_trace(trace, [_tool_span("list_skills", {}), _tool_span("list_education", {})])
    result = code_step_efficiency("s", str(trace), max_tool_calls=6)
    assert result.passed is True
    assert result.score == 1.0


def test_code_task_completion_requires_tailor_span(tmp_path: Path) -> None:
    """TaskCompletion: tailor.run span + summary + experiences required."""
    trace = tmp_path / "trace.jsonl"
    _write_trace(trace, [_agent_span("tailor.run")])
    contact = ContactInformation("a", "b", "c", "d", None, None)
    tailored = TailoredResume(
        contact=contact,
        summary="Engineer.",
        skills=SkillsByCategory(categories={}),
        experiences=(
            Experience(role="x", company="y", start_date="2020", end_date="2024", bullets=()),
        ),
        projects=(),
        education=(),
        awards=(),
        dropped=(),
        rationale="r",
        grounding=(),
        jobs=(),
    )
    result = code_task_completion("c", str(trace), tailored)
    assert result.passed is True


def test_code_task_completion_fails_when_summary_blank(tmp_path: Path) -> None:
    """TaskCompletion: blank summary is a structural failure."""
    trace = tmp_path / "trace.jsonl"
    _write_trace(trace, [_agent_span("tailor.run")])
    contact = ContactInformation("a", "b", "c", "d", None, None)
    tailored = TailoredResume(
        contact=contact,
        summary="",
        skills=SkillsByCategory(categories={}),
        experiences=(),
        projects=(),
        education=(),
        awards=(),
        dropped=(),
        rationale="r",
        grounding=(),
        jobs=(),
    )
    result = code_task_completion("c", str(trace), tailored)
    assert result.passed is False


def test_code_task_completion_fails_when_experiences_empty(tmp_path: Path) -> None:
    """TaskCompletion: missing experiences is a structural failure."""
    trace = tmp_path / "trace.jsonl"
    _write_trace(trace, [_agent_span("tailor.run")])
    contact = ContactInformation("a", "b", "c", "d", None, None)
    tailored = TailoredResume(
        contact=contact,
        summary="Engineer.",
        skills=SkillsByCategory(categories={}),
        experiences=(),
        projects=(),
        education=(),
        awards=(),
        dropped=(),
        rationale="r",
        grounding=(),
        jobs=(),
    )
    result = code_task_completion("c", str(trace), tailored)
    assert result.passed is False


def test_all_graders_return_grader_result_instance() -> None:
    """Sanity: every new grader returns a GraderResult dataclass."""
    trace = "/nonexistent/trace.jsonl"
    for grader in (
        code_tool_correctness,
        code_argument_correctness,
        code_plan_adherence,
        code_plan_quality,
        code_step_efficiency,
    ):
        result = grader("x", trace)
        assert isinstance(result, GraderResult)
