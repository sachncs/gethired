"""Tests for the audit report rendering (markdown path with non-empty reports)."""

from __future__ import annotations

from gethired.audit import AuditReport, audit_markdown


def test_audit_markdown_includes_hard_advisory_and_skipped() -> None:
    """The markdown render surfaces every gate tier when present."""
    report = AuditReport(
        run_id="abc",
        grounding_violations=("g1: detail",),
        style_violations=("s1: detail",),
        plagiarism_violations=("p1: 5gram",),
        ats_passed=False,
        ats_failed_gates=("pdf_compiles",),
        ats_advisory_failed_gates=("bullets_quantified",),
        ats_skipped_gates=("length_within_limit",),
    )
    md = audit_markdown(report)
    assert "Hard-failed gates" in md
    assert "pdf_compiles" in md
    assert "Advisory-failed gates" in md
    assert "bullets_quantified" in md
    assert "Skipped gates" in md
    assert "length_within_limit" in md
    assert "g1: detail" in md
    assert "s1: detail" in md
    assert "p1: 5gram" in md


def test_audit_markdown_omits_empty_sections() -> None:
    """When no violations exist, the per-section blocks are absent."""
    report = AuditReport(
        run_id="clean",
        grounding_violations=(),
        style_violations=(),
        plagiarism_violations=(),
        ats_passed=True,
        ats_failed_gates=(),
        ats_advisory_failed_gates=(),
        ats_skipped_gates=(),
    )
    md = audit_markdown(report)
    assert "Hard-failed gates" not in md
    assert "Advisory-failed gates" not in md
    assert "Skipped gates" not in md
    assert "## Grounding" not in md
    assert "## Style" not in md
    assert "## Plagiarism" not in md
