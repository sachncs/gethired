"""Tests for the eval framework itself (harness, graders, registry)."""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.graders.code import (
    GraderResult,
    code_equal,
    code_field_length,
    code_field_present,
    code_json_round_trip,
    code_no_banned_words,
    code_no_jd_plagiarism,
    code_numbers_in_master,
    code_text_contains,
    code_text_not_contains,
)
from evals.graders.registry import GraderRegistry
from evals.harness import (
    EvalHarness,
    load_suite,
    load_task,
)
from gethired.models import Resume, Skills

# ---------------------------------------------------------------------------
# Grader tests
# ---------------------------------------------------------------------------


def test_code_equal_passes_on_match() -> None:
    result = code_equal("test", "value", "value")
    assert result.passed
    assert result.detail == "values match"


def test_code_equal_fails_on_mismatch() -> None:
    result = code_equal("test", "a", "b")
    assert not result.passed
    assert "expected" in result.detail


def test_code_field_present_on_dataclass() -> None:
    """``_resolve_path`` supports dotted paths on dataclasses."""
    contact = Resume(
        name="Placeholder Name",
        city="Test City",
        phone="5555550100",
        email="placeholder@example.com",
        github=None,
        linkedin=None,
    )
    result = code_field_present("test", resume=contact, path="name")
    assert result.passed
    assert "Placeholder Name" in result.detail


def test_code_field_present_on_dict() -> None:
    """``_resolve_path`` supports dict access for runner outputs."""
    result = code_field_present("test", resume={"name": "x"}, path="name")
    assert result.passed


def test_code_field_present_missing_returns_false() -> None:
    result = code_field_present("test", resume={"other": "x"}, path="missing")
    assert not result.passed
    assert "<missing>" in result.detail


def test_code_field_length_correct_count() -> None:
    contact = Resume(
        name="A",
        city="X",
        phone="0",
        email="a@b.c",
        github=None,
        linkedin=None,
    )
    result = code_field_length("test", resume=contact, path="name", expected=1)
    assert result.passed


def test_code_field_length_wrong_count() -> None:
    contact = Resume(
        name="AB",
        city="X",
        phone="0",
        email="a@b.c",
        github=None,
        linkedin=None,
    )
    result = code_field_length("test", resume=contact, path="name", expected=1)
    assert not result.passed


def test_code_text_contains_case_insensitive() -> None:
    result = code_text_contains("test", text="Hello World", substring="world")
    assert result.passed


def test_code_text_contains_case_sensitive() -> None:
    result = code_text_contains(
        "test", text="Hello World", substring="WORLD", case_insensitive=False
    )
    assert not result.passed


def test_code_text_not_contains() -> None:
    result = code_text_not_contains("test", text="Hello World", forbidden="Python")
    assert result.passed
    result2 = code_text_not_contains("test", text="Hello Python World", forbidden="python")
    assert not result2.passed


def test_code_no_banned_words_empty_set() -> None:
    result = code_no_banned_words("test", text="Hello World", banned=frozenset())
    assert result.passed


def test_code_no_banned_words_detects_banned() -> None:
    result = code_no_banned_words(
        "test", text="We leverage Python for ML.", banned=frozenset({"leverage"})
    )
    assert not result.passed
    assert "leverage" in result.detail


def test_code_no_jd_plagiarism_no_overlap() -> None:
    result = code_no_jd_plagiarism(
        "test",
        tailored_text="Built Kubernetes platforms",
        jd_text="Hire senior developer",
    )
    assert result.passed


def test_code_no_jd_plagiarism_detects_5gram() -> None:
    jd = "designed and deployed isolated ai platforms for enterprise customers"
    tailored = "We designed and deployed isolated ai platforms for enterprise customers today"
    result = code_no_jd_plagiarism("test", tailored_text=tailored, jd_text=jd)
    assert not result.passed


def test_code_numbers_in_master_no_invention() -> None:
    master = Master(
        contact=Resume(
            name="A",
            city="X",
            phone="0",
            email="a@b.c",
            github=None,
            linkedin=None,
        ),
        summary="Engineer",
        skills=Skills(categories={}),
        experience=(),
        projects=(),
        education=(),
        awards=(),
    )
    tailored_text = "Built with 10000 requests"
    result = code_numbers_in_master("test", tailored_text=tailored_text, master=master)
    assert not result.passed
    assert "10000" in result.detail


