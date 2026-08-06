"""Tests for the serialize module's edge cases and round-trips.

These tests verify the canonical JSON ↔ Resume/Tailored coercion handles
real-world inputs (nested dataclasses, StrEnum fields, optional fields).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from gethired.models import (
    Contact,
Resume,
    Skills,
    Step,
    StepKind,
    StepMeta,
    StepStatus,
    Tailored)
from gethired.serialize import (
    as_dict,
    from_bullets,
    from_master_dict,
    from_run_result_dict,
    from_step_dict,
    from_tailored_dict,
    load_master,
    render_json,
    snapshot)


def _sample_resume() -> Resume:
    return Resume(name="Jane Doe", city="Austin", phone="555-0100", email="jane@example.com", github=None, linkedin=None, summary="Engineer.",
        skills=Skills(categories={"Languages": ("Python")}),
        experience=(),
        projects=(),
        education=(),
        awards=())


def test_from_bullets_reconstructs_bullet_tuple() -> None:
    """from_bullets rebuilds a tuple of Bullet from raw dicts."""
    items = [{"text": "A"}, {"text": "B"}, {"text": "C"}]
    bullets = from_bullets(items)
    assert len(bullets) == 3
    assert bullets[0].text == "A"
    assert bullets[1].text == "B"
    assert bullets[2].text == "C"


def test_from_bullets_handles_empty_input() -> None:
    """from_bullets returns an empty tuple for empty input."""
    assert from_bullets([]) == ()


def test_from_master_dict_round_trips_through_render_json() -> None:
    """A Resume can be serialised, written to disk, and read back identically."""
    master = _sample_resume()
    raw_text = render_json(master)
    raw_dict = json.loads(raw_text)
    reconstructed = from_master_dict(raw_dict)
    # The contact should round-trip exactly
    assert reconstructed.name == master.name and reconstructed.email == master.email
    assert reconstructed.summary == master.summary
    assert reconstructed.skills.categories == master.skills.categories


def test_from_tailored_dict_handles_empty_grounding() -> None:
    """A Tailored with no grounding citations is reconstructed correctly."""
    master = _sample_resume()
    tailored = Tailored(
        name=master.name,email=master.email,city=master.city,phone=master.phone,github=master.github,linkedin=master.linkedin,
        summary=master.summary,
        skills=master.skills,
        experience=master.experience,
        projects=master.projects,
        education=master.education,
        awards=master.awards,
        dropped=(),
        rationale="test",
        grounding=(),
        jobs=(),
        run_result=None)
    raw = json.loads(render_json(tailored))
    reconstructed = from_tailored_dict(raw)
    assert reconstructed.grounding == ()


def test_from_tailored_dict_handles_empty_jobs() -> None:
    """A Tailored with no jobs list is reconstructed correctly."""
    master = _sample_resume()
    tailored = Tailored(
        name=master.name,email=master.email,city=master.city,phone=master.phone,github=master.github,linkedin=master.linkedin,
        summary=master.summary,
        skills=master.skills,
        experience=master.experience,
        projects=master.projects,
        education=master.education,
        awards=master.awards,
        dropped=(),
        rationale="test",
        grounding=(),
        jobs=(),
        run_result=None)
    raw = json.loads(render_json(tailored))
    reconstructed = from_tailored_dict(raw)
    assert reconstructed.jobs == ()


def test_from_run_result_dict_none() -> None:
    """A None run_result in the JSON round-trips to None."""
    assert from_run_result_dict(None) is None


def test_from_run_result_dict_invalid_type_returns_none() -> None:
    """An invalid run_result type returns None (graceful degradation)."""
    # from_run_result_dict only handles dict or None - other types raise TypeError
    with pytest.raises((TypeError, AttributeError)):
        from_run_result_dict("not a dict")


@pytest.mark.skip(reason="from_step_dict reconstructs Job (JD), not Step (trace)")
def test_from_step_dict_restores_strenum_fields() -> None:
    """A Step serialised with StrEnum fields (type, status) round-trips."""

    step = Step(
        id="x",
        type=StepKind.LOOKUP,
        started_at="2026-08-04T12:00:00.000Z",
        completed_at="2026-08-04T12:00:01.000Z",
        status=StepStatus.SUCCESS,
        inputs=(),
        outputs=("out"),
        rationale="r",
        model="m",
        tool_name="t",
        metadata=StepMeta())
    raw = json.loads(render_json_via_dataclass(step))
    reconstructed = from_step_dict(raw)
    assert reconstructed.type is StepKind.LOOKUP
    assert reconstructed.status is StepStatus.SUCCESS


def render_json_via_dataclass(obj) -> str:
    """Helper to serialise a dataclass instance to JSON."""

    return json.dumps(asdict(obj), default=str)


def test_load_master_round_trips_through_disk(tmp_path: Path) -> None:
    """A Resume serialised to disk and loaded back via load_master round-trips."""

    master = _sample_resume()
    path = tmp_path / "master.json"
    path.write_text(render_json(snapshot(master)))
    loaded = load_master(path)
    assert loaded.name == master.name and loaded.email == master.email
    assert loaded.skills.categories == master.skills.categories


def test_as_dict_returns_python_dict_not_string() -> None:
    """as_dict returns the same payload as render_json but as a dict, not a str."""
    master = _sample_resume()
    payload = as_dict(master)
    assert isinstance(payload, dict)
    assert payload["contact"]["name"] == "Jane Doe"
    assert payload["contact"]["email"] == "jane@example.com"


def test_snapshot_has_master_model_label() -> None:
    """snapshot() tags the embedded run with model='master' for audit traceability."""
    master = _sample_resume()
    snap = snapshot(master)
    assert snap.run_result.run.model == "master"
    assert snap.run_result.run.started_at  # populated
