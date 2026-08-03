"""Tests for the audit module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gethired.audit import (
    AuditReport,
    audit,
    audit_json,
    audit_markdown,
)
from gethired.exceptions import TailorError


def _write_run(run_dir: Path, master: dict[str, object], tailored: dict[str, object]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "master.json").write_text(json.dumps(master))
    (run_dir / "tailored.json").write_text(json.dumps(tailored))


def _sample_run_payloads() -> tuple[dict[str, object], dict[str, object]]:
    master = {
        "contact": {
            "name": "Placeholder Name",
            "city": "Test City",
            "phone": "5555550100",
            "email": "placeholder@example.com",
            "github_url": None,
            "linkedin_url": None,
        },
        "summary": "Engineer with Python and Kubernetes experience.",
        "skills": {
            "categories": {
                "Languages": ("python",),
                "Cloud": ("kubernetes",),
            }
        },
        "experiences": [
            {
                "role": "Senior Engineer",
                "company": "Acme",
                "start_date": "2020",
                "end_date": "present",
                "bullets": [{"text": "Built Python services on Kubernetes."}],
            }
        ],
        "projects": [],
        "education": [],
        "awards": [],
    }
    tailored = {
        "contact": master["contact"],
        "summary": "Engineer with Python and Kubernetes experience.",
        "skills": master["skills"],
        "experiences": master["experiences"],
        "projects": [],
        "education": [],
        "awards": [],
        "run_result": {
            "run": {
                "id": "test-run-id",
                "started_at": "2026-01-01T00:00:00.000Z",
                "master_hash": "x",
                "jd_urls_hash": "y",
                "model": "test",
                "draft_model": None,
            },
            "completed_at": "2026-01-01T00:00:00.000Z",
            "duration_seconds": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "retry_attempts": 0,
            "final_outcome": "success",
            "jobs": [],
        },
    }
    return master, tailored


def test_audit_run_returns_report(tmp_path: Path) -> None:
    """audit returns an AuditReport with the run-id and per-validator outputs.

    Verifies the audit data process: parsing, grounding/style/plagiarism
    validation, and ATS evaluation. The test fixture may have some style
    violations (it's a synthetic test resume), so we only assert the
    structural properties of the report.
    """
    master, tailored = _sample_run_payloads()
    _write_run(tmp_path, master, tailored)
    report = audit(tmp_path)
    assert isinstance(report, AuditReport)
    assert report.run_id == "test-run-id"
    # Grounding must pass on the identity-transform fixture
    assert report.grounding_violations == (), (
        f"identity-transform must have no grounding violations, "
        f"got {report.grounding_violations}"
    )
    # Plagiarism must pass on the identity-transform fixture
    assert report.plagiarism_violations == (), (
        f"identity-transform must have no plagiarism violations, "
        f"got {report.plagiarism_violations}"
    )
    # ATS must have evaluated
    assert isinstance(report.ats_failed_gates, tuple)
    assert isinstance(report.ats_advisory_failed_gates, tuple)
    assert isinstance(report.ats_skipped_gates, tuple)


def test_audit_run_raises_when_tailored_missing(tmp_path: Path) -> None:
    """audit raises TailorError when tailored.json is missing."""
    master, _ = _sample_run_payloads()
    (tmp_path / "master.json").write_text(json.dumps(master))
    with pytest.raises(TailorError, match="tailored.json"):
        audit(tmp_path)


def test_audit_run_raises_when_master_missing(tmp_path: Path) -> None:
    """audit raises TailorError when master.json is missing."""
    _, tailored = _sample_run_payloads()
    (tmp_path / "tailored.json").write_text(json.dumps(tailored))
    with pytest.raises(TailorError, match="master.json"):
        audit(tmp_path)


def test_render_audit_json_includes_all_sections(tmp_path: Path) -> None:
    """audit_json produces JSON with all expected keys."""
    master, tailored = _sample_run_payloads()
    _write_run(tmp_path, master, tailored)
    report = audit(tmp_path)
    payload = json.loads(audit_json(report))
    assert payload["run_id"] == "test-run-id"
    assert "grounding_violations" in payload
    assert "style_violations" in payload
    assert "plagiarism_violations" in payload
    assert "ats_passed" in payload
    assert "ats_failed_gates" in payload
    assert "ats_advisory_failed_gates" in payload
    assert "ats_skipped_gates" in payload


def test_render_audit_markdown_includes_run_id(tmp_path: Path) -> None:
    """audit_markdown includes the run id in the header."""
    master, tailored = _sample_run_payloads()
    _write_run(tmp_path, master, tailored)
    report = audit(tmp_path)
    md = audit_markdown(report)
    assert "test-run-id" in md
    assert "# Audit report" in md
