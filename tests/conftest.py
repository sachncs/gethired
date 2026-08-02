"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from gethired.parser import parse_tex

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def resume_tex_path() -> Path:
    return FIXTURES_DIR / "resume.tex"


@pytest.fixture(scope="session")
def resume_tex_text(resume_tex_path: Path) -> str:
    return resume_tex_path.read_text()


@pytest.fixture(scope="session")
def master_resume(resume_tex_path: Path):
    """Parsed MasterResume from the fixture resume.tex."""
    return parse_tex(resume_tex_path)


@pytest.fixture(scope="session")
def master_resume_content_hash(master_resume) -> str:
    return master_resume.content_hash()
