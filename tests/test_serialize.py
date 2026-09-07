"""Tests for ``gethired.serialize``.

Covers the canonical JSON ↔ domain-model coercion, including the master
snapshot path used by ``ingest`` and the round-trip from a tailored JSON
file through ``from_tailored_dict`` and back.
"""

from __future__ import annotations

import json
from pathlib import Path

from gethired.models import (
    Award,
    Bullet,
    Citation,
    Contact,
    Education,
    Experience,
Resume,
    Project,
    Reason,
    Skills,
    Resume,
)
from gethired.serialize import (
    MasterSnapshot,
    as_dict,
    from_bullets,
    from_master_dict,
    from_run_result_dict,
    from_tailored_dict,
    load_master,
    render_json,
    snapshot)


def _sample_resume() -> Resume:
    """Build a minimal but realistic Resume for round-trip tests."""
    return Resume(name="Test User", city="Test City", phone="+1-555-0100", email="test@example.com", github=None, linkedin=None, summary="A short summary.",
        skills=Skills(categories={"Languages": ("Python", "Go")}),
        experience=(
            Experience(
                role="Engineer",
                company="Acme",
                start_date="2020",
                end_date="2021",
                bullets=(
                    Bullet(text="Built X"),
                    Bullet(text="Shipped Y")))),
        projects=(
            Project(
                name="Proj",
                url="https://example.com/proj",
                bullets=(Bullet(text="Did Z")))),
        education=(
            Education(
                institution="Test U",
                location="City",
                degree="BS",
                major="CS",
                graduation="2020",
                gpa=None)),
        awards=(
            Award(
                title="Award",
                organization="Org",
                date="2020",
                description="Desc")))


def test_coerce_bullets_maps_dicts_to_bullets() -> None:
    """``from_bullets`` reconstructs a tuple of ``Bullet`` from dict shapes."""
    items = [{"text": "a"}, {"text": "b"}]
    result = from_bullets(items)
    assert result == (Bullet(text="a"), Bullet(text="b"))


def test_coerce_master_from_dict_roundtrips() -> None:
    """A round-trip through render_json → from_master_dict preserves data."""
    master = _sample_resume()
    snap = snapshot(master)
    raw = json.loads(render_json(snap))
    reconstructed = from_master_dict(raw)
    assert reconstructed.name == master.name and reconstructed.email == master.email
    assert reconstructed.summary == master.summary
    assert reconstructed.skills.categories == master.skills.categories
    assert reconstructed.experiences[0].role == "Engineer"
    assert reconstructed.experiences[0].bullets[0].text == "Built X"


def test_coerce_tailored_from_dict_preserves_run_result() -> None:
    """A tailored JSON with run_result round-trips into a full Tailored."""
    master = _sample_resume()
    snap = snapshot(master)
    raw = json.loads(render_json(snap))
    tailored = from_tailored_dict(raw)
    assert tailored.name == "Test User"
    assert tailored.run_result is not None
    assert tailored.run_result.run.id == snap.run_result.run.id


def test_coerce_tailored_from_dict_handles_missing_run_result() -> None:
    """When run_result is absent, the reconstructed model has ``run_result=None``."""
    raw = {
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
    tailored = from_tailored_dict(raw)
    assert tailored.run_result is None


def test_load_master_from_json_reads_disk(tmp_path: Path) -> None:
    """``load_master`` reads a previously written master JSON."""
    master = _sample_resume()
    snap = snapshot(master)
    path = tmp_path / "master.json"
    path.write_text(render_json(snap))
    loaded = load_master(path)
    assert loaded.name == "Test User"
    assert loaded.experiences[0].company == "Acme"


def test_master_snapshot_uses_overrides() -> None:
    """``MasterSnapshot`` overrides flow into the embedded run identity."""
    master = _sample_resume()
    snap = snapshot(master, snapshot=MasterSnapshot(model="cli", draft_model="haiku"))
    assert snap.run_result.run.model == "cli"
    assert snap.run_result.run.draft_model == "haiku"


def test_tailored_to_snapshot_dict_returns_dict() -> None:
    """``as_dict`` returns the same payload as a dict."""
    master = _sample_resume()
    snap = snapshot(master)
    payload = as_dict(snap)
    assert isinstance(payload, dict)
    assert payload["contact"]["name"] == "Test User"


def test_coerce_run_result_returns_none_for_none_input() -> None:
    """A ``None`` input round-trips to ``None``."""
    assert from_run_result_dict(None) is None


def test_coerce_run_result_rebuilds_run() -> None:
    """A dict input rebuilds the embedded Run object."""
    raw = {
        "run": {
            "id": "abc",
            "started_at": "2026-01-01T00:00:00.000Z",
            "resume_hash": "x",
            "jd_hash": "y",
            "model": "m",
            "draft_model": None,
        },
        "completed_at": "2026-01-01T00:01:00.000Z",
        "duration_seconds": 0.0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "retry_attempts": 0,
        "final_outcome": "success",
        "jobs": [],
    }
    result = from_run_result_dict(raw)
    assert result is not None
    assert result.run.id == "abc"


def test_coerce_tailored_from_dict_preserves_dropped_and_grounding() -> None:
    """Drop reasons and grounding citations survive the JSON round-trip."""
    raw = {
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
        "dropped": [{"item_id": "experiences[0]", "reason": "r"}],
        "grounding": [
            {
                "tailored_path": "experiences[0].bullets[0]",
                "master_path": "experiences[0].bullets[0]",
                "verbatim_span": "x",
                "job_id": "writer",
            }
        ],
    }
    tailored = from_tailored_dict(raw)
    assert tailored.dropped == (Reason(item_id="experiences[0]", reason="r"))
    assert tailored.grounding[0] == Citation(
        tailored_path="experiences[0].bullets[0]",
        master_path="experiences[0].bullets[0]",
        verbatim_span="x",
        job_id="writer")
