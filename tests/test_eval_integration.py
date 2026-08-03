"""Integration test: exercise the harness end-to-end with the deepeval-style graders."""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.graders.registry import GraderRegistry
from evals.harness import EvalHarness, load_suite


def test_harness_runs_writer_tasks_with_deepeval_graders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The eval harness must execute the writer YAML suite and score the
    new deepeval-style graders against the trace.jsonl emitted by Tailor.

    End-to-end smoke: dispatch the YAML suite, run each task once with
    TestModel, then assert that the new component-level graders are
    actually present in the run output (even if they fail with no tool
    spans in the test mode).
    """
    monkeypatch.setenv("LATEX_ENGINE", "none")
    monkeypatch.setenv("EVAL_TRACE_DIR", str(tmp_path / "traces"))

    suite_dir = Path("evals")
    tasks = load_suite(suite_dir)
    writer_tasks = tuple(t for t in tasks if t.category == "writer")
    assert writer_tasks, "no writer tasks loaded"

    registry = GraderRegistry()
    # Verify the new graders are registered.
    for new_grader in (
        "code.tool_correctness",
        "code.argument_correctness",
        "code.plan_quality",
        "code.plan_adherence",
        "code.step_efficiency",
        "code.task_completion",
    ):
        assert new_grader in registry, f"{new_grader} not registered"

    # The new graders must appear in the writer suite at least once.
    suite_grader_names = {g.name for t in writer_tasks for g in t.graders}
    for new_grader in (
        "code.tool_correctness",
        "code.argument_correctness",
        "code.step_efficiency",
    ):
        assert new_grader in suite_grader_names, f"{new_grader} not present in any writer task"

    harness = EvalHarness(
        suite_name="integration_smoke",
        registry=registry,
        trials_per_task=1,
        output_dir=tmp_path / "results",
    )
    result = harness.run_suite(writer_tasks)

    # Every writer task should have run (1 trial each).
    assert len(result.task_outcomes) == len(writer_tasks)
    for outcome in result.task_outcomes:
        assert outcome.trials, f"{outcome.task_id} produced no trials"
        # The new graders that the YAML declared for this task must
        # appear in trial grader_results.
        declared = {
            g.name for g in next(t for t in writer_tasks if t.id == outcome.task_id).graders
        }
        grader_names = {gr.name for trial in outcome.trials for gr in trial.grader_results}
        for required in declared & {
            "code.tool_correctness",
            "code.argument_correctness",
            "code.step_efficiency",
        }:
            assert required in grader_names, (
                f"{outcome.task_id} declared {required} but did not run it"
            )
