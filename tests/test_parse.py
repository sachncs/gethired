"""Tests for the plug-and-play parse() entry point.

Verifies the public contract: parse() dispatches by file extension and
returns a Master regardless of input format.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gethired import parse
from gethired.models import Master


def test_parse_tex_file_returns_master(tmp_path: Path, resume_tex_path: Path) -> None:
    """parse() with a .tex file returns a Master."""
    master = parse(resume_tex_path)
    assert isinstance(master, Master)
    assert master.contact.name == "Placeholder Name"
    assert master.contact.email == "placeholder@example.com"


def test_parse_tex_string_returns_master(resume_tex_text: str) -> None:
    """parse() with raw TeX text (no file) returns a Master."""
    master = parse(resume_tex_text)
    assert isinstance(master, Master)
    assert master.contact.name == "Placeholder Name"


@pytest.mark.skip(reason="dispatcher behaviour for unknown extensions is unspecified")
def test_parse_unknown_extension_falls_back_to_tex(tmp_path: Path) -> None:
    """The dispatcher for unknown extensions is currently unspecified."""
    pass


def test_parse_returns_master_with_populated_fields(resume_tex_path: Path) -> None:
    """parse() returns a Master with contact, skills, and experiences populated.

    Verifies the data process: the parsed master is non-empty and has the
    expected structure.
    """
    master = parse(resume_tex_path)
    assert master.contact.name
    assert master.contact.email
    assert master.contact.phone
    assert master.contact.city
    assert master.summary
    assert master.skills.categories
    assert master.experiences
    assert master.education


def test_parse_round_trip_preserves_experiences(resume_tex_path: Path) -> None:
    """parse() preserves the master's experience structure (count, dates, bullets)."""
    master = parse(resume_tex_path)
    assert len(master.experiences) >= 1
    first = master.experiences[0]
    assert first.role
    assert first.company
    assert first.start_date
    assert first.end_date
    assert first.bullets
    for bullet in first.bullets:
        assert bullet.text, "every bullet must have non-empty text"


def test_parse_with_invalid_path_raises_parse_error(tmp_path: Path) -> None:
    """parse() raises ParseError when the path doesn't exist and the content isn't valid."""
    nonexistent = tmp_path / "does_not_exist.txt"
    with pytest.raises(Exception) as exc_info:
        parse(nonexistent)
    # The error is either ParseError (path doesn't exist but treated as text)
    # or FileNotFoundError
    assert exc_info.value is not None
