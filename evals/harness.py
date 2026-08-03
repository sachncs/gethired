"""Eval harness — runs tasks, records trials, aggregates results.

Implements the eval-loop pattern from Anthropic's "Demystifying evals
for AI agents":

  task → trial × N → transcript + graders → outcome
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic_ai.models.test import TestModel

from evals.graders.registry import GraderRegistry
from gethired.description import Analysis, analyze

# Backwards-compatible exception aliases (pre-0.4.0 import paths)
from gethired.fetcher import CacheEntry
from gethired.models import (
    Outcome,
    Job,
    Master,
    Run,
    RunResult,
    Tailored,
)
from gethired.parser import parse_tex as tex
from gethired.profiler import build as build_profile
from gethired.tailor import Tailor, load_master
from gethired.validator import (
    grounding,
    plagiarism,
    style,
)
from gethired.writer import Writer

# ---------------------------------------------------------------------------
# Task + Trial types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GraderSpec:
    """A single grader reference resolved at run time."""

    name: str                                # e.g. "code.field_present"
    args: dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0
    required: bool = True                    # required=True → task fails if this fails


@dataclass(frozen=True, slots=True)
class TaskDefinition:
    """A single eval task loaded from YAML."""

    id: str
    desc: str
    category: str                           # parser / fetcher / writer / etc.
    type: str                               # "code" | "model" | "outcome"
    input: dict[str, Any] = field(default_factory=dict)
    graders: tuple[GraderSpec, ...] = field(default_factory=tuple)
    tracked_metrics: tuple[str, ...] = field(default_factory=tuple)
    reference_solution: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_capability(self) -> bool:
        """Capability evals start low; regression evals stay near 100%."""
        return "capability" in self.tags

    @property
    def is_regression(self) -> bool:
        return "regression" in self.tags


@dataclass(frozen=True, slots=True)
class GraderResultRecord:
    """Result of running a single grader on a single trial."""

    name: str
    passed: bool
    detail: str
    score: float


@dataclass(frozen=True, slots=True)
class TrialRecord:
    """A single trial (one attempt at a task)."""

    task_id: str
    trial_index: int
    started_at: str
    completed_at: str
    duration_ms: float
    grader_results: tuple[GraderResultRecord, ...]
    transcript: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """A trial passes when all required graders pass."""
        return all(r.passed for r in self.grader_results)


@dataclass(frozen=True, slots=True)
class TaskOutcome:
    """Aggregated outcome across all trials of a task."""

    task_id: str
    category: str
    trials: tuple[TrialRecord, ...]
    pass_count: int
    pass_rate: float
    pass_at_1: float
    pass_at_k: float
    avg_duration_ms: float

    @property
    def passed(self) -> bool:
        return self.pass_count > 0


@dataclass(frozen=True, slots=True)
class EvalSuiteResult:
    """Aggregated outcome across a whole suite."""

    suite_name: str
    started_at: str
    completed_at: str
    task_outcomes: tuple[TaskOutcome, ...]

    @property
    def pass_rate(self) -> float:
        if not self.task_outcomes:
            return 0.0
        return sum(t.pass_rate for t in self.task_outcomes) / len(self.task_outcomes)

    @property
    def n_tasks(self) -> int:
        return len(self.task_outcomes)

    @property
    def n_passing_tasks(self) -> int:
        return sum(1 for t in self.task_outcomes if t.passed)

    @property
    def n_trials(self) -> int:
        return sum(len(t.trials) for t in self.task_outcomes)

    def to_markdown(self) -> str:
        lines: list[str] = []
        lines.append(f"# Eval suite: {self.suite_name}")
        lines.append("")
        lines.append(f"- Started: {self.started_at}")
        lines.append(f"- Completed: {self.completed_at}")
        lines.append(f"- Tasks: {self.n_tasks} ({self.n_passing_tasks} passing)")
        lines.append(f"- Trials: {self.n_trials}")
        lines.append(f"- Overall pass-rate: {self.pass_rate:.0%}")
        lines.append("")
        lines.append("## Per-task results")
        lines.append("")
        lines.append("| task | category | pass-rate | pass@1 | pass^k | avg ms |")
        lines.append("|------|----------|-----------|--------|--------|--------|")
        for outcome in self.task_outcomes:
            lines.append(
                f"| `{outcome.task_id}` | {outcome.category} "
                f"| {outcome.pass_rate:.0%} | {outcome.pass_at_1:.0%} | {outcome.pass_at_k:.0%} "
                f"| {outcome.avg_duration_ms:.1f} |"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Task loader
# ---------------------------------------------------------------------------


def load_task(path: Path) -> TaskDefinition:
    """Load a single task definition from a YAML file."""
    data = yaml.safe_load(path.read_text())
    return parse_task(data)


def load_suite(suite_dir: Path) -> tuple[TaskDefinition, ...]:
    """Load all task definitions under ``suite_dir/tasks/**/*.yaml``."""
    tasks: list[TaskDefinition] = []
    for yaml_path in sorted(suite_dir.glob("tasks/**/*.yaml")):
        data = yaml.safe_load(yaml_path.read_text())
        tasks.append(parse_task(data))
    return tuple(tasks)


def parse_task(data: dict[str, Any]) -> TaskDefinition:
    # Accept either flat (id at root) or wrapped under `task:` key.
    task_data = data.get("task", data)
    graders: list[GraderSpec] = []
    for grader in task_data.get("graders", []):
        graders.append(
            GraderSpec(
                name=grader["name"],
                args=grader.get("args", {}),
                weight=float(grader.get("weight", 1.0)),
                required=bool(grader.get("required", True)),
            )
        )
    return TaskDefinition(
        id=str(task_data["id"]),
        desc=str(task_data.get("desc", "")),
        category=str(task_data.get("category", "")),
        type=str(task_data.get("type", "code")),
        input=task_data.get("input", {}),
        graders=tuple(graders),
        tracked_metrics=tuple(task_data.get("tracked_metrics", ())),
        reference_solution=task_data.get("reference_solution"),
        tags=tuple(task_data.get("tags", ())),
    )


# ---------------------------------------------------------------------------
# Eval harness
# ---------------------------------------------------------------------------


@dataclass
class EvalHarness:
    """Runs a list of tasks multiple times and aggregates results.

    Per Anthropic's article: run multiple trials per task to handle
    non-determinism; report both pass@k (any success) and pass^k
    (all-success) metrics.
    """

    suite_name: str
    registry: GraderRegistry = field(default_factory=GraderRegistry)
    trials_per_task: int = 1
    output_dir: Path = field(default_factory=lambda: Path("evals/results"))

    def run_suite(self, tasks: tuple[TaskDefinition, ...]) -> EvalSuiteResult:
        """Run every task ``trials_per_task`` times and aggregate."""
        started = now()
        outcomes: list[TaskOutcome] = []
        for task in tasks:
            outcome = self._run_task(task)
            outcomes.append(outcome)
        completed = now()
        result = EvalSuiteResult(
            suite_name=self.suite_name,
            started_at=started,
            completed_at=completed,
            task_outcomes=tuple(outcomes),
        )
        self._write_report(result)
        return result

    def _run_task(self, task: TaskDefinition) -> TaskOutcome:
        shared_master = load_shared_master()
        trials: list[TrialRecord] = []
        for trial_index in range(self.trials_per_task):
            trial = self._execute_trial(task, trial_index, shared_master)
            trials.append(trial)
        return aggregate_task(task.id, task.category, tuple(trials))

    def _execute_trial(
        self,
        task: TaskDefinition,
        trial_index: int,
        shared_master: Master | None = None,
    ) -> TrialRecord:
        """Run the task once, grade the output, record the trial."""
        started = now()
        runner = REGISTRY.get(task.type, passthrough_runner)
        if shared_master is not None:
            task = inject_master(task, shared_master)
        output, transcript = runner(task)
        completed = now()
        started_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
        completed_dt = datetime.fromisoformat(completed.replace("Z", "+00:00"))
        duration_ms = (completed_dt - started_dt).total_seconds() * 1000.0

        grader_results: list[GraderResultRecord] = []
        for spec in task.graders:
            grader = self.registry.get(spec.name)
            try:
                resolved_args = resolve_args(spec.args, output, task, shared_master)
                # Grader signature uses the first positional arg for the
                # human-readable name; everything else comes from spec.args.
                result = grader(spec.name, **resolved_args)
                grader_results.append(
                    GraderResultRecord(
                        name=result.name,
                        passed=result.passed,
                        detail=result.detail,
                        score=getattr(result, "score", 1.0 if result.passed else 0.0),
                    )
                )
            except Exception as exc:
                grader_results.append(
                    GraderResultRecord(
                        name=spec.name,
                        passed=False,
                        detail=f"grader raised {type(exc).__name__}: {exc}",
                        score=0.0,
                    )
                )

        return TrialRecord(
            task_id=task.id,
            trial_index=trial_index,
            started_at=started,
            completed_at=completed,
            duration_ms=duration_ms,
            grader_results=tuple(grader_results),
            transcript={**transcript, "category": task.category},
            metrics={},
        )

    def _write_report(self, result: EvalSuiteResult) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        report_path = self.output_dir / f"{result.suite_name}-{result.completed_at}.md"
        report_path.write_text(result.to_markdown())

        json_path = self.output_dir / f"{result.suite_name}-{result.completed_at}.json"
        json_path.write_text(
            json.dumps(
                {
                    "suite_name": result.suite_name,
                    "started_at": result.started_at,
                    "completed_at": result.completed_at,
                    "n_tasks": result.n_tasks,
                    "n_passing_tasks": result.n_passing_tasks,
                    "n_trials": result.n_trials,
                    "pass_rate": result.pass_rate,
                    "task_outcomes": [
                        {
                            "task_id": o.task_id,
                            "pass_rate": o.pass_rate,
                            "pass_at_1": o.pass_at_1,
                            "pass_at_k": o.pass_at_k,
                            "avg_duration_ms": o.avg_duration_ms,
                            "trials": [
                                {
                                    "trial_index": t.trial_index,
                                    "passed": t.passed,
                                    "duration_ms": t.duration_ms,
                                    "grader_results": [
                                        {
                                            "name": g.name,
                                            "passed": g.passed,
                                            "detail": g.detail,
                                            "score": g.score,
                                        }
                                        for g in t.grader_results
                                    ],
                                }
                                for t in o.trials
                            ],
                        }
                        for o in result.task_outcomes
                    ],
                },
                indent=2,
            )
        )


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def aggregate_task(
    task_id: str, category: str, trials: tuple[TrialRecord, ...]
) -> TaskOutcome:
    if not trials:
        return TaskOutcome(
            task_id=task_id,
            category=category,
            trials=(),
            pass_count=0,
            pass_rate=0.0,
            pass_at_1=0.0,
            pass_at_k=0.0,
            avg_duration_ms=0.0,
        )
    pass_count = sum(1 for t in trials if t.passed)
    n = len(trials)
    pass_at_1 = pass_count / n
    pass_at_k = 1.0 if pass_count == n else 0.0
    pass_rate = pass_at_1
    avg_ms = sum(t.duration_ms for t in trials) / n
    return TaskOutcome(
        task_id=task_id,
        category=category,
        trials=trials,
        pass_count=pass_count,
        pass_rate=pass_rate,
        pass_at_1=pass_at_1,
        pass_at_k=pass_at_k,
        avg_duration_ms=avg_ms,
    )


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# ---------------------------------------------------------------------------
# Argument resolution: shorthand from task YAML to grader call
# ---------------------------------------------------------------------------


def resolve_args(
    spec_args: dict[str, Any],
    output: dict[str, Any],
    task: TaskDefinition,
    shared_master: Master | None = None,
) -> dict[str, Any]:
    """Resolve special argument placeholders against the output.

    Supported placeholders:
        ``$output``       → the entire output dict
        ``$master``       → the parsed Master from the shared cache
        ``$tailored``     → the Tailored if present
        ``$text``         → the tailored text (summary + bullets joined)
        ``$jd_text``      → the Job full text
        ``$analysis``     → the Analysis object
        ``$trace_path``   → the agent trace.jsonl emitted by the runner
        ``$<key>``        → output[key] for any other output key

    The reserved key ``name`` in the YAML is treated as a display label
    and stripped before passing the rest to the grader function.
    """
    resolved: dict[str, Any] = {}
    for key, raw in spec_args.items():
        if key == "name":
            continue
        if isinstance(raw, str) and raw.startswith("$"):
            placeholder = raw[1:]
            if placeholder == "output":
                resolved[key] = output
            elif placeholder == "master":
                resolved[key] = shared_master or task.input.get("__master__")
            elif placeholder == "trace_path":
                resolved[key] = output.get("trace_path")
            elif placeholder in output:
                resolved[key] = output[placeholder]
            else:
                resolved[key] = None
        else:
            resolved[key] = raw
    return resolved


def load_shared_master() -> Master | None:
    """Load the canonical master.json (or dispatch the canonical resume.tex).

    The master is loaded once per eval run and shared across tasks so that
    every writer/critic task operates on the same source of truth.
    """
    canonical = Path("resume.tex")
    if canonical.exists():
        return tex(canonical)
    cached = Path("data/master.json")
    if cached.exists():
        return load_master(cached)
    return None


# ---------------------------------------------------------------------------
# Task runners — produce an output dict and transcript for grading
# ---------------------------------------------------------------------------


def inject_master(task: TaskDefinition, master: Master) -> TaskDefinition:
    """Return a copy of ``task`` with the shared master injected.

    Replaces the ``__load_master__`` sentinel so downstream runners
    receive the cached ``Master`` object.
    """
    new_input = dict(task.input)
    if new_input.get("__master__") == "__load_master__":
        new_input["__master__"] = master
    return TaskDefinition(
        id=task.id,
        desc=task.desc,
        category=task.category,
        type=task.type,
        input=new_input,
        graders=task.graders,
        tracked_metrics=task.tracked_metrics,
        reference_solution=task.reference_solution,
        tags=task.tags,
    )


def passthrough_runner(task: TaskDefinition) -> tuple[dict[str, Any], dict[str, Any]]:
    """Default runner: reads the output from task input verbatim.

    Used for tasks that pre-compute their own outputs.
    """
    return dict(task.input.get("__output__", {})), {"task_id": task.id}


def parser_runner(task: TaskDefinition) -> tuple[dict[str, Any], dict[str, Any]]:
    """Runner for parser tasks: dispatch a TeX file and emit the model."""
    tex_path = Path(task.input["tex_path"])
    resume = tex(tex_path)
    return (
        {
            "master": resume,
            "text": resume.to_markdown(),
            "__master__": resume,
        },
        {"task_id": task.id, "tex_path": str(tex_path)},
    )


def fetcher_runner(task: TaskDefinition) -> tuple[dict[str, Any], dict[str, Any]]:
    """Runner for fetcher tasks: dispatch cached JDs without network."""
    cache_path = Path(task.input["cache_path"])
    if not cache_path.exists():
        return ({"text": "", "jd": None}, {"error": "missing cache"})

    payload = json.loads(cache_path.read_text())
    entry = CacheEntry(
        url=payload["url"],
        url_hash=payload["url_hash"],
        content_hash=payload["content_hash"],
        fetched_at=payload["fetched_at"],
        raw_html=payload["raw_html"],
    )

    return (
        {
            "text": entry.raw_html,
            "jd": Job(
                url=entry.url,
                title="",
                company="",
                full_text=entry.raw_html,
                keywords=(),
                must_have_keywords=(),
                nice_to_have_keywords=(),
                content_hash=entry.content_hash,
            ),
        },
        {"task_id": task.id, "cache_path": str(cache_path)},
    )


def writer_runner(task: TaskDefinition) -> tuple[dict[str, Any], dict[str, Any]]:
    """Runner for writer tasks: produce a tailored resume against a JD.

    When ``task.input["deterministic"]`` is true, the runner unsets
    ``MODEL`` and ``DRAFT_MODEL`` so the writer falls back to the
    deterministic path. This makes the eval reproducible without
    requiring an LLM API call.

    When ``task.input["skip_if_deterministic"]`` is true and deterministic
    mode is on, the runner returns an empty output (signalling "not
    applicable") — used for tasks that require the LLM to be meaningful
    (e.g. plagiarism avoidance requires actual rewriting).
    """


    test_model = None
    if task.input.get("use_test_model", False):
        test_model = TestModel()
        if task.input.get("skip_if_test_model", False):
            return ({"text": "", "master": None, "tailored": None}, {"skipped": True})

    master = task.input["__master__"]
    jd = Job(
        url="eval://synthetic",
        title=task.input.get("jd_title", "Senior ML Engineer"),
        company=task.input.get("jd_company", "Eval Co"),
        full_text=task.input["jd_text"],
        keywords=tuple(task.input.get("keywords", ())),
        must_have_keywords=tuple(task.input.get("must_have_keywords", ())),
        nice_to_have_keywords=tuple(task.input.get("nice_to_have_keywords", ())),
        content_hash="eval",
    )
    analysis = Analysis(
        role=jd.title,
        seniority="senior",
        must_have_skills=jd.must_have_keywords,
        nice_to_have_skills=jd.nice_to_have_keywords,
        keywords_to_mirror=jd.must_have_keywords + jd.nice_to_have_keywords[:5],
        responsibilities=(),
        company_context=jd.company,
    )
    voice = build_profile(master)

    writer = Writer(model=task.input.get("model"), model_instance=test_model)
    tailored, jobs = writer.tailor(
        master=master, analysis=analysis, voice=voice
    )

    text = (
        tailored.summary
        + "\n"
        + "\n".join(b.text for e in tailored.experiences for b in e.bullets)
        + "\n"
        + "\n".join(b.text for p in tailored.projects for b in p.bullets)
    )
    return (
        {
            "master": master,
            "tailored": tailored,
            "text": text,
            "jd_text": jd.full_text,
            "jobs": [j.description() for j in jobs],
        },
        {"task_id": task.id, "n_jobs": len(jobs)},
    )


def critic_runner(task: TaskDefinition) -> tuple[dict[str, Any], dict[str, Any]]:
    """Runner for critic tasks: run validators against a tailored resume."""

    master = task.input["__master__"]
    tailored_dict = task.input["tailored_dict"]
    tailored = Tailored(
        contact=master.contact,
        summary=tailored_dict["summary"],
        skills=master.skills,
        experiences=master.experiences,
        projects=master.projects,
        education=master.education,
        awards=master.awards,
        dropped=(),
        rationale="",
        grounding=(),
        jobs=(),
        run_result=RunResult(
            run=Run("eval", "2026-01-01T00:00:00.000Z", "x", "y", "eval", None),
            completed_at="2026-01-01T00:00:00.000Z",
            duration_seconds=0.0,
            total_input_tokens=0,
            total_output_tokens=0,
            retry_attempts=0,
            final_outcome=Outcome.SUCCESS,
            jobs=(),
        ),
    )
    jd = Job(
        url="eval://synthetic",
        title="",
        company="",
        full_text=task.input.get("jd_text", ""),
        keywords=(),
        must_have_keywords=(),
        nice_to_have_keywords=(),
        content_hash="eval",
    )

    grounding = grounding(tailored, master)
    style = style(tailored)
    plagiarism = plagiarism(tailored, (jd,))
    return (
        {
            "master": master,
            "tailored": tailored,
            "grounding": grounding,
            "style": style,
            "plagiarism": plagiarism,
        },
        {
            "task_id": task.id,
            "n_grounding_violations": len(grounding),
            "n_style_violations": len(style),
            "n_plagiarism_violations": len(plagiarism),
        },
    )


def description_runner(task: TaskDefinition) -> tuple[dict[str, Any], dict[str, Any]]:
    """Runner for description tasks: analyze a JD."""
    jd = Job(
        url="eval://synthetic",
        title="",
        company="",
        full_text=task.input["jd_text"],
        keywords=(),
        must_have_keywords=(),
        nice_to_have_keywords=(),
        content_hash="eval",
    )
    analysis = analyze(jd)
    return (
        {"text": jd.full_text, "analysis": analysis},
        {"task_id": task.id},
    )


def tailor_runner(task: TaskDefinition) -> tuple[dict[str, Any], dict[str, Any]]:
    """Runner for end-to-end tailor tasks: full pipeline run."""
    test_model = None
    if task.input.get("use_test_model", False):
        test_model = TestModel()

    master = task.input["__master__"]
    jd = Job(
        url="eval://synthetic",
        title=task.input.get("jd_title", ""),
        company=task.input.get("jd_company", ""),
        full_text=task.input["jd_text"],
        keywords=tuple(task.input.get("keywords", ())),
        must_have_keywords=tuple(task.input.get("must_have_keywords", ())),
        nice_to_have_keywords=tuple(task.input.get("nice_to_have_keywords", ())),
        content_hash="eval",
    )
    trace_dir = Path(
        task.input.get("trace_dir") or os.environ.get("EVAL_TRACE_DIR") or "evals/traces"
    )
    trace_dir.mkdir(parents=True, exist_ok=True)
    run_id_marker = task.input.get("run_id_marker", task.id)
    # Match the real `Tracer` layout: <trace_dir>/<run_id>/trace.jsonl.
    trace_path = trace_dir / run_id_marker / "trace.jsonl"
    os.environ["GETHIRED_TRACE_PATH"] = "on"
    tailor = Tailor(
        resume=master,
        job_description=jd,
        model=task.input.get("model"),
        model_instance=test_model,
        tailored_dir=trace_dir,
    )
    tailored = tailor.run()

    text = (
        tailored.summary
        + "\n"
        + "\n".join(b.text for e in tailored.experiences for b in e.bullets)
    )
    return (
        {
            "master": master,
            "tailored": tailored,
            "text": text,
            "jobs": [j.description() for j in tailored.jobs],
            "run": tailored.run_result,
            "trace_path": str(trace_path),
        },
        {
            "task_id": task.id,
            "n_jobs": len(tailored.jobs),
            "n_grounding": len(tailored.grounding),
            "trace_path": str(trace_path),
        },
    )


REGISTRY: dict[str, Callable[[TaskDefinition], tuple[dict[str, Any], dict[str, Any]]]] = {
    "code": passthrough_runner,
    "model": passthrough_runner,
    "parser": parser_runner,
    "fetcher": fetcher_runner,
    "writer": writer_runner,
    "critic": critic_runner,
    "description": description_runner,
    "tailor": tailor_runner,
}


__all__ = [
    "EvalHarness",
    "EvalSuiteResult",
    "GraderSpec",
    "TaskDefinition",
    "TaskOutcome",
    "TrialRecord",
    "GraderResultRecord",
    "load_suite",
    "load_task",
]
