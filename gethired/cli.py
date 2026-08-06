"""CLI for gethired.

Uniform ``verb noun`` command pattern.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import sys
from datetime import UTC, datetime  # noqa: F401  # legacy imports retained for backward compat
from pathlib import Path

import typer
from dotenv import load_dotenv

import gethired.audit as audit_module
from gethired.audit import (
    audit_json,
    audit_markdown,
)
from gethired.consent import require
from gethired.constants import (
    DATA_DIR,
    MASTER,
    OUTPUT_DIR,
)
from gethired.cover_letter import (
    compose as compose_cover_letter,
)
from gethired.cover_letter import (
    markdown as render_cover_markdown,
)
from gethired.description import (
    overlay_for_jd,
)
from gethired.exceptions import (
    AntiBotError,
    AtsError,
    FetchError,
    GroundingError,
    PlagiarismError,
    StyleError,
)
from gethired.fetcher import Fetcher, from_text
from gethired.models import (
    Job,
)
from gethired.observability import configure
from gethired.parser import parse_tex as parse_tex_func
from gethired.profiler import build as build_profile
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

# Load .env from the current working directory (and the package root as a
# fallback). Existing process env vars win so users can override on the command
# line without editing the file. Idempotent: safe to call from every command.
load_dotenv(Path.cwd() / ".env", override=False)
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

app = typer.Typer(help="gethired — multi-agent CV tailoring", no_args_is_help=True)


def ensure_consent(force_prompt: bool = False) -> None:
    """Prompt for consent if no valid on-disk record exists.

    Thin wrapper around :func:`gethired.consent.require` for the CLI surface.
    Library users should call :func:`gethired.consent.current` or
    :func:`gethired.consent.require` directly.
    """
    require(force=force_prompt)


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


def _common_paste_args(
    pasted_jd: str | None,
    no_tty_prompt: bool,
) -> tuple[str | None, bool]:
    """Return ``(pasted_jd, no_tty_prompt)`` — placeholder for symmetry / future use."""
    return pasted_jd, no_tty_prompt


def _resolve_jds(
    urls: list[str] | None,
    pasted_jd: str | None,
    no_tty_prompt: bool,
) -> tuple[Job, ...]:
    """Resolve the JD tuple for a command.

    Either ``urls`` or ``pasted_jd`` must be supplied (not both). When
    ``pasted_jd`` is set, the fetcher is bypassed entirely. When
    ``urls`` triggers an :class:`AntiBotError`, the CLI either launches an
    inline paste prompt (TTY) or prints the recovery command and exits 2.
    """
    if urls and pasted_jd:
        typer.echo("error: pass either <urls> or --pasted-jd, not both", err=True)
        raise typer.Exit(code=2)
    if pasted_jd is not None:
        return (_load_pasted_jd(pasted_jd),)
    if not urls:
        typer.echo("error: at least one <url> or --pasted-jd is required", err=True)
        raise typer.Exit(code=2)
    try:
        return fetch_all_jds(urls)
    except AntiBotError as exc:
        jd = _antibot_recover(exc, no_tty_prompt=no_tty_prompt)
        if jd is None:
            raise typer.Exit(code=2) from exc
        return (jd,)


@app.command()
def plan(
    urls: list[str] | None = typer.Argument(None),
    resume: Path = typer.Option(Path("sample.tex"), "--resume", "-r"),
    model: str | None = typer.Option(None, "--model", "-m"),
    pasted_jd: str | None = typer.Option(
        None,
        "--pasted-jd",
        help="Path to a file containing the JD text (use '-' for stdin). Skips fetching.",
    ),
    no_tty_prompt: bool = typer.Option(
        False,
        "--no-tty-prompt",
        help=("Disable the inline paste prompt on anti-bot detection "
            "(exit with recovery command instead)."),
    ),
) -> None:
    """Estimate cost without running the agent."""
    configure()
    ensure_consent()
    jds = _resolve_jds(urls, pasted_jd, no_tty_prompt)
    tailor = Tailor(resume=resume, job_description=jds, model=model)
    plan_data = tailor.plan()
    typer.echo(json.dumps(plan_data, indent=2))


@app.command()
def run(
    urls: list[str] | None = typer.Argument(None),
    resume: Path = typer.Option(Path("sample.tex"), "--resume", "-r"),
    model: str | None = typer.Option(None, "--model", "-m"),
    debug: bool = typer.Option(False, "--debug", "-d"),
    out_dir: Path = typer.Option(DEFAULT_TAILORED_DIR_PATH, "--out-dir"),
    pasted_jd: str | None = typer.Option(
        None,
        "--pasted-jd",
        help="Path to a file containing the JD text (use '-' for stdin). Skips fetching.",
    ),
    no_tty_prompt: bool = typer.Option(
        False,
        "--no-tty-prompt",
        help=("Disable the inline paste prompt on anti-bot detection "
            "(exit with recovery command instead)."),
    ),
) -> None:
    """Run the full tailoring pipeline. Accepts multiple URLs."""
    configure(debug=debug)
    ensure_consent()
    jds = _resolve_jds(urls, pasted_jd, no_tty_prompt)
    tailor = Tailor(
        resume=resume, job_description=jds, model=model, debug=debug, tailored_dir=out_dir
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
    urls: list[str] | None = typer.Argument(None),
    resume: Path = typer.Option(Path("sample.tex"), "--resume", "-r"),
    model: str | None = typer.Option(None, "--model", "-m"),
    debug: bool = typer.Option(False, "--debug", "-d"),
    out_dir: Path = typer.Option(DEFAULT_TAILORED_DIR_PATH, "--out-dir"),
    pasted_jd: str | None = typer.Option(
        None,
        "--pasted-jd",
        help="Path to a file containing the JD text (use '-' for stdin). Skips fetching.",
    ),
    no_tty_prompt: bool = typer.Option(
        False,
        "--no-tty-prompt",
        help=("Disable the inline paste prompt on anti-bot detection "
            "(exit with recovery command instead)."),
    ),
) -> None:
    """Run the pipeline with cover-letter production enabled.

    With a single URL: writes ``cover_letter.md`` (backward-compatible).
    With multiple URLs: writes one ``cover_letter_<index>_<slug>.md`` per JD.
    """
    configure(debug=debug)
    ensure_consent()
    jds = _resolve_jds(urls, pasted_jd, no_tty_prompt)
    tailor = Tailor(
        resume=resume,
        job_description=jds,
        model=model,
        debug=debug,
        tailored_dir=out_dir,
        produce_cover_letter=False,
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
    written = _write_cover_letters(
        tailored=tailored,
        resume=resume,
        model=model,
        debug=debug,
        out_dir=out_dir,
    )
    typer.echo(f"Run complete: {tailored.run.id}")
    for label, path in written:
        typer.echo(f"Cover letter ({label}): {path}")


@app.command()
def preflight(
    urls: list[str] | None = typer.Argument(None),
    resume: Path = typer.Option(Path("sample.tex"), "--resume", "-r"),
    model: str | None = typer.Option(None, "--model", "-m"),
    pasted_jd: str | None = typer.Option(
        None,
        "--pasted-jd",
        help="Path to a file containing the JD text (use '-' for stdin). Skips fetching.",
    ),
    no_tty_prompt: bool = typer.Option(
        False,
        "--no-tty-prompt",
        help=("Disable the inline paste prompt on anti-bot detection "
            "(exit with recovery command instead)."),
    ),
) -> None:
    """Dry-run preflight: estimate cost and gate outcomes without invoking the LLM."""
    configure()
    ensure_consent()
    jds = _resolve_jds(urls, pasted_jd, no_tty_prompt)
    tailor = Tailor(resume=resume, job_description=jds, model=model, debug=False)
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


# ---------------------------------------------------------------------------
# Helpers — multi-URL fetching, paste fallback, anti-bot recovery
# ---------------------------------------------------------------------------


_SLUG_RE: re.Pattern[str] = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Lower-case, strip non-alphanumerics, collapse runs into single hyphens."""
    slug = _SLUG_RE.sub("-", value.lower()).strip("-")
    return slug or "job"


