"""CLI entry for the gethired eval framework.

Usage::

    gethired-eval                       # run all tasks, 1 trial each
    gethired-eval --category parser     # run parser tasks only
    gethired-eval --trials 3            # run each task 3 times for pass@k metrics
    gethired-eval --model MiniMax-M3    # set the model for LLM-based tasks
"""

from __future__ import annotations

import os
from pathlib import Path

import typer

from evals.harness import EvalHarness, GraderRegistry, load_suite


def run(
    tasks_dir: Path = typer.Option(Path("evals"), "--tasks", "-t"),
    category: str | None = typer.Option(None, "--category", "-c"),
    trials: int = typer.Option(1, "--trials", "-n"),
    model: str | None = typer.Option(None, "--model", "-m"),
    suite_name: str = typer.Option("default", "--suite", "-s"),
) -> None:
    """Run the eval suite and write a markdown + JSON report."""
    if not tasks_dir.exists():
        typer.echo(f"Tasks directory not found: {tasks_dir}", err=True)
        raise typer.Exit(code=1)

    suite = load_suite(tasks_dir)
    if category:
        suite = tuple(t for t in suite if t.category == category)

    if not suite:
        typer.echo("No tasks found (or matched by filter).", err=True)
        raise typer.Exit(code=1)

    if model:
        os.environ["MODEL"] = model

    harness = EvalHarness(
        suite_name=suite_name,
        registry=GraderRegistry(),
        trials_per_task=trials,
        output_dir=Path("evals/results"),
    )

    typer.echo(
        f"Running {len(suite)} task(s) × {trials} trial(s) "
        f"in category={category or 'all'}"
    )
    result = harness.run_suite(suite)
    typer.echo(result.to_markdown())


def main() -> None:
    typer.run(run)


if __name__ == "__main__":
    main()

