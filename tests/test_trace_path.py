"""Tests for trace_path plumbing through the eval runner + resolvers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from evals.harness import GraderSpec, TaskDefinition, resolve_args, tailor_runner
from gethired.models import (
    Contact,
    Skills,
    Tailored,
)


def _build_task(graders: list[GraderSpec], **overrides: Any) -> TaskDefinition:
    """Helper to assemble a TaskDefinition with sensible defaults."""
    base: dict[str, Any] = {
        "id": "test-task",
        "desc": "test",
        "category": "tailor",
        "type": "tailor",
        "input": {
            "__master__": None,
            "use_test_model": True,
            "jd_text": "x",
            "jd_title": "x",
        },
        "graders": graders,
    }
    base["input"].update(overrides.pop("input", {}))
    base.update(overrides)
    return TaskDefinition(**base)


def test_resolve_args_recognises_trace_path_placeholder(tmp_path: Path) -> None:
    """resolve_args maps the literal ``$trace_path`` to output['trace_path']."""
    spec_args = {"trace_path": "$trace_path", "name": "x"}
    output = {"trace_path": str(tmp_path / "trace.jsonl")}
    task = _build_task([])
    resolved = resolve_args(spec_args, output, task)
    assert resolved == {"trace_path": str(tmp_path / "trace.jsonl")}


def test_resolve_args_strips_name_placeholder() -> None:
    """The reserved ``name`` key never reaches the grader call."""
    spec_args = {"name": "display-label", "text": "$text"}
    output = {"text": "hello"}
    task = _build_task([])
    resolved = resolve_args(spec_args, output, task)
    assert "name" not in resolved
    assert resolved == {"text": "hello"}


def test_resolve_args_passes_lit_through_unchanged() -> None:
    """Non-string and non-prefixed values are passed through verbatim."""
    spec_args = {"max_tool_calls": 6, "expected_tools": ["skills"], "name": "x"}
    output: dict[str, Any] = {"trace_path": "ignored"}
    task = _build_task([])
    resolved = resolve_args(spec_args, output, task)
    assert resolved["max_tool_calls"] == 6
    assert resolved["expected_tools"] == ["skills"]


def test_resolve_args_returns_none_for_unknown_placeholder() -> None:
    """Unknown placeholders resolve to None (fail-fast via grader)."""
    spec_args = {"trace_path": "$does_not_exist"}
    output: dict[str, Any] = {"trace_path": "real/path"}
    task = _build_task([])
    resolved = resolve_args(spec_args, output, task)
    assert resolved["trace_path"] is None


def test_yaml_writer_tasks_announce_expected_tools() -> None:
    """Every writer/* YAML carries expected_tools + trace_path graders."""
    task_files = sorted(Path("evals/tasks/writer").glob("*.yaml"))
    assert task_files, "no writer tasks found"
    for path in task_files:
        payload = yaml.safe_load(path.read_text())
        graders = payload["task"]["graders"]
        grader_names = {g["name"] for g in graders}
        assert "code.tool_correctness" in grader_names, f"{path.name} missing code.tool_correctness"
        assert "code.argument_correctness" in grader_names, (
            f"{path.name} missing code.argument_correctness"
        )
        # Every code.tool_correctness grader must reference $trace_path.
        for g in graders:
            if g["name"] == "code.tool_correctness":
                assert "trace_path" in g["args"], (
                    f"{path.name} code.tool_correctness missing trace_path arg"
                )
                assert g["args"]["trace_path"] == "$trace_path"


def test_yaml_tailor_tasks_include_plan_graders() -> None:
    """Every tailor/* YAML carries the three deepeval-style graders."""
    task_files = sorted(Path("evals/tasks/tailor").glob("*.yaml"))
    assert task_files, "no tailor tasks found"
    for path in task_files:
        payload = yaml.safe_load(path.read_text())
        graders = payload["task"]["graders"]
        grader_names = {g["name"] for g in graders}
        assert "code.task_completion" in grader_names, f"{path.name} missing code.task_completion"
        assert "code.tool_correctness" in grader_names, f"{path.name} missing code.tool_correctness"
        assert "code.step_efficiency" in grader_names, f"{path.name} missing code.step_efficiency"


def test_tailor_runner_surfaces_trace_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The tailor runner must surface trace_path through output and metrics."""
    trace_dir = tmp_path

    class _Stub:
        def __init__(self, **_: Any) -> None:
            self.tailored_dir = trace_dir

        def run(self) -> Any:
            return Tailored(
                contact=Contact("x", "x", "x", "x", None, None),
                summary="x",
                skills=Skills(categories={}),
                experience=(),
                projects=(),
                education=(),
                awards=(),
                dropped=(),
                rationale="x",
                grounding=(),
                jobs=(),
            )

    monkeypatch.setattr("evals.harness.Tailor", _Stub)

    # Pre-create a fake trace.jsonl in the expected location so we can
    # verify the runner reports a real path back to the grader.
    fake_trace = trace_dir / "fake-run" / "trace.jsonl"
    fake_trace.parent.mkdir(parents=True, exist_ok=True)
    fake_trace.write_text(
        json.dumps(
            {
                "name": "tailor.run",
                "kind": "agent",
                "started_at": "x",
                "ended_at": "x",
                "duration_ms": 0.0,
                "attributes": {},
                "parent_id": None,
                "span_id": "x",
            }
        )
        + "\n"
    )

    task = _build_task(
        [],
        input={
            "__master__": None,
            "use_test_model": True,
            "jd_text": "Need Python engineer.",
            "jd_title": "Senior Python Engineer",
            "jd_company": "Acme",
            "must_have_keywords": ["python"],
            "trace_dir": str(trace_dir),
        },
    )
    output, metrics = tailor_runner(task)
    assert "trace_path" in output
    assert "trace_path" in metrics
    assert output["trace_path"] == metrics["trace_path"]
    surfaced = Path(output["trace_path"])
    # The surfaced path should point inside the configured trace_dir
    # (the actual trace.jsonl is written by the real Tailor; the stub
    # doesn't invoke the tracer).
    assert surfaced.parent.parent == trace_dir
    assert surfaced.name == "trace.jsonl"
