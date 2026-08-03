"""Tests for the validators."""

from __future__ import annotations

from pathlib import Path

import pymupdf

from gethired.models import (
    Bullet,
    Experience,
    FinalOutcome,
    JobDescription,
    MasterResume,
    Run,
    RunResult,
    SkillsByCategory,
    TailoredResume,
)
from gethired.renderer import render_tex, render_text
from gethired.validator import (
    AtsGate,
    GateStatus,
    GateTier,
    ats_check,
    grounding_check,
    plagiarism_check,
    style_check,
)


def _make_tailored(master: MasterResume) -> TailoredResume:
    """Build a tailored resume that's an identity transform of master."""
    run_result = RunResult(
        run=Run("test-id", "2026-08-02T00:00:00.000Z", "x", "y", "model", None),
        completed_at="2026-08-02T00:00:00.000Z",
        duration_seconds=0.0,
        total_input_tokens=0,
        total_output_tokens=0,
        retry_attempts=0,
        final_outcome=FinalOutcome.SUCCESS,
        jobs=(),
    )
    return TailoredResume(
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
    tailored = _make_tailored(master_resume)
    violations = grounding_check(tailored, master_resume)
    assert violations == ()


def test_grounding_detects_invented_skill(master_resume) -> None:
    tailored = _make_tailored(master_resume)
    fake = TailoredResume(
        contact=tailored.contact,
        summary=tailored.summary,
        skills=SkillsByCategory(
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
    violations = grounding_check(fake, master_resume)
    assert any(v.detail.startswith("Skill 'QuantumScript'") for v in violations)


def test_grounding_detects_invented_number(master_resume) -> None:
    tailored = _make_tailored(master_resume)
    fake = TailoredResume(
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
    violations = grounding_check(fake, master_resume)
    assert any("99999999" in v.detail for v in violations)


def test_style_detects_banned_word(master_resume) -> None:
    tailored = _make_tailored(master_resume)
    fake = TailoredResume(
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
    violations = style_check(fake)
    assert any("leverage" in v.detail.lower() for v in violations)


def test_plagiarism_passes_for_identity_transform(master_resume) -> None:
    tailored = _make_tailored(master_resume)
    jd = JobDescription(
        url="https://example.com/jd",
        title="ML Engineer",
        company="Acme",
        full_text="some completely unrelated job description text here",
        keywords=("python",),
        must_have_keywords=(),
        nice_to_have_keywords=("python",),
        content_hash="abc",
    )
    violations = plagiarism_check(tailored, (jd,))
    assert violations == ()


def test_plagiarism_detects_5gram_overlap(master_resume) -> None:
    """JD and tailored share a 5-gram → violation."""
    shared_phrase = "designed and deployed isolated ai platforms"
    jd_text = f"Requirements include {shared_phrase} for enterprise customers in fintech."
    jd = JobDescription(
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
    fake = TailoredResume(
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
    violations = plagiarism_check(fake, (jd,))
    expected_5gram = "designed and deployed isolated ai"
    assert any(expected_5gram in v.ngram for v in violations), (
        f"Expected 5-gram {expected_5gram!r} not found in violations: "
        f"{[v.ngram for v in violations]}"
    )


def test_ats_check_produces_full_report(master_resume) -> None:
    tailored = _make_tailored(master_resume)
    tex = render_tex(tailored)
    txt = render_text(tailored)
    report = ats_check(tailored, tex, None, txt, ())
    assert len(report.results) == len(list(AtsGate))


def test_ats_section_headings_pass_for_master(master_resume) -> None:
    tailored = _make_tailored(master_resume)
    tex = render_tex(tailored)
    txt = render_text(tailored)
    report = ats_check(tailored, tex, None, txt, ())
    section_gate = next(r for r in report.results if r.gate == AtsGate.SECTION_HEADINGS_STANDARD)
    assert section_gate.passed


def test_pdf_gates_skip_when_no_pdf(master_resume) -> None:
    tailored = _make_tailored(master_resume)
    tex = render_tex(tailored)
    txt = render_text(tailored)
    report = ats_check(tailored, tex, None, txt, ())
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
    tex = render_tex(tailored)
    txt = render_text(tailored)
    missing_pdf = tmp_path / "missing.pdf"
    report = ats_check(tailored, tex, missing_pdf, txt, ())
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
    tex = render_tex(tailored)
    txt = render_text(tailored)
    tex_with_layout = tex + r"\begin{multicols}{2}"
    report = ats_check(tailored, tex_with_layout, None, txt, ())
    assert AtsGate.NO_TABLES_FOR_LAYOUT in report.hard_failed_gates
    assert AtsGate.NO_TABLES_FOR_LAYOUT in report.failed_gates
    assert AtsGate.NO_TABLES_FOR_LAYOUT.tier is GateTier.HARD


def test_advisory_gate_failure_is_not_blocking(master_resume) -> None:
    tailored = _make_tailored(master_resume)
    tex = render_tex(tailored)
    txt = render_text(tailored)
    jd = JobDescription(
        url="https://example.com/jd",
        title="Senior Engineer",
        company="Acme",
        full_text="Need python, kubernetes, docker, terraform, kafka.",
        keywords=("python", "kubernetes", "docker", "terraform", "kafka"),
        must_have_keywords=("terraform", "kafka"),
        nice_to_have_keywords=(),
        content_hash="jd",
    )
    report = ats_check(tailored, tex, None, txt, (jd,))
    assert AtsGate.KEYWORDS_COVERED in report.advisory_failed_gates
    assert AtsGate.KEYWORDS_COVERED.tier is GateTier.ADVISORY
    assert report.hard_failed_gates == ()


def test_length_gate_passes_for_single_page_pdf(master_resume, tmp_path) -> None:
    tailored = _make_tailored(master_resume)
    tex = render_tex(tailored)
    txt = render_text(tailored)
    pdf_path = tmp_path / "one_page.pdf"
    _write_pdf(pdf_path, pages=1)
    report = ats_check(tailored, tex, pdf_path, txt, ())
    result = next(r for r in report.results if r.gate == AtsGate.LENGTH_WITHIN_LIMIT)
    assert result.status is GateStatus.PASS
    assert "1 page(s)" in result.detail


def test_length_gate_fails_for_multi_page_pdf(master_resume, tmp_path) -> None:
    tailored = _make_tailored(master_resume)
    tex = render_tex(tailored)
    txt = render_text(tailored)
    pdf_path = tmp_path / "two_pages.pdf"
    _write_pdf(pdf_path, pages=2)
    report = ats_check(tailored, tex, pdf_path, txt, ())
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