def test_code_numbers_in_master_passes_when_present() -> None:
    master = Master(
        contact=Resume(
            name="A",
            city="X",
            phone="0",
            email="a@b.c",
            github=None,
            linkedin=None,
        ),
        summary="Built 10000 requests",
        skills=Skills(categories={}),
        experience=(),
        projects=(),
        education=(),
        awards=(),
    )
    result = code_numbers_in_master("test", tailored_text="Built 10000 requests", master=master)
    assert result.passed


def test_code_json_round_trip() -> None:
    master = Master(
        contact=Resume(
            name="A",
            city="X",
            phone="0",
            email="a@b.c",
            github=None,
            linkedin=None,
        ),
        summary="Engineer",
        skills=Skills(categories={"Programming": ("Python",)}),
        experience=(),
        projects=(),
        education=(),
        awards=(),
    )
    result = code_json_round_trip("test", tailored=master)
    assert result.passed


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


def test_registry_contains_builtins() -> None:
    r = GraderRegistry()
    for name in (
        "code.equal",
        "code.field_present",
        "code.field_length",
        "code.text_contains",
        "code.text_not_contains",
        "code.no_banned_words",
        "code.no_jd_plagiarism",
        "code.numbers_in_master",
        "code.json_round_trip",
    ):
        assert name in r


def test_registry_lookup_unknown_raises() -> None:
    r = GraderRegistry()
    with pytest.raises(KeyError, match="Unknown grader"):
        r.get("nonexistent.grader")


def test_registry_register_custom() -> None:
    r = GraderRegistry()

    def my_grader(name, **kwargs):
        return GraderResult(name=name, passed=True, detail="ok")

    r.register("custom.grader", my_grader)
    assert "custom.grader" in r


# ---------------------------------------------------------------------------
# Task loading tests
# ---------------------------------------------------------------------------


def test_load_task_with_task_wrapper(tmp_path: Path) -> None:
    task_file = tmp_path / "test.yaml"
    task_file.write_text(
        """
task:
  id: test_001
  desc: test description
  category: parser
  type: code
  input:
    foo: bar
  graders:
    - name: code.equal
      args:
        name: x
        actual: 1
        expected: 1
  tags: [regression]
"""
    )
    task = load_task(task_file)
    assert task.id == "test_001"
    assert task.category == "parser"
    assert task.type == "code"
    assert task.input == {"foo": "bar"}
    assert len(task.graders) == 1
    assert task.is_regression
    assert not task.is_capability


def test_load_task_with_flat_structure(tmp_path: Path) -> None:
    task_file = tmp_path / "test.yaml"
    task_file.write_text(
        """
id: flat_001
desc: flat
category: writer
type: writer
"""
    )
    task = load_task(task_file)
    assert task.id == "flat_001"
    assert task.category == "writer"


def test_load_suite_loads_all_yaml(tmp_path: Path) -> None:
    (tmp_path / "tasks" / "parser").mkdir(parents=True)
    (tmp_path / "tasks" / "writer").mkdir(parents=True)
    (tmp_path / "tasks" / "parser" / "a.yaml").write_text("id: a\ncategory: parser\ntype: code\n")
    (tmp_path / "tasks" / "writer" / "b.yaml").write_text("id: b\ncategory: writer\ntype: code\n")
    suite = load_suite(tmp_path)
    assert len(suite) == 2
    assert {t.id for t in suite} == {"a", "b"}


# ---------------------------------------------------------------------------
# Harness execution test (uses a tiny synthetic task)
# ---------------------------------------------------------------------------


def test_eval_harness_runs_and_aggregates(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "test.yaml").write_text(
        """
task:
  id: simple_001
  desc: simple grader test
  category: parser
  type: code
  input:
    __output__:
      text: hello world
  graders:
    - name: code.text_contains
      args:
        name: has_hello
        text: hello world
        substring: hello
"""
    )

    harness = EvalHarness(
        suite_name="test",
        output_dir=tmp_path / "results",
        trials_per_task=1,
    )
    suite = load_suite(tmp_path)
    result = harness.run_suite(suite)

    assert result.n_tasks == 1
    assert result.n_passing_tasks == 1
    assert result.pass_rate == 1.0


def test_eval_harness_records_metrics(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "metric.yaml").write_text(
        """
task:
  id: metric_001
  category: parser
  type: code
  input:
    __output__: {}
  graders:
    - name: code.equal
      args: {name: x, actual: 1, expected: 1}
"""
    )
    harness = EvalHarness(suite_name="metric", output_dir=tmp_path / "results")
    result = harness.run_suite(load_suite(tmp_path))
    assert result.task_outcomes[0].pass_at_1 == 1.0
    assert result.task_outcomes[0].pass_at_k == 1.0
    assert result.task_outcomes[0].avg_duration_ms >= 0
