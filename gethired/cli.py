"""CLI for gethired.

Uniform ``verb noun`` command pattern.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from gethired.constants import (
    CONSENT_FILE_PATH,
    CONSENT_RE_PROMPT_DAYS,
    CONSENT_TEXT,
    DEFAULT_MASTER_JSON,
)
from gethired.constants import DEFAULT_DATA_DIR as _DEFAULT_DATA_DIR_STR
from gethired.constants import DEFAULT_TAILORED_DIR as _DEFAULT_TAILORED_DIR_STR

DEFAULT_DATA_DIR_PATH = Path(_DEFAULT_DATA_DIR_STR)
DEFAULT_TAILORED_DIR_PATH = Path(_DEFAULT_TAILORED_DIR_STR)
DEFAULT_MASTER_JSON_PATH = Path(DEFAULT_MASTER_JSON)
from gethired.exceptions import (
    AtsGateFailureError,
    GroundingViolationError,
    JobDescriptionRetrievalError,
    PlagiarismViolationError,
    StyleViolationError,
)
from gethired.fetcher import JobDescriptionRetriever
from gethired.models import JobDescription
from gethired.observability import configure_logging
from gethired.parser import parse_tex
from gethired.renderer import render_json
from gethired.tailor import Tailor

app = typer.Typer(help="gethired — multi-agent CV tailoring", no_args_is_help=True)


def ensure_consent(force_prompt: bool = False) -> None:
    consent_file = Path(CONSENT_FILE_PATH).expanduser()
    if consent_file.exists() and not force_prompt:
        try:
            import datetime as _dt

            data = json.loads(consent_file.read_text())
            timestamp = _dt.datetime.fromisoformat(data["timestamp"])
            now = _dt.datetime.now(timestamp.tzinfo) if timestamp.tzinfo else _dt.datetime.utcnow()
            if (now - timestamp).days < CONSENT_RE_PROMPT_DAYS:
                return
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

    typer.echo(CONSENT_TEXT, err=True)
    if not typer.confirm("Continue?", default=False):
        raise typer.Exit(code=1)

    consent_file.parent.mkdir(parents=True, exist_ok=True)
    import datetime as _dt

    consent_file.write_text(
        json.dumps({"timestamp": _dt.datetime.now(_dt.UTC).isoformat()})
    )


@app.command()
def ingest(
    tex_path: Path = typer.Argument(..., exists=True, readable=True),
    out: Path = typer.Option(DEFAULT_MASTER_JSON_PATH, "--out", "-o"),
) -> None:
    """Parse master resume into data/master.json."""
    configure_logging()
    ensure_consent()
    master = parse_tex(tex_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    snapshot = render_json(master_to_snapshot(master))
    out.write_text(snapshot)
    typer.echo(f"Ingested {tex_path} → {out}")


@app.command()
def fetch(
    urls: list[str] = typer.Argument(...),
    cache_dir: Path = typer.Option(DEFAULT_DATA_DIR_PATH / "jd_cache", "--cache"),
) -> None:
    """Fetch and cache job description URLs."""
    configure_logging()
    ensure_consent()
    retriever = JobDescriptionRetriever(cache_dir)
    for url in urls:
        try:
            jd = retriever.retrieve(url)
            typer.echo(f"Fetched {url} → {jd.title or '(no title)'}")
        except JobDescriptionRetrievalError as exc:
            typer.echo(f"Failed: {url}: {exc}", err=True)
            raise typer.Exit(code=1)


@app.command(name="show")
def show_cmd(
    what: str = typer.Argument(..., help="'master' or 'jd'"),
    url: str | None = typer.Option(None, "--url"),
) -> None:
    """Show master.json or a cached JD."""
    configure_logging()
    if what == "master":
        if not DEFAULT_MASTER_JSON_PATH.exists():
            typer.echo(f"master.json not found at {DEFAULT_MASTER_JSON_PATH}", err=True)
            raise typer.Exit(code=1)
        typer.echo(DEFAULT_MASTER_JSON_PATH.read_text())
    elif what == "jd":
        if url is None:
            typer.echo("--url required for jd", err=True)
            raise typer.Exit(code=1)
        import hashlib

        url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
        cache_path = DEFAULT_DATA_DIR_PATH / "jd_cache" / f"{url_hash}.json"
        if not cache_path.exists():
            typer.echo(f"JD not cached: {url}", err=True)
            raise typer.Exit(code=1)
        typer.echo(cache_path.read_text())
    else:
        typer.echo("Usage: gethired show master | gethired show jd --url URL", err=True)
        raise typer.Exit(code=1)


@app.command()
def plan(
    urls: list[str] = typer.Argument(...),
    resume: Path = typer.Option(Path("resume.tex"), "--resume", "-r"),
    model: str | None = typer.Option(None, "--model", "-m"),
) -> None:
    """Estimate cost without running the agent."""
    configure_logging()
    ensure_consent()
    jd = fetch_first_jd(urls)
    tailor = Tailor(resume=resume, job_description=jd, model=model)
    plan_data = tailor.plan()
    typer.echo(json.dumps(plan_data, indent=2))


@app.command()
def run(
    urls: list[str] = typer.Argument(...),
    resume: Path = typer.Option(Path("resume.tex"), "--resume", "-r"),
    model: str | None = typer.Option(None, "--model", "-m"),
    debug: bool = typer.Option(False, "--debug", "-d"),
    out_dir: Path = typer.Option(DEFAULT_TAILORED_DIR_PATH, "--out-dir"),
) -> None:
    """Run the full tailoring pipeline."""
    configure_logging(debug=debug)
    ensure_consent()
    jd = fetch_first_jd(urls)
    tailor = Tailor(
        resume=resume, job_description=jd, model=model, debug=debug, tailored_dir=out_dir
    )
    try:
        tailored = tailor.run()
    except (
        GroundingViolationError,
        StyleViolationError,
        PlagiarismViolationError,
        AtsGateFailureError,
    ) as exc:
        typer.echo(f"Tailoring failed: {exc}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"Run complete: {tailored.run.id}")
    typer.echo(f"Output: {out_dir / tailored.run.id}")


@app.command()
def validate(
    target: Path = typer.Argument(..., exists=True),
) -> None:
    """Run ATS gates against a tailored.tex or tailored.json."""
    configure_logging()
    if target.suffix == ".json":
        from gethired.tailor import _read_master_json

        data = json.loads(target.read_text())
        from gethired.models import (
            Award,
            Bullet,
            ContactInformation,
            Education,
            Experience,
            Project,
            Run,
            RunResult,
            SkillsByCategory,
            TailoredResume,
        )

        def _bullet(text: str) -> Bullet:
            return Bullet(text=text)

        def _bullets(items: list[dict]) -> tuple[Bullet, ...]:
            return tuple(_bullet(b["text"]) for b in items)

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
                bullets=_bullets(e["bullets"]),
            )
            for e in data["experiences"]
        )
        projects = tuple(
            Project(name=p["name"], url=p["url"], bullets=_bullets(p["bullets"]))
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
            dropped=(),
            rationale=data.get("rationale", ""),
            grounding=(),
            jobs=(),
            run_result=run_result,
        )
        master = _read_master_json(Path("data/master.json"))
        tex_source = target.read_text() if target.suffix == ".tex" else ""
        from gethired.renderer import render_tex

        tex_source = render_tex(tailored)
        from gethired.renderer import render_text

        txt_source = render_text(tailored)
        from gethired.validator import ats_check

        report = ats_check(
            tailored,
            tex_source=tex_source,
            pdf_path=None,
            txt_source=txt_source,
            jds=(),
        )
    else:
        typer.echo("Provide a tailored.json (tex-only validation not yet supported)", err=True)
        raise typer.Exit(code=1)
    if report.all_passed:
        typer.echo("All ATS gates passed")
    else:
        typer.echo(f"Failed gates: {[g.value for g in report.failed_gates]}")
        raise typer.Exit(code=1)


@app.command()
def trace(
    run_dir: Path = typer.Argument(..., exists=True),
) -> None:
    """Print the Job trail of a previous run."""
    configure_logging()
    json_path = run_dir / "tailored.json"
    if not json_path.exists():
        typer.echo(f"tailored.json not found in {run_dir}", err=True)
        raise typer.Exit(code=1)
    data = json.loads(json_path.read_text())
    run_result = data.get("run_result", {})
    jobs = run_result.get("jobs", [])
    typer.echo(f"Run: {run_result.get('run', {}).get('id', '?')}")
    typer.echo(f"Outcome: {run_result.get('final_outcome', '?')}")
    typer.echo(f"Jobs: {len(jobs)}")
    for idx, job in enumerate(jobs, start=1):
        typer.echo(
            f"  {idx}. [{job.get('type')}] {job.get('rationale')[:80]}"
        )


@app.command()
def diff(
    run_a: str = typer.Argument(...),
    run_b: str = typer.Argument(...),
    out_dir: Path = typer.Option(DEFAULT_TAILORED_DIR_PATH, "--out-dir"),
) -> None:
    """Diff two tailored runs."""
    configure_logging()
    a = (out_dir / run_a / "match_report.md").read_text()
    b = (out_dir / run_b / "match_report.md").read_text()
    import difflib

    diff_text = "\n".join(
        difflib.unified_diff(
            a.splitlines(), b.splitlines(), fromfile=run_a, tofile=run_b, lineterm=""
        )
    )
    typer.echo(diff_text)


def fetch_first_jd(urls: list[str]) -> JobDescription:
    retriever = JobDescriptionRetriever(DEFAULT_DATA_DIR_PATH / "jd_cache")
    return retriever.retrieve(urls[0])


def master_to_snapshot(master) -> object:
    """Wrap a master into a TailoredResume-like snapshot for JSON serialisation."""
    from uuid import uuid4

    from gethired.models import (
        FinalOutcome,
        Run,
        RunResult,
        TailoredResume,
    )
    from gethired.observability import utcnow_iso

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
                id=str(uuid4()),
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


if __name__ == "__main__":
    app()
