"""End-to-end smoke test using a synthetic JD.

This test runs the full pipeline against the bundled sample resume and a
synthetic JobDescription, and asserts that all 12 ATS gates are evaluated.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf
from pydantic_ai.models.test import TestModel

from gethired.models import FinalOutcome, JobDescription, JobType, job_validate
from gethired.renderer import render_tex, render_text
from gethired.tailor import VALIDATION_JOB_TYPES, Tailor, merge_critic_jobs
from gethired.validator import AtsGate, AtsGateReport, ats_check

SAMPLE_JD = JobDescription(
    url="https://example.com/jd",
    title="Senior Machine Learning Engineer",
    company="Acme AI",
    full_text=(
        "Senior Machine Learning Engineer — Acme AI. "
        "We need Python, Kubernetes, Docker, AWS, distributed systems, "
        "PyTorch, TensorFlow, LLM inference optimisation with vLLM, "
        "retrieval-augmented generation. "
        "5+ years experience. "
        "Must have: machine learning engineering, production Kubernetes."
    ),
    keywords=(
        "python",
        "kubernetes",
        "docker",
        "aws",
        "distributed",
        "pytorch",
        "tensorflow",
        "llm",
        "vllm",
    ),
    must_have_keywords=("python", "kubernetes", "docker"),
    nice_to_have_keywords=("llm", "vllm", "pytorch", "tensorflow"),
    content_hash="sample",
)


def test_end_to_end_pipeline_runs() -> None:
    tailor = Tailor(
        resume="resume.tex",
        job_description=SAMPLE_JD,
        debug=False,
        model="test",
        model_instance=TestModel(),
    )
    result = tailor.run()
    assert result.run.id
    run_dir = Path("tailored") / result.run.id
    assert (run_dir / "tailored.tex").exists()
    assert (run_dir / "tailored.txt").exists()
    assert (run_dir / "tailored.json").exists()
    assert (run_dir / "match_report.md").exists()


def test_end_to_end_atg_gates_all_evaluated() -> None:
    tailor = Tailor(
        resume="resume.tex",
        job_description=SAMPLE_JD,
        debug=False,
        model="test",
        model_instance=TestModel(),
    )
    result = tailor.run()
    tex = render_tex(result)
    txt = render_text(result)
    report = ats_check(result, tex, None, txt, (SAMPLE_JD,))
    assert isinstance(report, AtsGateReport)
    assert len(report.results) == len(list(AtsGate))
    for gate_result in report.results:
        assert gate_result.status.value in {"pass", "fail", "skip"}


def test_end_to_end_job_trail_emitted() -> None:
    tailor = Tailor(
        resume="resume.tex",
        job_description=SAMPLE_JD,
        debug=False,
        model="test",
        model_instance=TestModel(),
    )
    result = tailor.run()
    job_types = {job.type for job in result.jobs}
    assert "tailor" in job_types
    assert "validate_grounding" in job_types
    assert "validate_style" in job_types
    assert "validate_plagiarism" in job_types
    assert "validate_ats" in job_types


def test_end_to_end_section_headings_present() -> None:
    """The rendered TeX must contain the standard ATS section headings."""
    tailor = Tailor(
        resume="resume.tex",
        job_description=SAMPLE_JD,
        debug=False,
        model="test",
        model_instance=TestModel(),
    )
    result = tailor.run()
    tex = render_tex(result)
    assert "\\section{Summary}" in tex
    assert "\\section{Experience}" in tex
    assert "\\section{Education}" in tex
    assert "\\section{Technical Skills}" in tex
    assert "\\section{Selected Projects}" in tex


def test_merge_critic_jobs_replaces_all_prior_validation_jobs() -> None:
    """Re-running the critic after PDF compile must not duplicate validation jobs."""
    existing = (
        job_validate(JobType.VALIDATE_GROUNDING, outputs=(), rationale="first"),
        job_validate(JobType.VALIDATE_STYLE, outputs=(), rationale="first"),
        job_validate(JobType.VALIDATE_PLAGIARISM, outputs=(), rationale="first"),
        job_validate(JobType.VALIDATE_ATS, outputs=(), rationale="first"),
    )
    authoritative = (
        job_validate(JobType.VALIDATE_GROUNDING, outputs=(), rationale="second"),
        job_validate(JobType.VALIDATE_STYLE, outputs=(), rationale="second"),
        job_validate(JobType.VALIDATE_PLAGIARISM, outputs=(), rationale="second"),
        job_validate(JobType.VALIDATE_ATS, outputs=(), rationale="second"),
    )
    merged = merge_critic_jobs(existing, authoritative)
    validate_jobs = [j for j in merged if j.type in VALIDATION_JOB_TYPES]
    assert len(validate_jobs) == 4
    assert all(j.rationale == "second" for j in validate_jobs)


def test_pipeline_pdf_pass_revalidates_and_recomputes_outcome(tmp_path: Path, monkeypatch) -> None:
    """When a PDF compiles, the critic re-runs and the outcome reflects PDF gates."""

    def fake_compile(tex_source: str, output_dir: Path) -> Path:
        run_dir = Path(output_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = run_dir / "tailored.pdf"
        document = pymupdf.open()
        document.new_page()
        document.new_page()
        document.save(pdf_path)
        document.close()
        return pdf_path

    monkeypatch.setattr("gethired.tailor.compile_pdf", fake_compile)
    tailor = Tailor(
        resume="resume.tex",
        job_description=SAMPLE_JD,
        debug=False,
        model="test",
        model_instance=TestModel(),
        tailored_dir=tmp_path,
    )
    result = tailor.run()
    for job_type in VALIDATION_JOB_TYPES:
        matches = [job for job in result.jobs if job.type is job_type]
        assert len(matches) == 1, f"{job_type.value} duplicated: {len(matches)}"
    assert result.run_result.final_outcome is FinalOutcome.ATS_HARD_FAIL
