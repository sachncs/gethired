"""End-to-end smoke test using a synthetic JD.

This test runs the full pipeline against the bundled sample resume and a
synthetic Job, and asserts that all 12 ATS gates are evaluated.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest
from pydantic_ai.models.test import TestModel
from typer.testing import CliRunner

from gethired import cli as cli_module
from gethired.cover_letter import compose, markdown
from gethired.description import consolidate, overlay_for_jd
from gethired.models import (
    Job,
    Outcome,
    Run,
    RunResult,
    Step,
    StepKind,
    StepMeta,
    StepStatus,
    Tailored,
    job_validate,
    Resume,
)
from gethired.parser import parse_tex
from gethired.profiler import build as build_profile
from gethired.renderer import tex, text
from gethired.tailor import VALIDATION, Tailor, hash_urls, merge_steps
from gethired.validator import AtsGate, AtsReport, ats

SAMPLE_JD = Job(
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
        "vllm"),
    must_have_keywords=("python", "kubernetes", "docker"),
    nice_to_have_keywords=("llm", "vllm", "pytorch", "tensorflow"),
    content_hash="sample")


def test_end_to_end_pipeline_runs() -> None:
    """The full pipeline produces a TailoredResume with persisted artefacts.

    Verifies the on-disk data process: parsing, JD input, run-id
    generation, and the persistence of all four artefacts. Each artefact
    must contain non-empty content (not just be a 0-byte file).
    """
    tailor = Tailor(
        resume="sample.tex",
        job_description=SAMPLE_JD,
        debug=False,
        model="test",
        model_instance=TestModel())
    result = tailor.run()
    # Run-id must be a UUID
    assert len(result.run.id) == 36, f"run.id must be UUID-shaped, got {result.run.id!r}"
    # The master's contact must round-trip
    assert result.name == "Placeholder Name", (
        f"contact.name not preserved: {result.name!r}"
    )
    assert result.email == "placeholder@example.com"
    # All four artefacts must be persisted with non-empty content
    run_dir = Path("tailored") / result.run.id
    for name in ("tailored.tex", "tailored.txt", "tailored.json", "match_report.md"):
        path = run_dir / name
        assert path.exists(), f"missing artefact: {path}"
        assert path.stat().st_size > 0, f"empty artefact: {path}"
    # The match report must reference the run
    report_text = (run_dir / "match_report.md").read_text()
    assert result.run.id in report_text, "match_report.md must reference the run-id"


def test_end_to_end_atg_gates_all_evaluated() -> None:
    tailor = Tailor(
        resume="sample.tex",
        job_description=SAMPLE_JD,
        debug=False,
        model="test",
        model_instance=TestModel())
    result = tailor.run()
    t = tex(result)
    t2 = text(result)
    report = ats(result, t, None, t2, (SAMPLE_JD))
    assert isinstance(report, AtsReport)
    assert len(report.results) == len(list(AtsGate))
    for gate_result in report.results:
        assert gate_result.status.value in {"pass", "fail", "skip"}


def test_end_to_end_job_trail_emitted() -> None:
    tailor = Tailor(
        resume="sample.tex",
        job_description=SAMPLE_JD,
        debug=False,
        model="test",
        model_instance=TestModel())
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
        resume="sample.tex",
        job_description=SAMPLE_JD,
        debug=False,
        model="test",
        model_instance=TestModel())
    result = tailor.run()
    t = tex(result)
    assert "\\section{Summary}" in t
    assert "\\section{Experience}" in t
    assert "\\section{Education}" in t
    assert "\\section{Technical Skills}" in t
    assert "\\section{Selected Projects}" in t


def test_merge_critic_jobs_replaces_all_prior_validation_jobs() -> None:
    """Re-running the critic after PDF compile must not duplicate validation jobs."""
    existing = (
        job_validate(StepKind.VALIDATE_GROUNDING, outputs=(), rationale="first"),
        job_validate(StepKind.VALIDATE_STYLE, outputs=(), rationale="first"),
        job_validate(StepKind.VALIDATE_PLAGIARISM, outputs=(), rationale="first"),
        job_validate(StepKind.VALIDATE_ATS, outputs=(), rationale="first"))
    authoritative = (
        job_validate(StepKind.VALIDATE_GROUNDING, outputs=(), rationale="second"),
        job_validate(StepKind.VALIDATE_STYLE, outputs=(), rationale="second"),
        job_validate(StepKind.VALIDATE_PLAGIARISM, outputs=(), rationale="second"),
        job_validate(StepKind.VALIDATE_ATS, outputs=(), rationale="second"))
    merged = merge_steps(existing, authoritative)
    validate_jobs = [j for j in merged if j.type in VALIDATION]
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
        resume="sample.tex",
        job_description=SAMPLE_JD,
        debug=False,
        model="test",
        model_instance=TestModel(),
        tailored_dir=tmp_path)
    result = tailor.run()
    for job_type in VALIDATION:
        matches = [job for job in result.jobs if job.type is job_type]
        assert len(matches) == 1, f"{job_type.value} duplicated: {len(matches)}"
    assert result.run_result.final_outcome is Outcome.ATS_HARD_FAIL


def test_end_to_end_multi_jd_run_persists_combined_match_report(tmp_path: Path) -> None:
    """A multi-JD run writes a single run-dir; the match report's jd_hash covers both URLs."""
    jd_b = Job(
        url="https://example.com/jd-b",
        title="Staff ML Engineer",
        company="Beta Co",
        full_text="Staff ML Engineer. Must have: Python, AWS, Kubernetes.",
        keywords=("python", "aws", "kubernetes"),
        must_have_keywords=("python", "aws"),
        nice_to_have_keywords=("kubernetes",),
        content_hash="b")
    tailor = Tailor(
        resume="sample.tex",
        job_description=(SAMPLE_JD, jd_b),
        debug=False,
        model="test",
        model_instance=TestModel(),
        tailored_dir=tmp_path)
    result = tailor.run()
    run_dir = tmp_path / result.run.id
    assert (run_dir / "tailored.json").exists()
    assert (run_dir / "match_report.md").exists()
    # The merged analysis attached to Tailored reflects both JDs (union of must-haves).
    assert result.analysis is not None
    for kw in ("python", "kubernetes", "aws"):
        assert kw in result.analysis.must_have
    # jd_hash is deterministic and covers both URLs.
    assert result.run.jd_hash == hash_urls((SAMPLE_JD, jd_b))