def fetch_all_jds(urls: list[str]) -> tuple[Job, ...]:
    """Fetch every URL, returning all parsed ``Job``s in input order.

    Raises:
        AntiBotError: If any URL is blocked by an anti-bot challenge.
        FetchError: If any URL fails to fetch for any other reason.
    """
    retriever = Fetcher(DEFAULT_DATA_DIR_PATH / "jd_cache")
    return tuple(retriever.retrieve(url) for url in urls)


def _load_pasted_jd(path: str) -> Job:
    """Build a ``Job`` from a file path (``-`` reads stdin).

    The URL is set to ``pasted://<path>`` so it round-trips through cache
    invalidation by content hash rather than by URL.
    """
    if path == "-":
        return _job_from_text(sys.stdin.read(), source="stdin")
    return _job_from_text(Path(path).read_text(), source=path)


def _job_from_text(text: str, *, source: str) -> Job:
    """Build a ``Job`` from already-read text (used by both file load and TTY paste).

    Runs the fetcher's keyword extractor over the text so must-haves and
    nice-to-haves are populated even when the JD wasn't fetched (so the
    merger has real data to consolidate).
    """
    title = next((line.strip() for line in text.splitlines() if line.strip()), source)
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    base = from_text(text, url=f"pasted://{source}", content_hash=content_hash)
    return Job(
        url=base.url,
        title=title,
        company=base.company,
        full_text=base.full_text,
        keywords=base.keywords,
        must_have_keywords=base.must_have_keywords,
        nice_to_have_keywords=base.nice_to_have_keywords,
        content_hash=base.content_hash,
    )


