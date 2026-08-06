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

from gethired.constants import (
    DRIFT_SCALE,
    MODEL_VAR,
    TOKENS_BASE,
    TOKENS_BULLET,
)
from gethired.cover_letter import (
    compose,
    markdown,
)
from gethired.critic import Critic
from gethired.description import analyze_description
from gethired.exceptions import (
    ConfigError,
    TailorError,
)
from gethired.fetcher import Fetcher
from gethired.merger import safe_merge
from gethired.models import (
    Job,
Resume,
    Outcome,
    Report,
    Run,
    RunResult,
    Step,
    StepKind,
    Tailored,
)
from gethired.observability import configure, logger, now
from gethired.parser import parse_tex
from gethired.profiler import build as build_profile
from gethired.render_pdf import compile_pdf
from gethired.renderer import (
    report as render_report,
)
from gethired.renderer import (
    tex as render_tex,
)
from gethired.renderer import (
    text as render_text,
)
from gethired.serialize import (
    from_bullets,
    from_tailored_dict,
    load_master,
    render_json,
    snapshot,
)
from gethired.tracing import Tracer, tracer
from gethired.validator import AtsReport, ats
from gethired.writer import Writer, current_tracer

DATA_DIR: Final[Path] = Path("data")
OUTPUT_DIR: Final[Path] = Path("tailored")
CACHE_DIR: Final[Path] = DATA_DIR / "jd_cache"
MASTER: Final[Path] = DATA_DIR / "master.json"


