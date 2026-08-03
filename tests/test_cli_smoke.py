"""Tests for the gethired CLI surface.

These tests exercise the actual command callbacks (with consent bypassed
and the LLM replaced by a TestModel where required) so the on-disk
data process is covered: argument parsing, command dispatch, and output
artefact generation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gethired import cli as cli_module
from gethired.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _no_consent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass the consent prompt for every CLI test."""
    monkeypatch.setattr(cli_module, "ensure_consent", lambda: None)


def test_help_lists_all_commands() -> None:
    """``--help`` lists every registered command."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("ingest", "fetch", "show", "validate", "trace", "diff", "audit"):
        assert cmd in result.stdout, f"help should mention {cmd}"


def test_show_master_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``show master`` reports when master.json is absent."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["show", "master"])
    assert result.exit_code != 0
    assert "not found" in (result.stderr or result.stdout)


def test_show_master_existing_file(
    tmp_path: Path, resume_tex_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``show master`` reads the master.json that was previously ingested.

    Verifies the on-disk data process: ingest -> master.json -> show master
    round-trips the parsed master. The show command looks at a fixed
    relative path, so we change directory to the ingest target.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    out = data_dir / "master.json"
    result = runner.invoke(app, ["ingest", str(resume_tex_path), "--out", str(out)])
    assert result.exit_code == 0, result.stderr
    assert out.exists()
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        result = runner.invoke(app, ["show", "master"])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["contact"]["name"] == "Placeholder Name"
    finally:
        os.chdir(cwd)


def test_validate_requires_json(tmp_path: Path) -> None:
    """``validate`` against a non-JSON file exits non-zero."""
    tex_path = tmp_path / "resume.tex"
    tex_path.write_text("\\documentclass{article}\n")
    result = runner.invoke(app, ["validate", str(tex_path)])
    assert result.exit_code != 0
    assert "tex-only validation not yet supported" in (result.stderr or result.stdout)


def test_audit_missing_run_dir_reports_error(tmp_path: Path) -> None:
    """``audit <run-dir>`` reports the missing-file error."""
    result = runner.invoke(app, ["audit", str(tmp_path)])
    assert result.exit_code != 0
    assert "tailored.json missing" in str(result.exception)


def test_diff_with_no_run_reports_error(tmp_path: Path) -> None:
    """``diff a b`` fails when the source files are absent."""
    tailored = tmp_path / "tailored"
    tailored.mkdir()
    result = runner.invoke(app, ["diff", "run-a", "run-b", "--out-dir", str(tailored)])
    assert result.exit_code != 0
