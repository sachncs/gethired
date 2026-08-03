"""Tests for the validators."""

from __future__ import annotations

from pathlib import Path

import pymupdf

from gethired.models import (
    Bullet,
    Experience,
    Job,
    Master,
    Outcome,
    Run,
    RunResult,
    Skills,
    Tailored,
)
from gethired.renderer import tex, text
from gethired.validator import (
    AtsGate,
    GateStatus,
    GateTier,
    ats,
    grounding,
    pdf_guard,
    plagiarism,
    style,
)


def _make_tailored(master: Master) -> Tailored:
    """Build a tailored resume that's an identity transform of master."""
    run_result = RunResult(
        run=Run("test-id", "2026-08-02T00:00:00.000Z", "x", "y", "model", None),
        completed_at="2026-08-02T00:00:00.000Z",
        duration_seconds=0.0,
        total_input_tokens=0,
        total_output_tokens=0,
        retry_attempts=0,
        final_outcome=Outcome.SUCCESS,
        jobs=(),
    )
    return Tailored(
        contact=master.contact,
        summary=master.summary,
        skills=master.skills,
        experiences=master.experiences,
        projects=master.projects,
        education=master.education,
        awards=master.awards,
        dropped=(),
        rationale="identity",
        grounding=(),
        jobs=(),
        run_result=run_result,
    )


def test_grounding_passes_for_identity_transform(master_resume) -> None:
    """An identity-transform tailored resume produces zero grounding violations.

    When every skill, number, and company in the tailored resume comes
    directly from the master, grounding() must return an empty tuple.
    """
    tailored = _make_tailored(master_resume)
    violations = grounding(tailored, master_resume)
    assert violations == (), (
        f"identity transform must not produce violations, got {violations}"
    )


def test_grounding_detects_invented_skill(master_resume) -> None:
    """Grounding flags a skill that does not appear anywhere in the master.

    Verifies the data safety property: no fabricated skills can pass
    grounding. The violation path must point to the tailored.skills
    category and the detail must name the invented skill.
    """
    tailored = _make_tailored(master_resume)
    fake = Tailored(
        contact=tailored.contact,
        summary=tailored.summary,
        skills=Skills(
            categories={
                "Programming Languages": ("Python", "QuantumScript"),
            }
        ),
        experiences=tailored.experiences,
        projects=tailored.projects,
        education=tailored.education,
        awards=tailored.awards,
        dropped=(),
        rationale="",
        grounding=(),
        jobs=(),
        run_result=tailored.run_result,
    )
    violations = grounding(fake, master_resume)
    skill_violations = [v for v in violations if v.detail.startswith("Skill 'QuantumScript'")]
    assert skill_violations, (
        f"grounding() did not flag the fabricated skill 'QuantumScript'; "
        f"got violations: {violations}"
    )
    # The path must point at the skills tree
    assert skill_violations[0].path.startswith("skills"), (
        f"expected violation path to start with 'skills', got {skill_violations[0].path!r}"
    )


def test_grounding_detects_invented_number(master_resume) -> None:
    """Grounding flags a numeric claim that does not appear in the master.

    The invented number 99999999 is not present in any master bullet, so
    grounding() must produce a violation naming the specific number.
    """
    tailored = _make_tailored(master_resume)
    fake = Tailored(
        contact=master_resume.contact,
        summary=master_resume.summary + " Achieved 99999999% growth.",
        skills=master_resume.skills,
        experiences=master_resume.experiences,
        projects=master_resume.projects,
        education=master_resume.education,
        awards=master_resume.awards,
        dropped=(),
        rationale="",
        grounding=(),
        jobs=(),
        run_result=tailored.run_result,
    )
    violations = grounding(fake, master_resume)
    number_violations = [v for v in violations if "99999999" in v.detail]
    assert number_violations, (
        f"grounding() did not flag the fabricated number 99999999; "
        f"got violations: {violations}"
    )


def test_style_detects_banned_word(master_resume) -> None:
    tailored = _make_tailored(master_resume)
    fake = Tailored(
        contact=master_resume.contact,
        summary="Leveraged Python to deliver comprehensive solutions.",
        skills=master_resume.skills,
        experiences=master_resume.experiences,
        projects=master_resume.projects,
        education=master_resume.education,
        awards=master_resume.awards,
        dropped=(),
        rationale="",
        grounding=(),
        jobs=(),
        run_result=tailored.run_result,
    )
    violations = style(fake)
    assert any("leverage" in v.detail.lower() for v in violations)


def test_plagiarism_passes_for_identity_transform(master_resume) -> None:
    tailored = _make_tailored(master_resume)
    jd = Job(
        url="https://example.com/jd",
        title="ML Engineer",
        company="Acme",
        full_text="some completely unrelated job description text here",
        keywords=("python",),
        must_have_keywords=(),
        nice_to_have_keywords=("python",),
        content_hash="abc",
    )
    violations = plagiarism(tailored, (jd,))
    assert violations == ()