class Tailor:
    """Main entry point for the gethired system.

    Example::

        tailor = Tailor(resume="sample.tex", job_description="https://example.com/jd", debug=True)
        result = tailor.run()
    """

    def __init__(
        self,
        resume: Resume | str | Path,
        job_description: Job | str | tuple[Job | str, ...],
        debug: bool = False,
        model: str | None = None,
        model_instance: object | None = None,
        draft_model: str | None = None,
        data_dir: Path = DATA_DIR,
        tailored_dir: Path = OUTPUT_DIR,
        produce_cover_letter: bool = False,
    ) -> None:
        """Construct the orchestrator.

        Args:
            resume: Resume or path to ``.tex`` file.
            job_description: One or more job descriptions (or URL strings).
            debug: Enable verbose loguru output.
            model: LLM identifier (e.g. ``"MiniMax-M3"``). Read from ``MODEL`` env var if ``None``.
            model_instance: Pre-constructed model instance for dependency injection
                (typically ``TestModel`` in tests).
            draft_model: Optional cheap model identifier for preflight drafts.
            data_dir: Directory for resume.json and JD cache.
            tailored_dir: Directory for tailored run outputs.
            produce_cover_letter: When True, the run also emits ``cover_letter.md``.

        Raises:
            ConfigError: If neither ``model`` nor ``model_instance`` is provided.
        """
        configure(debug=debug)
        self.resume_input = resume
        self.jd_input = job_description
        self.debug = debug
        resolved_model = model or os.environ.get(MODEL_VAR)
        if not resolved_model and model_instance is None:
            raise ConfigError(
                "MODEL is required. Set the MODEL env var (e.g. 'MiniMax-M3', "
                "'anthropic:claude-sonnet-4-5', 'openai:gpt-5') and API_KEY "
                "(or ANTHROPIC_API_KEY / OPENAI_API_KEY), or pass "
                "model_instance=TestModel() for offline tests."
            )
        self.model: str = resolved_model if resolved_model else "test"
        self.model_instance = model_instance
        self.draft_model = draft_model
        self.produce_cover_letter = produce_cover_letter
        self.data_dir = Path(data_dir)
        self.tailored_dir = Path(tailored_dir)
        self.cache_dir = Path(data_dir) / "jd_cache"
        self.master_json = Path(data_dir) / "resume.json"
        self.cached_resume: Resume | None = None
        self.logger = logger("tailor", debug=debug)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> Tailored:
        """Execute the full tailoring pipeline."""
        run = Run(
            id=str(new_uuid()),
            started_at=now(),
            resume_hash="",
            jd_hash="",
            model=self.model,
            draft_model=self.draft_model,
        )
        t = tracer(run.id, self.tailored_dir)
        token = current_tracer.set(t)
        try:
            return self.__run(t, run)
        finally:
            t.close()
            current_tracer.reset(token)

    def __run(self, t: Tracer, run: Run) -> Tailored:
        """Inner pipeline implementation; called with an active t."""
        with t.span("tailor.run", "agent", run_id=run.id):
            master = self.__load_resume()
            jds = self.__load_jds()
            profile = build_profile(master)
            if jds:
                analysis = safe_merge(
                    jds,
                    model=self.model,
                    model_instance=self.model_instance,
                )
            else:
                analysis = None

        # Refresh the run with hashes once resume/jds are loaded.
        resume_hash = master.content_hash() if master else ""
        jd_hash = hash_urls(jds)
        run = Run(
            id=run.id,
            started_at=run.started_at,
            resume_hash=resume_hash,
            jd_hash=jd_hash,
            model=self.model,
            draft_model=self.draft_model,
        )

        writer = Writer(
            model=self.model,
            model_instance=self.model_instance,
            debug=self.debug,
        )
        analysis_for_writer = analysis if analysis is not None else analyze_description(jds[0])
        tailored, writer_jobs = writer.tailor(
            master=master,
            analysis=analysis_for_writer,
            voice=profile,
        )

        critic = Critic(debug=self.debug)
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
            completed_at=now(),
            duration_seconds=0.0,
            total_input_tokens=0,
            total_output_tokens=0,
            retry_attempts=0,
            final_outcome=outcome(ats_report),
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
            all_jobs = merge_steps(tailored_with_jobs.jobs, critic_jobs)
            run_result = replace(
                run_result,
                final_outcome=outcome(ats_report),
                jobs=all_jobs,
            )
            tailored_with_jobs = replace(tailored_with_jobs, jobs=all_jobs, run_result=run_result)

        self.__persist(tailored_with_jobs, tex_source, txt_source, ats_report)

        final = replace(
            tailored_with_jobs,
            master=master,
            jds=jds,
            analysis=analysis,
        )

        if self.produce_cover_letter and analysis is not None:
            cover_result = compose(master=master, analysis=analysis, voice=profile)
            cover_md = markdown(cover_result.letter)
            run_dir = self.tailored_dir / final.run.id
            (run_dir / "cover_letter.md").write_text(cover_md)
            self.logger.info("Cover letter written", path=str(run_dir / "cover_letter.md"))
            return final

        return final

    def plan(self) -> dict[str, object]:
        """Estimate cost without executing the agent.

        Returns:
            A dict containing token estimates, gate expectations, and metadata.
        """
        master = self.__load_resume()
        jds = self.__load_jds()
        profile = build_profile(master)
        if jds:
            analysis = safe_merge(
                jds,
                model=self.model,
                model_instance=self.model_instance,
            )
        else:
            analysis = None

        bullets = sum(len(exp.bullets) for exp in master.experience) + sum(
            len(p.bullets) for p in master.projects
        )
        tokens_estimate = TOKENS_BASE + bullets * TOKENS_BULLET
        return {
            "model": self.model,
            "tokens_estimate": tokens_estimate,
            "bullet_count": bullets,
            "jd_count": len(jds),
            "must_have_keywords": list(analysis.must_have) if analysis else [],
            "voice_profile": {
                "avg_bullet_length": profile.avg_bullet_length,
                "opening_verbs": list(profile.opening_verbs[:5]),
            },
        }

    def preflight(self) -> Report:
        """Estimate cost and gate outcomes without invoking the LLM.

        Returns:
            A ``Report`` summarising token estimate, expected ATS
            gates, JD keyword coverage, voice drift risk, and any must-have
            keywords missing from the master.
        """
        master = self.__load_resume()
        jds = self.__load_jds()
        profile = build_profile(master)
        if jds:
            analysis = safe_merge(
                jds,
                model=self.model,
                model_instance=self.model_instance,
            )
        else:
            analysis = None
        bullets = sum(len(exp.bullets) for exp in master.experience) + sum(
            len(p.bullets) for p in master.projects
        )
        tokens_estimate = TOKENS_BASE + bullets * TOKENS_BULLET
        coverage: dict[str, float] = {}
        master_text = master.to_markdown().lower()
        if analysis is not None:
            for keyword in analysis.must_have:
                coverage[keyword] = float(keyword.lower() in master_text)
        missing = (
            tuple(kw for kw, score in coverage.items() if score < 1.0)
            if analysis is not None
            else ()
        )
        expected_gates = (
            "ATS_HARD_PASS",
            "BULLETS_QUANTIFIED",
            "ACTION_VERBS_FIRST",
        )
        voice_drift_risk = min(1.0, bullets / max(profile.avg_bullet_length, 1) / DRIFT_SCALE)
        return Report(
            tokens_estimate=tokens_estimate,
            expected_gates=expected_gates,
            jd_keyword_coverage=coverage,
            voice_drift_risk=voice_drift_risk,
            missing_must_haves=missing,
        )

    def finalize(self, edited_json_path: Path) -> Tailored:
        """Re-render an edited tailored.json without invoking the agent.

        Args:
            edited_json_path: Path to a hand-edited Tailored JSON.

        Returns:
            The re-rendered Tailored.
        """
        data_dict = json.loads(Path(edited_json_path).read_text())
        tailored = from_tailored_dict(data_dict)
        if tailored.run_result is None:
            raise TailorError("tailored.json is missing run_result")
        run = tailored.run_result.run
        run_result = tailored.run_result

        tex_source = render_tex(tailored)
        txt_source = render_text(tailored)
        json_source = render_json(tailored)
        ats_report = ats(
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
            render_report(run, run_result, tailored, ats_report)
        )
        return tailored

    def diff(self, other_run_id: str) -> str:
        """Return a markdown diff between this run and a prior run."""
        current = self.__load_report()
        prior = (self.tailored_dir / other_run_id / "match_report.md").read_text()
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

    def __load_resume(self) -> Resume:
        if isinstance(self.resume_input, Resume):
            return self.resume_input
        if self.master_json.exists():
            return load_master(self.master_json)
        resume = parse_tex(Path(self.resume_input))
        self.master_json.parent.mkdir(parents=True, exist_ok=True)
        self.master_json.write_text(render_json(snapshot(resume)))
        return resume

    @property
    def master(self) -> Resume:
        """The parsed resume (read-only). Deprecated alias for :attr:`resume`."""
        if self.cached_resume is None:
            self.cached_resume = self.__load_resume()
        return self.cached_resume

    @property
    def resume(self) -> Resume:
        """The parsed resume (read-only). Loads on first access."""
        if self.cached_resume is None:
            self.cached_resume = self.__load_resume()
        return self.cached_resume

    def __load_jds(self) -> tuple[Job, ...]:
        if isinstance(self.jd_input, Job):
            return (self.jd_input,)
        if isinstance(self.jd_input, tuple):
            if all(isinstance(j, Job) for j in self.jd_input):
                jds_input = tuple(j for j in self.jd_input if isinstance(j, Job))
                return jds_input
            urls: tuple[str, ...] = tuple(j for j in self.jd_input if isinstance(j, str))
            if urls and len(urls) != len(self.jd_input):
                raise TypeError("job_description tuple must contain only Job or only str")
            retriever = Fetcher(self.cache_dir)
            return tuple(retriever.retrieve(url) for url in urls)
        retriever = Fetcher(self.cache_dir)
        jd = retriever.retrieve(self.jd_input)
        return (jd,)

    def __persist(
        self,
        tailored: Tailored,
        tex_source: str,
        txt_source: str,
        ats_report,
    ) -> Path:
        run_dir = self.tailored_dir / tailored.run.id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "tailored.tex").write_text(tex_source)
        (run_dir / "tailored.txt").write_text(txt_source)
        (run_dir / "tailored.json").write_text(render_json(tailored))
        if tailored.run_result is not None:
            (run_dir / "match_report.md").write_text(
                render_report(tailored.run, tailored.run_result, tailored, ats_report)
            )
        return run_dir

    def __load_report(self) -> str:
        runs = sorted(self.tailored_dir.iterdir(), key=lambda p: p.stat().st_mtime)
        if not runs:
            raise TailorError("No runs found")
        return (runs[-1] / "match_report.md").read_text()

    def __compile_pdf_best_effort(self, tailored: Tailored, tex_source: str) -> Path | None:
        """Compile the tailored TeX into a PDF.

        Returns ``None`` when ``LATEX_ENGINE=none`` (intentional skip) or when
        the compiled PDF does not materialise on disk. Compilation failures
        propagate as ``CompileError`` — the caller decides whether to
        log and continue or abort.
        """
        run_dir = self.tailored_dir / tailored.run.id
        pdf_path = compile_pdf(tex_source, run_dir)
        if pdf_path is None:
            self.logger.info("PDF compilation skipped (LATEX_ENGINE=none)")
            return None
        self.logger.info("PDF compiled", path=str(pdf_path))
        return pdf_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def new_uuid() -> str:
    return str(uuid4())


