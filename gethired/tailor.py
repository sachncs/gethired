"""Tailor — orchestrator (entry point).

Multi-agent coordination: parser → fetcher → description → profiler → writer → critic → renderer.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Final
from uuid import uuid4

from gethired.constants import MODEL_ENV_VAR
from gethired.cover_letter import (
    render_cover_letter_markdown,
    tailor_cover_letter,
)
from gethired.critic import Critic
from gethired.description import analyze as analyze_description
from gethired.description import analyze_multiple as analyze_description_multiple
from gethired.exceptions import (
    ConfigurationError,
    ResumeTailoringError,
)
from gethired.fetcher import JobDescriptionRetriever
from gethired.models import (
    Award,
    Bullet,
    ContactInformation,
    DropReason,
    Education,
    Experience,
    FinalOutcome,
    GroundedCitation,
    JobDescription,
    MasterResume,
    PreflightReport,
    Project,
    Run,
    RunResult,
    SkillsByCategory,
    TailoredResume,
)
from gethired.observability import configure_logging, step_logger, utcnow_iso
from gethired.parser import parse_tex
from gethired.profiler import build as build_profile
from gethired.render_pdf import compile_pdf
from gethired.renderer import (
    render_json,
    render_match_report,
    render_tex,
    render_text,
)
from gethired.tracing import Tracer, tracer_for_run
from gethired.validator import ats_check
from gethired.writer import Writer, _current_tracer

DEFAULT_DATA_DIR: Final[Path] = Path("data")
DEFAULT_TAILORED_DIR: Final[Path] = Path("tailored")
DEFAULT_CACHE_DIR: Final[Path] = DEFAULT_DATA_DIR / "jd_cache"
DEFAULT_MASTER_JSON: Final[Path] = DEFAULT_DATA_DIR / "master.json"


class Tailor:
    """Main entry point for the gethired system.

    Example::

        tailor = Tailor(resume="resume.tex", job_description="https://example.com/jd", debug=True)
        result = tailor.run()
    """

    def __init__(
        self,
        resume: MasterResume | str | Path,
        job_description: JobDescription | str | tuple[JobDescription | str, ...],
        debug: bool = False,
        model: str | None = None,
        model_instance: object | None = None,
        draft_model: str | None = None,
        data_dir: Path = DEFAULT_DATA_DIR,
        tailored_dir: Path = DEFAULT_TAILORED_DIR,
        produce_cover_letter: bool = False,
    ) -> None:
        """Construct the orchestrator.

        Args:
            resume: Master resume or path to ``.tex`` file.
            job_description: One or more job descriptions (or URL strings).
            debug: Enable verbose loguru output.
            model: LLM identifier (e.g. ``"MiniMax-M3"``). Read from ``MODEL`` env var if ``None``.
            model_instance: Pre-constructed model instance for dependency injection
                (typically ``TestModel`` in tests).
            draft_model: Optional cheap model identifier for preflight drafts.
            data_dir: Directory for master.json and JD cache.
            tailored_dir: Directory for tailored run outputs.
            produce_cover_letter: When True, the run also emits ``cover_letter.md``.

        Raises:
            ConfigurationError: If neither ``model`` nor ``model_instance`` is provided.
        """
        configure_logging(debug=debug)
        self._resume_input = resume
        self._jd_input = job_description
        self._debug = debug
        resolved_model = model or os.environ.get(MODEL_ENV_VAR)
        if not resolved_model and model_instance is None:
            raise ConfigurationError(
                "MODEL is required. Set the MODEL env var (e.g. 'MiniMax-M3', "
                "'anthropic:claude-sonnet-4-5', 'openai:gpt-5') and API_KEY "
                "(or ANTHROPIC_API_KEY / OPENAI_API_KEY), or pass "
                "model_instance=TestModel() for offline tests."
            )
        self._model: str = resolved_model if resolved_model else "test"
        self._model_instance = model_instance
        self._draft_model = draft_model
        self._produce_cover_letter = produce_cover_letter
        self._data_dir = Path(data_dir)
        self._tailored_dir = Path(tailored_dir)
        self._cache_dir = Path(data_dir) / "jd_cache"
        self._master_json = Path(data_dir) / "master.json"
        self._logger = step_logger("tailor", debug=debug)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> TailoredResume:
        """Execute the full tailoring pipeline."""
        run = Run(
            id=str(new_uuid()),
            started_at=utcnow_iso(),
            master_hash="",
            jd_urls_hash="",
            model=self._model,
            draft_model=self._draft_model,
        )
        tracer = tracer_for_run(run.id, self._tailored_dir)
        token = _current_tracer.set(tracer)
        try:
            return self.__run_pipeline(tracer, run)
        finally:
            tracer.close()
            _current_tracer.reset(token)

    def __run_pipeline(
        self, tracer: Tracer, run: Run
    ) -> TailoredResume:
        """Inner pipeline implementation; called with an active tracer."""
        with tracer.span("tailor.run", "agent", run_id=run.id):
            master = self.__load_master()
            jds = self.__load_jds()
            profile = build_profile(master)
            analysis = (
                analyze_description_multiple(jds)
                if len(jds) > 1
                else (analyze_description(jds[0]) if jds else None)
            )

        # Refresh the run with hashes once master/jds are loaded.
        master_hash = master.content_hash() if master else ""
        jd_hash = hash_jd_urls(jds)
        run = Run(
            id=run.id,
            started_at=run.started_at,
            master_hash=master_hash,
            jd_urls_hash=jd_hash,
            model=self._model,
            draft_model=self._draft_model,
        )

        writer = Writer(
            model=self._model,
            model_instance=self._model_instance,
            debug=self._debug,
        )
        analysis_for_writer = (
            analysis if analysis is not None else analyze_description(jds[0])
        )
        tailored, writer_jobs = writer.tailor(
            master=master,
            analysis=analysis_for_writer,
            voice=profile,
        )

        critic = Critic(debug=self._debug)
        tex_source = render_tex(tailored)
        txt_source = render_text(tailored)
        ats_report, critic_jobs = critic.evaluate(
            tailored=tailored,
            master=master,
            jds=jds,
            tex_source=tex_source,
            txt_source=txt_source,
            pdf_path=None,
        )

        all_jobs = writer_jobs + critic_jobs
        tailored_with_jobs = replace(tailored, jobs=all_jobs)

        run_result = RunResult(
            run=run,
            completed_at=utcnow_iso(),
            duration_seconds=0.0,
            total_input_tokens=0,
            total_output_tokens=0,
            retry_attempts=0,
            final_outcome=outcome_from_ats(ats_report),
            jobs=all_jobs,
        )
        tailored_with_jobs = replace(tailored_with_jobs, run_result=run_result)

        pdf_path = self.__compile_pdf_best_effort(tailored_with_jobs, tex_source)
        if pdf_path is not None:
            ats_report, critic_jobs = critic.evaluate(
                tailored=tailored_with_jobs,
                master=master,
                jds=jds,
                tex_source=tex_source,
                txt_source=txt_source,
                pdf_path=pdf_path,
            )
            tailored_with_jobs = replace(
                tailored_with_jobs,
                jobs=tuple(j for j in tailored_with_jobs.jobs if j.type.value != "validate_ats")
                + critic_jobs,
            )

        self.__persist(tailored_with_jobs, tex_source, txt_source, ats_report)

        if self._produce_cover_letter and analysis is not None:
            cover_result = tailor_cover_letter(
                master=master, analysis=analysis, voice=profile
            )
            cover_md = render_cover_letter_markdown(cover_result.cover_letter)
            run_dir = self._tailored_dir / tailored_with_jobs.run.id
            (run_dir / "cover_letter.md").write_text(cover_md)
            self._logger.info("Cover letter written", path=str(run_dir / "cover_letter.md"))
            return tailored_with_jobs

        return tailored_with_jobs

    def plan(self) -> dict[str, object]:
        """Estimate cost without executing the agent.

        Returns:
            A dict containing token estimates, gate expectations, and metadata.
        """
        master = self.__load_master()
        jds = self.__load_jds()
        profile = build_profile(master)
        analysis = (
            analyze_description_multiple(jds)
            if len(jds) > 1
            else (analyze_description(jds[0]) if jds else None)
        )

        bullets = sum(len(exp.bullets) for exp in master.experiences) + sum(
            len(p.bullets) for p in master.projects
        )
        tokens_estimate = 2_500 + bullets * 150
        return {
            "model": self._model,
            "tokens_estimate": tokens_estimate,
            "bullet_count": bullets,
            "jd_count": len(jds),
            "must_have_keywords": list(analysis.must_have_skills) if analysis else [],
            "voice_profile": {
                "avg_bullet_length": profile.avg_bullet_length,
                "opening_verbs": list(profile.opening_verbs[:5]),
            },
        }

    def preflight(self) -> PreflightReport:
        """Estimate cost and gate outcomes without invoking the LLM.

        Returns:
            A ``PreflightReport`` summarising token estimate, expected ATS
            gates, JD keyword coverage, voice drift risk, and any must-have
            keywords missing from the master.
        """
        master = self.__load_master()
        jds = self.__load_jds()
        profile = build_profile(master)
        analysis = (
            analyze_description_multiple(jds)
            if len(jds) > 1
            else (analyze_description(jds[0]) if jds else None)
        )
        bullets = sum(len(exp.bullets) for exp in master.experiences) + sum(
            len(p.bullets) for p in master.projects
        )
        tokens_estimate = 2_500 + bullets * 150
        coverage: dict[str, float] = {}
        master_text = master.to_markdown().lower()
        if analysis is not None:
            for keyword in analysis.must_have_skills:
                coverage[keyword] = float(keyword.lower() in master_text)
        missing = tuple(
            kw for kw, score in coverage.items() if score < 1.0
        ) if analysis is not None else ()
        expected_gates = (
            "ATS_HARD_PASS",
            "BULLETS_QUANTIFIED",
            "ACTION_VERBS_FIRST",
        )
        voice_drift_risk = min(1.0, bullets / max(profile.avg_bullet_length, 1) / 100)
        return PreflightReport(
            tokens_estimate=tokens_estimate,
            expected_gates=expected_gates,
            jd_keyword_coverage=coverage,
            voice_drift_risk=voice_drift_risk,
            missing_must_haves=missing,
        )

    def finalize(self, edited_json_path: Path) -> TailoredResume:
        """Re-render an edited tailored.json without invoking the agent.

        Args:
            edited_json_path: Path to a hand-edited TailoredResume JSON.

        Returns:
            The re-rendered TailoredResume.
        """
        data = json.loads(Path(edited_json_path).read_text())

        contact = ContactInformation(**data["contact"])
        skills = SkillsByCategory(
            categories={k: tuple(v) for k, v in data["skills"]["categories"].items()}
        )
        experiences = tuple(
            Experience(
                role=e["role"],
                company=e["company"],
                start_date=e["start_date"],
                end_date=e["end_date"],
                bullets=coerce_bullets(e["bullets"]),
            )
            for e in data["experiences"]
        )
        projects = tuple(
            Project(name=p["name"], url=p["url"], bullets=coerce_bullets(p["bullets"]))
            for p in data["projects"]
        )
        education = tuple(Education(**e) for e in data["education"])
        awards = tuple(Award(**a) for a in data["awards"])
        run = Run(**data["run_result"]["run"])
        run_result = RunResult(**data["run_result"])
        tailored = TailoredResume(
            contact=contact,
            summary=data["summary"],
            skills=skills,
            experiences=experiences,
            projects=projects,
            education=education,
            awards=awards,
            dropped=tuple(DropReason(**d) for d in data.get("dropped", [])),
            rationale=data.get("rationale", ""),
            grounding=tuple(GroundedCitation(**g) for g in data.get("grounding", [])),
            jobs=(),
            run_result=run_result,
        )
        tex_source = render_tex(tailored)
        txt_source = render_text(tailored)
        json_source = render_json(tailored)
        ats_report = ats_check(
            tailored,
            tex_source=tex_source,
            pdf_path=None,
            txt_source=txt_source,
            jds=(),
        )
        run_dir = Path(edited_json_path).parent
        (run_dir / "tailored.tex").write_text(tex_source)
        (run_dir / "tailored.txt").write_text(txt_source)
        (run_dir / "tailored.json").write_text(json_source)
        (run_dir / "match_report.md").write_text(
            render_match_report(run, run_result, tailored, ats_report)
        )
        return tailored

    def diff(self, other_run_id: str) -> str:
        """Return a markdown diff between this run and a prior run."""
        current = self.__load_report()
        prior = (self._tailored_dir / other_run_id / "match_report.md").read_text()
        return "\n".join(
            difflib.unified_diff(
                prior.splitlines(),
                current.splitlines(),
                fromfile=other_run_id,
                tofile="current",
                lineterm="",
            )
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def __load_master(self) -> MasterResume:
        if isinstance(self._resume_input, MasterResume):
            return self._resume_input
        if self._master_json.exists():
            return read_master_json(self._master_json)
        master = parse_tex(Path(self._resume_input))
        self._master_json.parent.mkdir(parents=True, exist_ok=True)
        self._master_json.write_text(render_json(to_tailored(master)))
        return master

    def __load_jds(self) -> tuple[JobDescription, ...]:
        if isinstance(self._jd_input, JobDescription):
            return (self._jd_input,)
        if isinstance(self._jd_input, tuple):
            if all(isinstance(j, JobDescription) for j in self._jd_input):
                jds_input = tuple(j for j in self._jd_input if isinstance(j, JobDescription))
                return jds_input
            urls: tuple[str, ...] = tuple(j for j in self._jd_input if isinstance(j, str))
            if urls and len(urls) != len(self._jd_input):
                raise TypeError(
                    "job_description tuple must contain only JobDescription or only str"
                )
            retriever = JobDescriptionRetriever(self._cache_dir)
            return tuple(retriever.retrieve(url) for url in urls)
        retriever = JobDescriptionRetriever(self._cache_dir)
        jd = retriever.retrieve(self._jd_input)
        return (jd,)

    def __persist(
        self,
        tailored: TailoredResume,
        tex_source: str,
        txt_source: str,
        ats_report,
    ) -> Path:
        run_dir = self._tailored_dir / tailored.run.id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "tailored.tex").write_text(tex_source)
        (run_dir / "tailored.txt").write_text(txt_source)
        (run_dir / "tailored.json").write_text(render_json(tailored))
        if tailored.run_result is not None:
            (run_dir / "match_report.md").write_text(
                render_match_report(
                    tailored.run, tailored.run_result, tailored, ats_report
                )
            )
        return run_dir

    def __load_report(self) -> str:
        runs = sorted(self._tailored_dir.iterdir(), key=lambda p: p.stat().st_mtime)
        if not runs:
            raise ResumeTailoringError("No runs found")
        return (runs[-1] / "match_report.md").read_text()

    def __compile_pdf_best_effort(
        self, tailored: TailoredResume, tex_source: str
    ) -> Path | None:
        """Compile the tailored TeX into a PDF.

        Returns ``None`` when ``LATEX_ENGINE=none`` (intentional skip) or when
        the compiled PDF does not materialise on disk. Compilation failures
        propagate as ``PdfCompilationError`` — the caller decides whether to
        log and continue or abort.
        """
        run_dir = self._tailored_dir / tailored.run.id
        pdf_path = compile_pdf(tex_source, run_dir)
        if pdf_path is None:
            self._logger.info("PDF compilation skipped (LATEX_ENGINE=none)")
            return None
        self._logger.info("PDF compiled", path=str(pdf_path))
        return pdf_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def coerce_bullets(items: list[dict[str, str]]) -> tuple[Bullet, ...]:
    """Map a list of ``{"text": str}`` dicts to a tuple of ``Bullet`` values."""
    return tuple(Bullet(text=item["text"]) for item in items)


def new_uuid() -> str:
    return str(uuid4())


def hash_jd_urls(jds: tuple[JobDescription, ...]) -> str:
    blob = "|".join(jd.url for jd in jds)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def outcome_from_ats(report) -> FinalOutcome:
    if report.all_passed:
        return FinalOutcome.SUCCESS
    if report.failed_gates:
        return FinalOutcome.ATS_HARD_FAIL
    return FinalOutcome.SUCCESS


def read_master_json(path: Path) -> MasterResume:
    """Reconstruct a MasterResume from a previously written JSON snapshot.

    The JSON snapshot is produced by ``render_json`` against a TailoredResume;
    we recover only the master fields.
    """
    data = json.loads(path.read_text())
    contact = ContactInformation(**data["contact"])
    skills = SkillsByCategory(
        categories={k: tuple(v) for k, v in data["skills"]["categories"].items()}
    )

    experiences = tuple(
        Experience(
            role=e["role"],
            company=e["company"],
            start_date=e["start_date"],
            end_date=e["end_date"],
            bullets=coerce_bullets(e["bullets"]),
        )
        for e in data["experiences"]
    )
    projects = tuple(
        Project(name=p["name"], url=p["url"], bullets=coerce_bullets(p["bullets"]))
        for p in data["projects"]
    )
    education = tuple(Education(**e) for e in data["education"])
    awards = tuple(Award(**a) for a in data["awards"])
    return MasterResume(
        contact=contact,
        summary=data["summary"],
        skills=skills,
        experiences=experiences,
        projects=projects,
        education=education,
        awards=awards,
    )


def to_tailored(master: MasterResume) -> TailoredResume:
    """Wrap a master resume in a TailoredResume for JSON serialisation."""
    return TailoredResume(
        contact=master.contact,
        summary=master.summary,
        skills=master.skills,
        experiences=master.experiences,
        projects=master.projects,
        education=master.education,
        awards=master.awards,
        dropped=(),
        rationale="Master snapshot",
        grounding=(),
        jobs=(),
        run_result=RunResult(
            run=Run(
                id=str(new_uuid()),
                started_at=utcnow_iso(),
                master_hash=master.content_hash(),
                jd_urls_hash="",
                model="master",
                draft_model=None,
            ),
            completed_at=utcnow_iso(),
            duration_seconds=0.0,
            total_input_tokens=0,
            total_output_tokens=0,
            retry_attempts=0,
            final_outcome=FinalOutcome.SUCCESS,
            jobs=(),
        ),
    )


__all__ = ["DEFAULT_CACHE_DIR", "DEFAULT_DATA_DIR", "DEFAULT_MASTER_JSON", "Tailor"]
