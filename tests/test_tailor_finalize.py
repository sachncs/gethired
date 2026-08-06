"""Tests for ``Tailor.finalize`` and ``Tailor.diff``.

These two methods have no LLM path — they re-render an existing
``tailored.json``. Both are covered in isolation here so the broader
integration suite doesn't have to spin up a model just to exercise them.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from gethired.exceptions import TailorError
from gethired.models import Resume, Skills
from gethired.serialize import render_json, snapshot
from gethired.tailor import Tailor


def _sample_master_json() -> str:
    """Build a serialised Tailored (master snapshot) for testing."""
    master = Master(
        contact=Resume(
            name="Test",
            city="City",
            phone="+1-555-0100",
            email="test@example.com",
            github=None,
            linkedin=None,
        ),
        summary="Summary.",
        skills=Skills(categories={"Languages": ("Python",)}),
        experience=(),
        projects=(),
        education=(),
        awards=(),
    )
    return render_json(snapshot(master))


def _make_tailor_with_test_model() -> Tailor:
    """Construct a Tailor instance that bypasses the MODEL requirement."""
    return Tailor(
        resume="ignored",
        job_description="ignored",
        model_instance=mock.MagicMock(),
    )


def test_finalize_re_renders_tailored_json(tmp_path: Path) -> None:
    """``finalize`` parses an edited ``tailored.json`` and re-renders artefacts."""
    source = tmp_path / "source.json"
    source.write_text(_sample_master_json())
    tailor = _make_tailor_with_test_model()
    tailored = tailor.finalize(source)
    assert tailored.name == "Test"
    assert (source.parent / "tailored.tex").exists()
    assert (source.parent / "tailored.txt").exists()
    assert (source.parent / "tailored.json").exists()
    assert (source.parent / "match_report.md").exists()


def test_finalize_rejects_json_without_run_result(tmp_path: Path) -> None:
    """``finalize`` raises when the snapshot has no embedded ``run_result``."""
    source = tmp_path / "bare.json"
    source.write_text(
        json.dumps(
            {
                "contact": {
                    "name": "x",
                    "city": "x",
                    "phone": "x",
                    "email": "x@x",
                    "github_url": None,
                    "linkedin_url": None,
                },
                "summary": "x",
                "skills": {"categories": {}},
                "experiences": [],
                "projects": [],
                "education": [],
                "awards": [],
                "dropped": [],
                "grounding": [],
            }
        )
    )
    tailor = _make_tailor_with_test_model()
    with pytest.raises(TailorError, match="missing run_result"):
        tailor.finalize(source)


def test_diff_returns_unified_diff(tmp_path: Path) -> None:
    """``diff`` produces a unified diff between two ``match_report.md`` files."""
    run_a = tmp_path / "a"
    run_b = tmp_path / "b"
    run_a.mkdir()
    run_b.mkdir()
    (run_a / "match_report.md").write_text("# run a\n\nfirst line\n")
    (run_b / "match_report.md").write_text("# run b\n\nsecond line\n")

    tailor = _make_tailor_with_test_model()
    tailor.tailored_dir = tmp_path  # type: ignore[assignment]
    diff_text = tailor.diff(other_run_id="a")
    assert "--- a" in diff_text
    assert "first line" in diff_text
