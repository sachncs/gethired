"""CLI for gethired.

Uniform ``verb noun`` command pattern.
"""

from __future__ import annotations

import difflib
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import typer

import gethired.audit as audit_module
from gethired.audit import (
    audit_json,
    audit_markdown,
)
from gethired.constants import (
    CONSENT,
    CONSENT_DAYS,
    CONSENT_PATH,
    DATA_DIR,
    MASTER,
    OUTPUT_DIR,
)
from gethired.exceptions import (
    AtsError,
    FetchError,
    GroundingError,
    PlagiarismError,
    StyleError,
)
from gethired.fetcher import Fetcher
from gethired.models import (
    Job,
)
from gethired.observability import configure
from gethired.parser import parse_tex as parse_tex_func
from gethired.renderer import tex as render_tex
from gethired.renderer import text as render_text
from gethired.serialize import (
    from_tailored_dict,
    render_json,
    snapshot,
)
from gethired.tailor import Tailor
from gethired.validator import ats

DEFAULT_DATA_DIR_PATH = Path(DATA_DIR)
DEFAULT_TAILORED_DIR_PATH = Path(OUTPUT_DIR)
DEFAULT_MASTER_JSON_PATH = Path(MASTER)

app = typer.Typer(help="gethired — multi-agent CV tailoring", no_args_is_help=True)


def ensure_consent(force_prompt: bool = False) -> None:
    consent_file = Path(CONSENT_PATH).expanduser()
    if consent_file.exists() and not force_prompt:
        try:
            data_dict = json.loads(consent_file.read_text())
            timestamp = datetime.fromisoformat(data_dict["timestamp"])
            if timestamp.tzinfo is None:
                now = datetime.now(UTC).replace(tzinfo=None)
            else:
                now = datetime.now(timestamp.tzinfo)
            if (now - timestamp).days < CONSENT_DAYS:
                return
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

    typer.echo(CONSENT, err=True)
    if not typer.confirm("Continue?", default=False):
        raise typer.Exit(code=1)

    consent_file.parent.mkdir(parents=True, exist_ok=True)
    consent_file.write_text(json.dumps({"timestamp": datetime.now(UTC).isoformat()}))