def test_end_to_end_multi_jd_cover_letters_write_per_jd(tmp_path: Path) -> None:
    """``cover`` with two URLs writes two per-JD letters with their own role."""
    jd_b = Job(
        url="https://example.com/jd-b",
        title="Staff Backend Engineer",
        company="Beta Co",
        full_text="Staff Backend Engineer. You will lead API design.",
        keywords=("python", "aws"),
        must_have_keywords=("python", "aws"),
        nice_to_have_keywords=("kubernetes",),
        content_hash="b")
    master = parse_tex("sample.tex")
    analysis = consolidate((SAMPLE_JD, jd_b,))
    voice = build_profile(master)
    per_b = overlay_for_jd(analysis, jd_b)
    cover_b = compose(master, per_b, voice)
    cover_b_md = markdown(cover_b.letter)

    class FakeTailor:
        def __init__(self, **_kwargs):
            pass

        def run(self):
            steps = (
                Step(
                    id="x",
                    type=StepKind.TAILOR,
                    started_at="now",
                    completed_at="now",
                    status=StepStatus.SUCCESS,
                    inputs=(),
                    outputs=(),
                    rationale="ok",
                    model="test",
                    tool_name=None,
                    metadata=Meta()))
            return Tailored(
                name=master.name,email=master.email,city=master.city,phone=master.phone,github=master.github,linkedin=master.linkedin,
                summary="",
                skills=master.skills,
                experience=master.experience,
                projects=master.projects,
                education=master.education,
                awards=master.awards,
                dropped=(),
                rationale="",
                grounding=(),
                jobs=steps,
                run_result=RunResult(
                    run=Run(
                        id="run-multi-cover",
                        started_at="now",
                        resume_hash="",
                        jd_hash="",
                        model="test",
                        draft_model=None),
                    completed_at="now",
                    duration_seconds=0.0,
                    total_input_tokens=0,
                    total_output_tokens=0,
                    retry_attempts=0,
                    final_outcome=Outcome.SUCCESS,
                    jobs=steps),)

    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(cli_module, "Tailor", FakeTailor)
        mp.setattr(cli_module, "fetch_all_jds", lambda _urls: (SAMPLE_JD, jd_b))

        result = CliRunner().invoke(
            cli_module.app,
            [
                "cover",
                SAMPLE_JD.url,
                jd_b.url,
                "--resume",
                "sample.tex",
                "--out-dir",
                str(tmp_path),
            ])
        assert result.exit_code == 0, result.stdout + (result.stderr or "")
        run_dir = tmp_path / "run-multi-cover"
        covers = sorted(run_dir.glob("cover_letter_*.md"))
        assert len(covers) == 2, f"expected 2 per-JD cover letters, got {[p.name for p in covers]}"
        bodies = [p.read_text() for p in covers]
        assert any("Staff Backend Engineer" in b for b in bodies)
        assert cover_b_md.strip() in [b.strip() for b in bodies]
    finally:
        mp.undo()
