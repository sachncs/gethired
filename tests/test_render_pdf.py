"""Tests for the PDF compiler module."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from gethired.constants import LATEX_ENGINE_ENV_VAR, PDFLATEX_BINARY, TECTONIC_BINARY
from gethired.exceptions import PdfCompilationError
from gethired.render_pdf import compile_pdf


def test_compile_pdf_uses_tectonic_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When LATEX_ENGINE is unset and tectonic is on PATH, tectonic is invoked."""
    monkeypatch.delenv(LATEX_ENGINE_ENV_VAR, raising=False)
    fake_binary = tmp_path / "tectonic"
    fake_binary.write_text("#!/bin/sh\ntouch \"$2.pdf\"\n")
    fake_binary.chmod(0o755)
    with patch("shutil.which", return_value=str(fake_binary)):
        with patch("subprocess.run") as run_mock:
            def fake_run(cmd, **_kwargs):
                out = Path(cmd[1])
                out.with_suffix(".pdf").write_bytes(b"%PDF-1.4 fake")
                return None

            run_mock.side_effect = fake_run
            tex = r"\documentclass{article}\begin{document}hi\end{document}"
            result = compile_pdf(tex, tmp_path)
    assert result.suffix == ".pdf"
    assert result.exists()


def test_compile_pdf_falls_back_to_pdflatex_when_env_var_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Setting LATEX_ENGINE=pdflatex selects pdflatex binary."""
    monkeypatch.setenv(LATEX_ENGINE_ENV_VAR, PDFLATEX_BINARY)
    with patch("shutil.which", return_value="/usr/bin/pdflatex"):
        with patch("subprocess.run") as run_mock:
            def fake_run(cmd, **_kwargs):
                Path(cmd[1]).with_suffix(".pdf").write_bytes(b"%PDF-1.4 fake")
                return None

            run_mock.side_effect = fake_run
            tex = r"\documentclass{article}\begin{document}hi\end{document}"
            result = compile_pdf(tex, tmp_path)
    assert result.suffix == ".pdf"


def test_compile_pdf_raises_when_engine_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing LaTeX engine raises PdfCompilationError with installation hint."""
    monkeypatch.delenv(LATEX_ENGINE_ENV_VAR, raising=False)
    with patch("shutil.which", return_value=None):
        with pytest.raises(PdfCompilationError, match=TECTONIC_BINARY):
            compile_pdf("body", tmp_path)


def test_compile_pdf_raises_on_engine_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-zero engine exit raises PdfCompilationError with stderr snippet."""
    monkeypatch.delenv(LATEX_ENGINE_ENV_VAR, raising=False)
    import subprocess

    err = subprocess.CalledProcessError(
        returncode=1, cmd=["tectonic"], stderr=b"! Undefined control sequence."
    )
    with patch("shutil.which", return_value="/usr/bin/tectonic"):
        with patch("subprocess.run", side_effect=err):
            with pytest.raises(PdfCompilationError, match="Undefined control sequence"):
                compile_pdf("body", tmp_path)


def test_compile_pdf_raises_on_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Subprocess timeout is wrapped in PdfCompilationError."""
    import subprocess

    monkeypatch.delenv(LATEX_ENGINE_ENV_VAR, raising=False)
    err = subprocess.TimeoutExpired(cmd=["tectonic"], timeout=60)
    with patch("shutil.which", return_value="/usr/bin/tectonic"):
        with patch("subprocess.run", side_effect=err):
            with pytest.raises(PdfCompilationError, match="timed out"):
                compile_pdf("body", tmp_path)