def hash_urls(jds: tuple[Job, ...]) -> str:
    blob = "|".join(jd.url for jd in jds)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def outcome(report: AtsReport) -> Outcome:
    """Map an ATS report to a final run outcome.

    Only hard-tier gate failures block the run; advisory failures and
    skipped PDF gates (no PDF compiled) do not.
    """
    if report.hard_failed_gates:
        return Outcome.ATS_HARD_FAIL
    return Outcome.SUCCESS


VALIDATION: frozenset[StepKind] = frozenset(
    {
        StepKind.VALIDATE_GROUNDING,
        StepKind.VALIDATE_STYLE,
        StepKind.VALIDATE_PLAGIARISM,
        StepKind.VALIDATE_ATS,
    }
)


def merge_steps(existing_jobs: tuple[Step, ...], critic_jobs: tuple[Step, ...]) -> tuple[Step, ...]:
    """Replace previously emitted validation jobs with an authoritative critic pass.

    The critic is re-run after PDF compilation so PDF-dependent gates are
    evaluated against the real artefact. Without dropping every earlier
    validation job, that second pass would duplicate the grounding, style,
    and plagiarism records in the job trail.
    """
    return tuple(job for job in existing_jobs if job.type not in VALIDATION) + critic_jobs


__all__ = [
    "CACHE_DIR",
    "DATA_DIR",
    "MASTER",
    "Tailor",
    "from_bullets",
    "load_master",
    "snapshot",
]
