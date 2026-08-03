"""End-to-end smoke test using a synthetic JD.

This test runs the full pipeline against the bundled sample resume and a
synthetic JobDescription, and asserts that all 12 ATS gates are evaluated.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_ai.models.test import TestModel

from gethired.models import JobDescription
from gethired.renderer import render_tex, render_text
from gethired.tailor import Tailor
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