def test_plagiarism_detects_5gram_overlap(master_resume) -> None:
    """JD and tailored share a 5-gram → violation."""
    shared_phrase = "designed and deployed isolated ai platforms"
    jd_text = f"Requirements include {shared_phrase} for enterprise customers in fintech."
    jd = Job(
        url="https://example.com/jd",
        title="ML Engineer",
        company="Acme",
        full_text=jd_text,
        keywords=(),
        must_have_keywords=(),
        nice_to_have_keywords=(),
        content_hash="abc",
    )
    tailored = _make_tailored(master_resume)
    fake = Tailored(
        contact=master_resume.contact,
        summary=master_resume.summary,
        skills=master_resume.skills,
        experiences=tailored.experiences
        + (
            Experience(
                role="Engineer",
                company="Acme",
                start_date="Jan 2020",
                end_date="Dec 2020",
                bullets=(Bullet(text=f"Worked on {shared_phrase} for enterprise customers."),),
            ),
        ),
        projects=master_resume.projects,
        education=master_resume.education,
        awards=master_resume.awards,
        dropped=(),
        rationale="",
        grounding=(),
        jobs=(),
        run_result=tailored.run_result,
    )
    violations = plagiarism(fake, (jd,))
    expected_5gram = "designed and deployed isolated ai"
    assert any(expected_5gram in v.ngram for v in violations), (
        f"Expected 5-gram {expected_5gram!r} not found in violations: "
        f"{[v.ngram for v in violations]}"
    )


def test_ats_check_produces_full_report(master_resume) -> None:
    """ats() evaluates all 12 gates with valid status values and tier annotations.

    Verifies the data process: every gate must produce a result, the result
    must have a valid status (pass/fail/skip), and the gate's tier must be
    set. Without a PDF, 4 PDF-dependent gates should be SKIP and the rest
    should evaluate against the test inputs.
    """
    tailored = _make_tailored(master_resume)
    t = tex(tailored)
    t2 = text(tailored)
    report = ats(tailored, t, None, t2, ())

    # Every gate produces a result
    assert len(report.results) == len(list(AtsGate))
    # Every result has a valid status and a tier
    valid_statuses = {GateStatus.PASS, GateStatus.FAIL, GateStatus.SKIP}
    expected_gates = {r.gate for r in report.results}
    assert expected_gates == set(AtsGate), (
        f"missing gates: {set(AtsGate) - expected_gates}"
    )
    for result in report.results:
        assert result.status in valid_statuses, (
            f"gate {result.gate.value} has invalid status {result.status}"
        )
        assert result.gate.tier in {GateTier.HARD, GateTier.ADVISORY}
    # With pdf_path=None, PDF-dependent gates must be SKIP
    pdf_gates = {
        AtsGate.PDF_COMPILES,
        AtsGate.PDF_TEXT_EXTRACTABLE,
        AtsGate.PDF_TEXT_MATCHES_TXT,
        AtsGate.LENGTH_WITHIN_LIMIT,
    }
    skipped = {r.gate for r in report.results if r.status is GateStatus.SKIP}
    assert pdf_gates.issubset(skipped), (
        f"expected {pdf_gates - skipped} to be SKIP without a PDF"
    )


def test_ats_section_headings_pass_for_master(master_resume) -> None:
    tailored = _make_tailored(master_resume)
    t = tex(tailored)
    t2 = text(tailored)
    report = ats(tailored, t, None, t2, ())
    section_gate = next(r for r in report.results if r.gate == AtsGate.SECTION_HEADINGS_STANDARD)
    assert section_gate.passed


def test_pdf_gates_skip_when_no_pdf(master_resume) -> None:
    tailored = _make_tailored(master_resume)
    t = tex(tailored)
    t2 = text(tailored)
    report = ats(tailored, t, None, t2, ())
    pdf_gates = {
        AtsGate.PDF_COMPILES,
        AtsGate.PDF_TEXT_EXTRACTABLE,
        AtsGate.PDF_TEXT_MATCHES_TXT,
        AtsGate.LENGTH_WITHIN_LIMIT,
    }
    skipped = {result.gate for result in report.results if result.status is GateStatus.SKIP}
    assert skipped == pdf_gates
    assert set(report.skipped_gates) == pdf_gates


def test_pdf_gates_fail_when_pdf_path_missing(master_resume, tmp_path: Path) -> None:
    tailored = _make_tailored(master_resume)
    t = tex(tailored)
    t2 = text(tailored)
    missing_pdf = tmp_path / "missing.pdf"
    report = ats(tailored, t, missing_pdf, t2, ())
    for gate in (AtsGate.PDF_COMPILES, AtsGate.PDF_TEXT_EXTRACTABLE, AtsGate.LENGTH_WITHIN_LIMIT):
        result = next(r for r in report.results if r.gate == gate)
        assert result.status is GateStatus.FAIL


