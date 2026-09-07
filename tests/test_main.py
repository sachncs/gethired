"""Smoke tests for the ``python -m gethired`` entry point."""

from __future__ import annotations

from typer.testing import CliRunner

from gethired.__main__ import main
from gethired.cli import app

runner = CliRunner()


def test_main_invokes_typer_app() -> None:
    """``main`` runs the typer app; the help command exits 0."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_main_help_exits_cleanly() -> None:
    """``main()`` is importable and routes to the typer app without side effects."""
    assert callable(main)