@app.command()
def ingest(
    tex_path: Path = typer.Argument(..., exists=True, readable=True),
    out: Path = typer.Option(DEFAULT_MASTER_JSON_PATH, "--out", "-o"),
) -> None:
    """Parse master resume into data/master.json."""
    configure()
    ensure_consent()
    master = parse_tex_func(tex_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = render_json(snapshot(master))
    out.write_text(payload)
    typer.echo(f"Ingested {tex_path} → {out}")


@app.command()
def fetch(
    urls: list[str] = typer.Argument(...),
    cache_dir: Path = typer.Option(DEFAULT_DATA_DIR_PATH / "jd_cache", "--cache"),
) -> None:
    """Fetch and cache job description URLs."""
    configure()
    ensure_consent()
    retriever = Fetcher(cache_dir)
    for url in urls:
        try:
            jd = retriever.retrieve(url)
            typer.echo(f"Fetched {url} → {jd.title or '(no title)'}")
        except FetchError as exc:
            typer.echo(f"Failed: {url}: {exc}", err=True)
            raise typer.Exit(code=1)


@app.command(name="show")
def show_cmd(
    what: str = typer.Argument(..., help="'master' or 'jd'"),
    url: str | None = typer.Option(None, "--url"),
) -> None:
    """Show master.json or a cached JD."""
    configure()
    if what == "master":
        if not DEFAULT_MASTER_JSON_PATH.exists():
            typer.echo(f"master.json not found at {DEFAULT_MASTER_JSON_PATH}", err=True)
            raise typer.Exit(code=1)
        typer.echo(DEFAULT_MASTER_JSON_PATH.read_text())
    elif what == "jd":
        if url is None:
            typer.echo("--url required for jd", err=True)
            raise typer.Exit(code=1)
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
    configure()
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
    configure(debug=debug)
    ensure_consent()
    jd = fetch_first_jd(urls)
    tailor = Tailor(
        resume=resume, job_description=jd, model=model, debug=debug, tailored_dir=out_dir
    )
    try:
        tailored = tailor.run()
    except (
        GroundingError,
        StyleError,
        PlagiarismError,
        AtsError,
    ) as exc:
        typer.echo(f"Tailoring failed: {exc}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"Run complete: {tailored.run.id}")
    typer.echo(f"Output: {out_dir / tailored.run.id}")


@app.command()
def cover(
    urls: list[str] = typer.Argument(...),
    resume: Path = typer.Option(Path("resume.tex"), "--resume", "-r"),
    model: str | None = typer.Option(None, "--model", "-m"),
    debug: bool = typer.Option(False, "--debug", "-d"),
    out_dir: Path = typer.Option(DEFAULT_TAILORED_DIR_PATH, "--out-dir"),
) -> None:
    """Run the pipeline with cover-letter production enabled."""
    configure(debug=debug)
    ensure_consent()
    jd = fetch_first_jd(urls)
    tailor = Tailor(
        resume=resume,
        job_description=jd,
        model=model,
        debug=debug,
        tailored_dir=out_dir,
        produce_cover_letter=True,
    )
    try:
        tailored = tailor.run()
    except (
        GroundingError,
        StyleError,
        PlagiarismError,
        AtsError,
    ) as exc:
        typer.echo(f"Tailoring failed: {exc}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"Run complete: {tailored.run.id}")
    typer.echo(f"Cover letter: {out_dir / tailored.run.id / 'cover_letter.md'}")


@app.command()
def preflight(
    urls: list[str] = typer.Argument(...),
    resume: Path = typer.Option(Path("resume.tex"), "--resume", "-r"),
    model: str | None = typer.Option(None, "--model", "-m"),
) -> None:
    """Dry-run preflight: estimate cost and gate outcomes without invoking the LLM."""
    configure()
    ensure_consent()
    jd = fetch_first_jd(urls)
    tailor = Tailor(resume=resume, job_description=jd, model=model, debug=False)
    report = tailor.preflight()
    typer.echo("Preflight report")
    typer.echo(f"  Tokens estimate: {report.tokens_estimate}")
    typer.echo(f"  Expected gates:  {', '.join(report.expected_gates)}")
    typer.echo(f"  Voice drift risk: {report.voice_drift_risk:.2f}")
    typer.echo(f"  Missing must-haves: {', '.join(report.missing_must_haves) or 'none'}")
    for keyword, coverage in report.jd_keyword_coverage.items():
        typer.echo(f"  Keyword '{keyword}': {coverage:.0%}")


@app.command()
def validate(
    target: Path = typer.Argument(..., exists=True),
) -> None:
    """Run ATS gates against a tailored.tex or tailored.json."""
    configure()
    if target.suffix == ".json":
        data_dict = json.loads(target.read_text())
        tailored = from_tailored_dict(data_dict)
        tex_source = render_tex(tailored)
        txt_source = render_text(tailored)
        report = ats(
            tailored,
            tex_source=tex_source,
            pdf_path=None,
            txt_source=txt_source,
            jds=(),
        )
    else:
        typer.echo("Provide a tailored.json (tex-only validation not yet supported)", err=True)
        raise typer.Exit(code=1)
    if report.hard_failed_gates:
        typer.echo(f"Hard-failed gates: {[g.value for g in report.hard_failed_gates]}")
        raise typer.Exit(code=1)
    if report.advisory_failed_gates:
        typer.echo(
            f"Advisory-failed gates (non-blocking): "
            f"{[g.value for g in report.advisory_failed_gates]}"
        )
    if report.skipped_gates:
        typer.echo(f"Skipped gates: {[g.value for g in report.skipped_gates]}")
    typer.echo("All hard ATS gates passed")


@app.command()
def trace(
    run_dir: Path = typer.Argument(..., exists=True),
) -> None:
    """Print the Job trail of a previous run."""
    configure()
    json_path = run_dir / "tailored.json"
    if not json_path.exists():
        typer.echo(f"tailored.json not found in {run_dir}", err=True)
        raise typer.Exit(code=1)
    data_dict = json.loads(json_path.read_text())
    run_result = data_dict.get("run_result", {})
    jobs = run_result.get("jobs", [])
    typer.echo(f"Run: {run_result.get('run', {}).get('id', '?')}")
    typer.echo(f"Outcome: {run_result.get('final_outcome', '?')}")
    typer.echo(f"Jobs: {len(jobs)}")
    for idx, job in enumerate(jobs, start=1):
        typer.echo(f"  {idx}. [{job.get('type')}] {job.get('rationale')[:80]}")


@app.command(name="audit")
def audit_cmd(
    run_dir: Path = typer.Argument(..., exists=True),
) -> None:
    """Re-run all validators against a previous run directory.

    Writes ``audit.json`` and ``audit.md`` into ``run_dir``. Exits non-zero
    if any validator reports a failure.
    """
    configure()
    report = audit_module.audit(run_dir)
    (Path(run_dir) / "audit.json").write_text(audit_json(report))
    (Path(run_dir) / "audit.md").write_text(audit_markdown(report))
    typer.echo(f"Audit written to {run_dir}/audit.json and audit.md")
    typer.echo(f"ATS passed: {report.ats_passed}")
    typer.echo(
        f"ATS advisory failed: {len(report.ats_advisory_failed_gates)} "
        f"| skipped: {len(report.ats_skipped_gates)}"
    )
    typer.echo(
        f"Violations: grounding={len(report.grounding_violations)} "
        f"style={len(report.style_violations)} "
        f"plagiarism={len(report.plagiarism_violations)}"
    )
    if (
        not report.ats_passed
        or report.grounding_violations
        or report.style_violations
        or report.plagiarism_violations
    ):
        raise typer.Exit(code=1)


@app.command()
def diff(
    run_a: str = typer.Argument(...),
    run_b: str = typer.Argument(...),
    out_dir: Path = typer.Option(DEFAULT_TAILORED_DIR_PATH, "--out-dir"),
) -> None:
    """Diff two tailored runs."""
    configure()
    a = (out_dir / run_a / "match_report.md").read_text()
    b = (out_dir / run_b / "match_report.md").read_text()
    diff_text = "\n".join(
        difflib.unified_diff(
            a.splitlines(), b.splitlines(), fromfile=run_a, tofile=run_b, lineterm=""
        )
    )
    typer.echo(diff_text)


def fetch_first_jd(urls: list[str]) -> Job:
    retriever = Fetcher(DEFAULT_DATA_DIR_PATH / "jd_cache")
    return retriever.retrieve(urls[0])


if __name__ == "__main__":
    app()
