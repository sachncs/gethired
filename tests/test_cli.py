"""End-to-end CLI tests using ``typer.testing.CliRunner``.

These exercise the public command surface declared in ``gethired.cli``:
``ingest``, ``show master``, ``validate``, ``trace``, ``diff``, and the
``--help`` output. Commands that require a real LLM (``run``, ``cover``,
``plan``, ``preflight``) are covered in ``test_end_to_end.py``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gethired.cli import app
from gethired.models import Job

runner = CliRunner()


def test_help_lists_main_commands() -> None:
    """``--help`` shows the top-level help and exits cleanly."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "ingest" in result.stdout
    assert "show" in result.stdout
    assert "validate" in result.stdout
    assert "trace" in result.stdout


def test_ingest_writes_master_json(
    tmp_path: Path, resume_tex_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``ingest`` parses the TeX resume and writes a JSON snapshot."""
    out = tmp_path / "master.json"
    result = runner.invoke(app, ["ingest", str(resume_tex_path), "--out", str(out)])
    assert result.exit_code == 0, result.stderr or result.stdout
    assert out.exists()
    payload = json.loads(out.read_text())
    assert "contact" in payload
    assert "experiences" in payload


def test_show_master_prints_json(
    tmp_path: Path, resume_tex_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``show master`` reads ``data/master.json`` and prints it."""
    # First, ingest to populate the default path
    data_dir = tmp_path / "data"
    out = data_dir / "master.json"
    ingest = runner.invoke(app, ["ingest", str(resume_tex_path), "--out", str(out)])
    assert ingest.exit_code == 0

    # Move to a cwd where the default path resolves to our snapshot
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["show", "master"])
    assert result.exit_code == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert "experiences" in payload


def test_show_master_missing_file_reports_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``show master`` with no master.json exits non-zero."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["show", "master"])
    assert result.exit_code != 0
    assert "master.json not found" in (result.stderr or result.stdout)


def test_show_jd_without_url_reports_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``show jd`` without ``--url`` exits non-zero."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["show", "jd"])
    assert result.exit_code != 0
    assert "--url required" in (result.stderr or result.stdout)


def test_validate_against_tex_file_reports_unsupported(
    tmp_path: Path,
) -> None:
    """``validate <path.tex>`` exits non-zero (only JSON is supported)."""
    tex_path = tmp_path / "resume.tex"
    tex_path.write_text("\\documentclass{article}\n")
    result = runner.invoke(app, ["validate", str(tex_path)])
    assert result.exit_code != 0
    assert "tex-only validation not yet supported" in (result.stderr or result.stdout)


def test_trace_against_missing_run_dir_reports_error(tmp_path: Path) -> None:
    """``trace <run-dir>`` exits non-zero when the dir has no tailored.json."""
    result = runner.invoke(app, ["trace", str(tmp_path)])
    assert result.exit_code != 0
    assert "tailored.json not found" in (result.stderr or result.stdout)


def test_audit_against_missing_run_dir_reports_error(tmp_path: Path) -> None:
    """``audit <run-dir>`` reports the missing-file error."""
    result = runner.invoke(app, ["audit", str(tmp_path)])
    assert result.exit_code != 0
    assert "tailored.json missing" in str(result.exception)


def test_diff_against_missing_run_reports_error(tmp_path: Path) -> None:
    """``diff a b`` fails when the source files are absent."""
    tailored = tmp_path / "tailored"
    tailored.mkdir()
    result = runner.invoke(app, ["diff", "run-a", "run-b", "--out-dir", str(tailored)])
    assert result.exit_code != 0


def test_fetch_uses_jd_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``fetch <url>`` writes a JD cache entry to ``data/jd_cache``."""
    cache_dir = tmp_path / "jd_cache"
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(
        "gethired.fetcher.Fetcher.retrieve",
        lambda _self, url: _fake_jd(url),
    )

    result = runner.invoke(
        app,
        [
            "fetch",
            "https://example.com/job",
            "--cache",
            str(cache_dir),
        ],
    )
    assert result.exit_code == 0, result.stderr or result.stdout
    assert "Fetched" in (result.stdout or result.stderr)


def test_cli_loads_dotenv_at_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``cli`` calls ``dotenv.load_dotenv`` at import so ``.env`` is picked up."""
    env_file = tmp_path / ".env"
    env_file.write_text("GETHIRED_TEST_DOTENV_KEY=loaded\n")
    monkeypatch.chdir(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os, gethired.cli; "
            "print(os.environ.get('GETHIRED_TEST_DOTENV_KEY', ''))",
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )
    assert result.stdout.strip() == "loaded", (
        f".env not loaded: stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def _fake_jd(url: str) -> Job:
    return Job(
        url=url,
        title="Engineer",
        company="Acme",
        full_text="We need a Python engineer.",
        keywords=("python", "engineer"),
        must_have_keywords=("python",),
        nice_to_have_keywords=("engineer",),
        content_hash="deadbeef",
    )
