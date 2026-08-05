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
    COMPILE_TIMEOUT,
    LATEX_VAR,
    PDFLATEX,
    TECTONIC,
)
from gethired.exceptions import CompileError


def compile_pdf(tex_source: str, output_dir: Path) -> Path | None:
    """Compile ``tex_source`` into a PDF in ``output_dir``.

    Selects the engine from the ``LATEX_ENGINE`` env var. Default is
    ``tectonic``; ``pdflatex`` is the alternative. Set ``LATEX_ENGINE=none``
    to skip compilation entirely (useful for tests and offline runs).

    Args:
        tex_source: The rendered LaTeX source.
        output_dir: Directory where the ``.tex`` and ``.pdf`` are written.

    Returns:
        Path to the compiled ``.pdf`` file, or ``None`` when the engine is
        intentionally disabled via ``LATEX_ENGINE=none``.

    Raises:
        CompileError: When the chosen engine is missing, exits
            non-zero, or exceeds ``COMPILE_TIMEOUT``.
    """
    engine = os.environ.get(LATEX_VAR, TECTONIC)
    if engine == "none":
        return None
    binary = TECTONIC if engine == TECTONIC else PDFLATEX
    binary_path = shutil.which(binary)
    if binary_path is None:
        raise CompileError(
            f"LaTeX engine '{binary}' not found on PATH. "
            f"Install tectonic (https://tectonic-typesetting.github.io/) "
            f"or set LATEX_ENGINE=none to skip compilation."
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    tex_path = output_dir / "tailored.tex"
    tex_path.write_text(tex_source)
    result = subprocess.run(
        [binary_path, "-interaction=nonstopmode", str(tex_path)],
        cwd=output_dir,
        check=False,
        capture_output=True,
        timeout=COMPILE_TIMEOUT,
    )
    pdf_path = tex_path.with_suffix(".pdf")
    if not pdf_path.exists():
        raise CompileError(
            f"{binary} failed (exit {result.returncode}). "
            f"stderr: {result.stderr.decode(errors='replace')[-500:]}"
        )
    return pdf_path


__all__ = ["compile_pdf"]
