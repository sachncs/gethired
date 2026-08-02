"""PDF compiler: shell out to tectonic (with pdflatex fallback).

The ATS gates ``PDF_COMPILES``, ``PDF_TEXT_EXTRACTABLE``, ``PDF_TEXT_MATCHES_TXT``
all depend on a compiled PDF. This module owns that side effect.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from gethired.constants import (
    LATEX_ENGINE_ENV_VAR,
    PDF_COMPILE_TIMEOUT_SECONDS,
    PDFLATEX_BINARY,
    TECTONIC_BINARY,
)
from gethired.exceptions import PdfCompilationError


def compile_pdf(tex_source: str, output_dir: Path) -> Path:
    """Compile ``tex_source`` into a PDF in ``output_dir``.

    Selects the engine from the ``LATEX_ENGINE`` env var (default
    ``tectonic``) and falls back to ``pdflatex`` when set explicitly.
    Raises ``PdfCompilationError`` when the engine is missing or exits non-zero.

    Args:
        tex_source: The rendered LaTeX source.
        output_dir: Directory where the ``.tex`` and ``.pdf`` are written.

    Returns:
        Path to the compiled ``.pdf`` file.

    Raises:
        PdfCompilationError: If the chosen engine is missing or exits non-zero.
    """
    engine = os.environ.get(LATEX_ENGINE_ENV_VAR, TECTONIC_BINARY)
    binary = TECTONIC_BINARY if engine == TECTONIC_BINARY else PDFLATEX_BINARY
    binary_path = shutil.which(binary)
    if binary_path is None:
        raise PdfCompilationError(
            f"LaTeX engine '{binary}' not found on PATH. "
            f"Install tectonic (https://tectonic-typesetting.github.io/) "
            f"or set LATEX_ENGINE=pdflatex."
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    tex_path = output_dir / "tailored.tex"
    tex_path.write_text(tex_source)
    try:
        subprocess.run(
            [binary_path, str(tex_path)],
            cwd=output_dir,
            check=True,
            capture_output=True,
            timeout=PDF_COMPILE_TIMEOUT_SECONDS,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode() if exc.stderr else ""
        raise PdfCompilationError(
            f"{binary} failed with code {exc.returncode}: {stderr}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise PdfCompilationError(
            f"{binary} timed out after {PDF_COMPILE_TIMEOUT_SECONDS}s"
        ) from exc
    return tex_path.with_suffix(".pdf")


__all__ = ["compile_pdf"]
