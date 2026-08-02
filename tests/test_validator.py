"""Tests for the validators."""

from __future__ import annotations

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
    jd_text = (
        f"Requirements include {shared_phrase} for enterprise customers in fintech."
    )
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
        f"Expected 5-gram {expected_5gram!r} not found in violations: {[v.ngram for v in violations]}"
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