def test_gate_tiers_partition_all_gates() -> None:
    all_gates = set(AtsGate)
    hard = {g for g in all_gates if g.tier is GateTier.HARD}
    advisory = {g for g in all_gates if g.tier is GateTier.ADVISORY}
    assert len(hard) == 9
    assert len(advisory) == 3
    assert hard | advisory == all_gates
    assert hard & advisory == set()


def test_hard_gate_failure_is_blocking(master_resume) -> None:
    tailored = _make_tailored(master_resume)
    t = tex(tailored)
    t2 = text(tailored)
    tex_with_layout = t + r"\begin{multicols}{2}"
    report = ats(tailored, tex_with_layout, None, t2, ())
    assert AtsGate.NO_TABLES_FOR_LAYOUT in report.hard_failed_gates
    assert AtsGate.NO_TABLES_FOR_LAYOUT in report.failed_gates
    assert AtsGate.NO_TABLES_FOR_LAYOUT.tier is GateTier.HARD


def test_advisory_gate_failure_is_not_blocking(master_resume) -> None:
    tailored = _make_tailored(master_resume)
    t = tex(tailored)
    t2 = text(tailored)
    jd = Job(
        url="https://example.com/jd",
        title="Senior Engineer",
        company="Acme",
        full_text="Need python, kubernetes, docker, terraform, kafka.",
        keywords=("python", "kubernetes", "docker", "terraform", "kafka"),
        must_have_keywords=("terraform", "kafka"),
        nice_to_have_keywords=(),
        content_hash="jd",
    )
    report = ats(tailored, t, None, t2, (jd,))
    assert AtsGate.KEYWORDS_COVERED in report.advisory_failed_gates
    assert AtsGate.KEYWORDS_COVERED.tier is GateTier.ADVISORY
    assert report.hard_failed_gates == ()


def test_length_gate_passes_for_single_page_pdf(master_resume, tmp_path) -> None:
    tailored = _make_tailored(master_resume)
    t = tex(tailored)
    t2 = text(tailored)
    pdf_path = tmp_path / "one_page.pdf"
    _write_pdf(pdf_path, pages=1)
    report = ats(tailored, t, pdf_path, t2, ())
    result = next(r for r in report.results if r.gate == AtsGate.LENGTH_WITHIN_LIMIT)
    assert result.status is GateStatus.PASS
    assert "1 page(s)" in result.detail


def test_length_gate_fails_for_multi_page_pdf(master_resume, tmp_path) -> None:
    tailored = _make_tailored(master_resume)
    t = tex(tailored)
    t2 = text(tailored)
    pdf_path = tmp_path / "two_pages.pdf"
    _write_pdf(pdf_path, pages=2)
    report = ats(tailored, t, pdf_path, t2, ())
    result = next(r for r in report.results if r.gate == AtsGate.LENGTH_WITHIN_LIMIT)
    assert result.status is GateStatus.FAIL
    assert AtsGate.LENGTH_WITHIN_LIMIT in report.hard_failed_gates


def _write_pdf(path: Path, pages: int) -> None:
    """Create a minimal blank PDF with ``pages`` pages."""
    document = pymupdf.open()
    for _ in range(pages):
        document.new_page()
    document.save(path)
    document.close()


def test_pdf_artefact_status_skips_when_pdf_path_is_none() -> None:
    """No PDF path returns SKIP, never FAIL."""
    result = pdf_guard(None, AtsGate.PDF_COMPILES)
    assert result is not None
    assert result.status is GateStatus.SKIP
    assert "not compiled" in result.detail


def test_pdf_artefact_status_fails_when_path_set_but_missing(tmp_path: Path) -> None:
    """A set-but-missing PDF path returns FAIL with the path in the detail."""
    missing_path = tmp_path / "does-not-exist.pdf"
    result = pdf_guard(missing_path, AtsGate.PDF_COMPILES)
    assert result is not None
    assert result.status is GateStatus.FAIL
    assert "does-not-exist" in result.detail


def test_pdf_artefact_status_returns_none_when_pdf_exists(tmp_path: Path) -> None:
    """An existing PDF returns None so the caller runs the real gate logic."""
    pdf_path = tmp_path / "exists.pdf"
    _write_pdf(pdf_path, pages=1)
    assert pdf_guard(pdf_path, AtsGate.PDF_COMPILES) is None


def test_pdf_artefact_status_accepts_custom_skip_and_missing_details() -> None:
    """Custom detail strings override the defaults for both branches."""
    skip = pdf_guard(None, AtsGate.PDF_COMPILES, skip_detail="custom skip")
    assert skip is not None and skip.detail == "custom skip"
    missing = pdf_guard(
        Path("/nope.pdf"),
        AtsGate.PDF_COMPILES,
        missing_detail="custom missing",
    )
    assert missing is not None and missing.detail == "custom missing"
