"""Shared pytest fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from gethired.constants import DATA_DIR, RESUME as RESUME_PATH
from gethired.parser import parse_tex as tex

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session", autouse=True)
def disable_pdf_compilation() -> None:
    """Set ``LATEX_ENGINE=none`` for the entire test session."""
    os.environ.setdefault("LATEX_ENGINE", "none")


@pytest.fixture(autouse=True)
def _clean_resume_cache() -> None:
    """Delete ``data/resume.json`` before each test.

    The CLI's ``Tailor.__load_resume`` short-circuits to the cached JSON when
    it exists. Real pipeline runs (``gethired run --resume ...``) overwrite it
    with whatever resume was last parsed, which would poison tests that
    expect ``sample.tex``'s placeholder data. Each test gets a clean slate
    so the parser runs from the ``.tex`` file.
    """
    cache = PROJECT_ROOT / DATA_DIR / Path(RESUME_PATH).name
    if cache.exists():
        cache.unlink()


@pytest.fixture(scope="session")
def resume_tex_path() -> Path:
    return PROJECT_ROOT / "sample.tex"


@pytest.fixture(scope="session")
def resume_tex_text(resume_tex_path: Path) -> str:
    return resume_tex_path.read_text()


@pytest.fixture(scope="session")
def resume(resume_tex_path: Path):
    """Parsed Resume from the fixture sample.tex."""
    return tex(resume_tex_path)


@pytest.fixture(scope="session")
def resume(resume_tex_path: Path):
    """Deprecated alias for :func:`resume`. Removed in Unit 11."""
    return tex(resume_tex_path)


@pytest.fixture(scope="session")
def resume_content_hash(resume) -> str:
    return resume.content_hash()


@pytest.fixture(scope="session")
def resume_content_hash(resume_content_hash: str) -> str:
    """Deprecated alias for :func:`resume_content_hash`. Removed in Unit 11."""
    return resume_content_hash