def _stdin_is_tty() -> bool:
    try:
        return sys.stdin.isatty()
    except ValueError:
        return False


def _inline_paste_prompt() -> str:
    """Read the JD text from stdin with an inline banner.

    Prints a banner to stderr so stdout stays usable for piping; reads stdin
    to EOF and returns the result.
    """
    typer.echo(
        "Paste the JD text below. Press Ctrl-D (Unix) or Ctrl-Z+Enter "
        "(Windows) when finished:",
        err=True,
    )
    return sys.stdin.read()


def _antibot_recover(exc: AntiBotError, *, no_tty_prompt: bool) -> Job | None:
    """Recover from an :class:`AntiBotError` by either prompting or printing recovery.

    Returns:
        A ``Job`` when the user successfully pasted a JD inline.
        ``None`` when the CLI is non-interactive (or ``--no-tty-prompt`` is set)
        and we printed the recovery command for a manual re-run.
    """
    if no_tty_prompt or not _stdin_is_tty():
        typer.echo(
            f"error: anti-bot challenge on {exc.url} (HTTP {exc.status}, markers: "
            f"{', '.join(exc.markers)})",
            err=True,
        )
        typer.echo(
            "Re-run with the JD text piped via stdin or a file, e.g.:",
            err=True,
        )
        typer.echo("  gethired run --pasted-jd -            < jd.txt", err=True)
        typer.echo("  gethired run --pasted-jd jd.txt", err=True)
        return None
    text = _inline_paste_prompt()
    if not text.strip():
        typer.echo("error: empty paste; aborting", err=True)
        return None
    return _job_from_text(text, source="stdin")


def _write_cover_letters(
    *,
    tailored,
    resume: Path,
    model: str | None,
    debug: bool,
    out_dir: Path,
) -> list[tuple[str, Path]]:
    """Write cover letter(s) for a tailored run.

    - N=1 → single ``cover_letter.md`` (backward-compatible).
    - N≥2 → one ``cover_letter_<index>_<slug>.md`` per JD, with role /
      seniority / company / responsibilities per-JD and the merged
      must-have / nice-to-have / keyword set.
    """
    run_dir = out_dir / tailored.run.id
    run_dir.mkdir(parents=True, exist_ok=True)
    jds = _jobs_for_tailored(tailored)
    analysis = _merged_analysis_for_tailored(tailored)
    voice = build_profile(_master_for_tailored(tailored))
    written: list[tuple[str, Path]] = []
    if len(jds) <= 1:
        cover_result = compose_cover_letter(
            master=_master_for_tailored(tailored), analysis=analysis, voice=voice
        )
        path = run_dir / "cover_letter.md"
        path.write_text(render_cover_markdown(cover_result.letter))
        written.append(("merged", path))
        return written
    width = max(2, len(str(len(jds))))
    for idx, jd in enumerate(jds, start=1):
        per_jd = overlay_for_jd(analysis, jd)
        cover_result = compose_cover_letter(
            master=_master_for_tailored(tailored), analysis=per_jd, voice=voice
        )
        slug_source = jd.company or jd.title or jd.url
        slug = slugify(slug_source)[:40]
        path = run_dir / f"cover_letter_{idx:0{width}d}_{slug}.md"
        path.write_text(render_cover_markdown(cover_result.letter))
        written.append((f"jd{idx}", path))
    return written


def _master_for_tailored(tailored):
    """Return the ``Master`` attached to a ``Tailored`` by the orchestrator."""
    master_obj = tailored.master
    if master_obj is None:
        raise RuntimeError("Tailored.master not populated; cannot produce cover letter")
    return master_obj


def _jobs_for_tailored(tailored) -> tuple[Job, ...]:
    """Return the JD tuple attached to a ``Tailored`` by the orchestrator."""
    return tailored.jds  # type: ignore[no-any-return]


def _merged_analysis_for_tailored(tailored):
    """Return the merged analysis attached to a ``Tailored`` by the orchestrator."""
    analysis = tailored.analysis
    if analysis is None:
        raise RuntimeError("Tailored.analysis not populated; cannot produce cover letter")
    return analysis


if __name__ == "__main__":
    app()
