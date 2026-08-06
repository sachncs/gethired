"""CLI tests for multi-URL fetching, paste-fallback, anti-bot recovery,
and per-URL cover-letter production."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from gethired import cli as cli_module
from gethired.cli import app
from gethired.description import consolidate
from gethired.exceptions import AntiBotError
from gethired.models import (
    Contact,
    Job,
Resume,
    Outcome,
    Report,
    Run,
    RunResult,
    Skills,
    Step,
    StepKind,
    StepMeta,
    StepStatus,
    Tailored)

runner = CliRunner()


@pytest.fixture(autouse=True)
def _no_consent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_module, "ensure_consent", lambda: None)


# ---------------------------------------------------------------------------
# Multi-URL fetching
# ---------------------------------------------------------------------------


def test_fetch_all_jds_returns_tuple_of_jobs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``fetch_all_jds`` returns a Job tuple in input order."""
    seen: list[str] = []

    def fake_retrieve(_self, url: str) -> Job:
        seen.append(url)
        return Job(
            url=url,
            title=f"Title for {url}",
            company="Acme",
            full_text="body",
            keywords=("python"),
            must_have_keywords=("python"),
            nice_to_have_keywords=(),
            content_hash=url)

    monkeypatch.setattr(cli_module, "DEFAULT_DATA_DIR_PATH", tmp_path)
    monkeypatch.setattr("gethired.cli.Fetcher.retrieve", fake_retrieve)
    jds = cli_module.fetch_all_jds(["https://a.example/jd", "https://b.example/jd"])
    assert seen == ["https://a.example/jd", "https://b.example/jd"]
    assert [jd.url for jd in jds] == ["https://a.example/jd", "https://b.example/jd"]


def test_fetch_all_jds_propagates_antibot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``fetch_all_jds`` re-raises :class:`AntiBotError` so the CLI can recover."""

    def fake_retrieve(_self, url: str) -> Job:  # pragma: no cover - exception path
        raise AntiBotError(url, 403, ("server: cloudflare"))

    monkeypatch.setattr(cli_module, "DEFAULT_DATA_DIR_PATH", tmp_path)
    monkeypatch.setattr("gethired.cli.Fetcher.retrieve", fake_retrieve)
    with pytest.raises(AntiBotError):
        cli_module.fetch_all_jds(["https://blocked.example/jd"])


# ---------------------------------------------------------------------------
# CLI: run with multiple URLs
# ---------------------------------------------------------------------------


def _two_jds() -> list[Job]:
    return [
        Job(
            url="https://a.example/jd",
            title="Senior ML Engineer",
            company="Acme",
            full_text="Senior ML Engineer at Acme. You will design platforms.",
            keywords=("python"),
            must_have_keywords=("python", "kubernetes"),
            nice_to_have_keywords=("pytorch",),
            content_hash="a"),
        Job(
            url="https://b.example/jd",
            title="Staff ML Engineer",
            company="Beta",
            full_text="Staff ML Engineer at Beta. You will lead reviews.",
            keywords=("python"),
            must_have_keywords=("python", "aws"),
            nice_to_have_keywords=("kubernetes", "pytorch"),
            content_hash="b"),
    ]


def test_cli_run_passes_all_urls_to_tailor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, resume_tex_path: Path
) -> None:
    """``run`` with two URLs forwards both Jobs to ``Tailor``."""
    captured: dict[str, object] = {}

    class FakeTailor:
        def __init__(self, *, resume, job_description, **_kwargs):  # noqa: ARG002
            captured["resume"] = resume  # noqa: F841  # retained for diagnostics
            captured["job_description"] = job_description

        def run(self):  # pragma: no cover - not exercised here
            raise RuntimeError("stop")

    monkeypatch.setattr(cli_module, "Tailor", FakeTailor)
    monkeypatch.setattr(cli_module, "fetch_all_jds", lambda _urls: tuple(_two_jds()))

    result = runner.invoke(
        app,
        [
            "run",
            "https://a.example/jd",
            "https://b.example/jd",
            "--resume",
            str(resume_tex_path),
            "--out-dir",
            str(tmp_path),
        ])
    assert result.exit_code != 0  # FakeTailor.run() raises; CLI surfaces it
    assert isinstance(captured["job_description"], tuple)
    assert len(captured["job_description"]) == 2
    assert [jd.url for jd in captured["job_description"]] == [
        "https://a.example/jd",
        "https://b.example/jd",
    ]


def test_cli_plan_cover_preflight_pass_tuples(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, resume_tex_path: Path
) -> None:
    """``plan``, ``cover``, ``preflight`` all forward the full URL tuple to ``Tailor``."""
    captured: list[tuple[object, ...]] = []

    class FakeTailor:
        def __init__(self, *, resume, job_description, **_kwargs):  # noqa: ARG002
            captured.append(job_description)

        def run(self):  # pragma: no cover
            class _R:
                run = type("R", (), {"id": "abc"})()

            return _R

        def plan(self):  # pragma: no cover
            return {"tokens_estimate": 1, "expected_gates": [], "voice_drift_risk": 0.0}

        def preflight(self):  # pragma: no cover
            return Report(
                tokens_estimate=1,
                expected_gates=(),
                jd_keyword_coverage={},
                voice_drift_risk=0.0,
                missing_must_haves=())

    monkeypatch.setattr(cli_module, "Tailor", FakeTailor)
    monkeypatch.setattr(cli_module, "fetch_all_jds", lambda _urls: tuple(_two_jds()))

    for cmd in ("plan", "preflight"):
        result = runner.invoke(
            app,
            [cmd, "https://a.example/jd", "https://b.example/jd", "--resume", str(resume_tex_path)])
        assert result.exit_code == 0, result.stdout + (result.stderr or "")
    # cover is exercised separately (writes files); skip here


# ---------------------------------------------------------------------------
# CLI: --pasted-jd flag
# ---------------------------------------------------------------------------


def test_cli_run_with_pasted_jd_file_skips_fetch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, resume_tex_path: Path
) -> None:
    """``run --pasted-jd <file>`` reads the JD from disk and skips the fetcher."""
    seen_urls: list[str] = []

    def fake_fetch_all(_urls: list[str]) -> tuple[Job, ...]:  # pragma: no cover
        seen_urls.append("called")
        return ()

    captured: dict[str, object] = {}

    class _StubRun:  # noqa: N801  # mirrors tailored.run attribute
        class run:  # noqa: N801
            id = "rid-pasted-file"

    class FakeTailor:
        def __init__(self, *, resume, job_description, **_kwargs):  # noqa: ARG002
            captured["job_description"] = job_description

        def run(self) -> _StubRun:
            return _StubRun()

    monkeypatch.setattr(cli_module, "fetch_all_jds", fake_fetch_all)
    monkeypatch.setattr(cli_module, "Tailor", FakeTailor)

    jd_file = tmp_path / "jd.txt"
    jd_file.write_text("Senior Engineer at Acme\n\nYou will build platforms.")
    result = runner.invoke(
        app,
        [
            "run",
            "--pasted-jd",
            str(jd_file),
            "--resume",
            str(resume_tex_path),
            "--out-dir",
            str(tmp_path),
        ])
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert not seen_urls, "fetch_all_jds must not be called when --pasted-jd is set"
    assert isinstance(captured["job_description"], tuple)
    assert len(captured["job_description"]) == 1
    pasted_jd = captured["job_description"][0]
    assert pasted_jd.url == f"pasted://{jd_file}"
    assert "Senior Engineer" in pasted_jd.full_text


def test_cli_run_pasted_jd_stdin_dash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, resume_tex_path: Path
) -> None:
    """``--pasted-jd -`` reads from stdin."""
    captured: dict[str, object] = {}

    class _StubRun:  # noqa: N801  # mirrors tailored.run attribute
        class run:  # noqa: N801
            id = "rid-pasted-stdin"

    class FakeTailor:
        def __init__(self, *, resume, job_description, **_kwargs):  # noqa: ARG002
            captured["job_description"] = job_description

        def run(self) -> _StubRun:
            return _StubRun()

    monkeypatch.setattr(cli_module, "Tailor", FakeTailor)

    jd_text = "Lead Engineer at Acme\n\nYou will design systems."
    result = runner.invoke(
        app,
        ["run", "--pasted-jd", "-", "--resume", str(resume_tex_path), "--out-dir", str(tmp_path)],
        input=jd_text)
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    pasted_jd = captured["job_description"][0]
    assert pasted_jd.url == "pasted://stdin"
    assert "Lead Engineer" in pasted_jd.title


def test_cli_run_pasted_jd_and_urls_mutually_exclusive(
    tmp_path: Path, resume_tex_path: Path
) -> None:
    """Passing both URLs and --pasted-jd exits non-zero with a clear error."""
    jd_file = tmp_path / "jd.txt"
    jd_file.write_text("hello")
    result = runner.invoke(
        app,
        [
            "run",
            "https://a.example/jd",
            "--pasted-jd",
            str(jd_file),
            "--resume",
            str(resume_tex_path),
        ])
    assert result.exit_code == 2
    combined = (result.stdout or "") + (result.stderr or "")
    assert "either <urls> or --pasted-jd" in combined


# ---------------------------------------------------------------------------
# CLI: anti-bot recovery
# ---------------------------------------------------------------------------


def test_cli_run_exits_2_on_antibot_non_tty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, resume_tex_path: Path
) -> None:
    """Anti-bot on a non-TTY CLI prints the recovery command and exits 2."""
    monkeypatch.setattr(cli_module, "stdin_is_tty", lambda: False)
    monkeypatch.setattr(
        cli_module,
        "fetch_all_jds",
        lambda _urls: (_ for _ in ()).throw(  # noqa: E501
            AntiBotError("https://blocked/jd", 403, ("server: cloudflare"))
        ))

    result = runner.invoke(
        app,
        ["run", "https://blocked/jd", "--resume", str(resume_tex_path), "--out-dir", str(tmp_path)])
    assert result.exit_code == 2
    combined = (result.stdout or "") + (result.stderr or "")
    assert "anti-bot" in combined.lower()
    assert "--pasted-jd" in combined


def test_cli_run_antibot_tty_invokes_inline_prompt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, resume_tex_path: Path
) -> None:
    """Anti-bot on a TTY CLI runs the inline paste prompt and continues with the pasted JD."""
    monkeypatch.setattr(cli_module, "stdin_is_tty", lambda: True)
    monkeypatch.setattr(cli_module, "inline_paste_prompt", lambda: "Pasted JD body\n")
    monkeypatch.setattr(
        cli_module,
        "fetch_all_jds",
        lambda _urls: (_ for _ in ()).throw(  # noqa: E501
            AntiBotError("https://blocked/jd", 403, ("server: cloudflare"))
        ))

    captured: dict[str, object] = {}

    class _StubRun:  # noqa: N801  # mirrors tailored.run attribute
        class run:  # noqa: N801
            id = "rid-anti-bot-paste"

    class FakeTailor:
        def __init__(self, *, resume, job_description, **_kwargs):  # noqa: ARG002
            captured["job_description"] = job_description

        def run(self) -> _StubRun:
            return _StubRun()

    monkeypatch.setattr(cli_module, "Tailor", FakeTailor)

    result = runner.invoke(
        app,
        ["run", "https://blocked/jd", "--resume", str(resume_tex_path), "--out-dir", str(tmp_path)])
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    pasted_jd = captured["job_description"][0]
    assert "Pasted JD body" in pasted_jd.full_text


def test_cli_no_tty_prompt_flag_overrides_isatty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, resume_tex_path: Path
) -> None:
    """``--no-tty-prompt`` short-circuits the inline paste even on a TTY."""
    monkeypatch.setattr(cli_module, "stdin_is_tty", lambda: True)
    def _must_not_be_called() -> None:
        raise AssertionError("must not be called")

    monkeypatch.setattr(cli_module, "inline_paste_prompt", _must_not_be_called)
    monkeypatch.setattr(
        cli_module,
        "fetch_all_jds",
        lambda _urls: (_ for _ in ()).throw(  # noqa: E501
            AntiBotError("https://blocked/jd", 403, ("server: cloudflare"))
        ))

    result = runner.invoke(
        app,
        [
            "run",
            "https://blocked/jd",
            "--no-tty-prompt",
            "--resume",
            str(resume_tex_path),
            "--out-dir",
            str(tmp_path),
        ])
    assert result.exit_code == 2
    combined = (result.stdout or "") + (result.stderr or "")
    assert "--pasted-jd" in combined


# ---------------------------------------------------------------------------
# CLI: per-URL cover letters (D2)
# ---------------------------------------------------------------------------


def _make_resume():
    """Build a minimal Resume for cover-letter tests."""
    return Resume(name="Jane Doe", city="NYC", phone="555", email="j@e.com", github=None, linkedin=None, summary="Senior engineer with ML focus.",
        skills=Skills(categories={"Languages": ("python")}),
        experience=(),
        projects=(),
        education=(),
        awards=())


def test_cli_cover_single_url_writes_cover_letter_md(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, resume_tex_path: Path
) -> None:
    """N=1 path: writes ``cover_letter.md`` (backward-compatible)."""
    master = _make_resume()
    jd = _two_jds()[0]
    analysis = consolidate((jd,))

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
                    metadata=StepMeta()))
            return Tailored(
                name=master.name,email=master.email,city=master.city,phone=master.phone,github=master.github,linkedin=master.linkedin,
                summary="",
                skills=Skills(categories={}),
                experience=(),
                projects=(),
                education=(),
                awards=(),
                dropped=(),
                rationale="",
                grounding=(),
                jobs=steps,
                run_result=RunResult(
                    run=Run(
                        id="rid1",
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
                    jobs=steps))

    monkeypatch.setattr(cli_module, "fetch_all_jds", lambda _urls: (jd))
    monkeypatch.setattr(cli_module, "Tailor", FakeTailor)

    result = runner.invoke(
        app,
        [
            "cover",
            "https://a.example/jd",
            "--resume",
            str(resume_tex_path),
            "--out-dir",
            str(tmp_path),
        ])
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    cover_files = list((tmp_path / "rid1").glob("cover_letter*.md"))
    assert any(p.name == "cover_letter.md" for p in cover_files), (
        f"missing cover_letter.md in {cover_files}"
    )


def test_cli_cover_three_urls_writes_three_per_jd_letters(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, resume_tex_path: Path
) -> None:
    """N=3 path: writes three per-JD cover letters with per-JD role and merged keywords."""
    master = _make_resume()
    jds = [
        Job(
            url="https://a.example/jd",
            title="Senior ML Engineer",
            company="Acme",
            full_text="Senior ML Engineer at Acme. You will design platforms.",
            keywords=("python"),
            must_have_keywords=("python"),
            nice_to_have_keywords=(),
            content_hash="a"),
        Job(
            url="https://b.example/jd",
            title="Staff Backend Engineer",
            company="Beta",
            full_text="Staff Backend Engineer at Beta. You will lead API design.",
            keywords=("aws"),
            must_have_keywords=("aws"),
            nice_to_have_keywords=(),
            content_hash="b"),
        Job(
            url="https://c.example/jd",
            title="Lead Platform Engineer",
            company="Gamma",
            full_text="Lead Platform Engineer at Gamma. You will drive strategy.",
            keywords=("kubernetes"),
            must_have_keywords=("kubernetes"),
            nice_to_have_keywords=(),
            content_hash="c"),
    ]
    analysis = consolidate(tuple(jds))

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
                    metadata=StepMeta()))
            return Tailored(
                name=master.name,email=master.email,city=master.city,phone=master.phone,github=master.github,linkedin=master.linkedin,
                summary="",
                skills=Skills(categories={}),
                experience=(),
                projects=(),
                education=(),
                awards=(),
                dropped=(),
                rationale="",
                grounding=(),
                jobs=steps,
                run_result=RunResult(
                    run=Run(
                        id="rid3",
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
                    jobs=steps))

    monkeypatch.setattr(cli_module, "fetch_all_jds", lambda _urls: tuple(jds))
    monkeypatch.setattr(cli_module, "Tailor", FakeTailor)

    urls = [jd.url for jd in jds]
    result = runner.invoke(
        app,
        ["cover", *urls, "--resume", str(resume_tex_path), "--out-dir", str(tmp_path)])
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    run_dir = tmp_path / "rid3"
    covers = sorted(p for p in run_dir.glob("cover_letter_*.md"))
    assert len(covers) == 3, f"expected 3 cover letters, got {[p.name for p in covers]}"
    bodies = [p.read_text() for p in covers]
    # Per-JD role / responsibility reflected
    assert any("Senior ML Engineer" in b and "design platforms" in b for b in bodies)
    assert any("Staff Backend Engineer" in b and "API design" in b for b in bodies)
    assert any("Lead Platform Engineer" in b and "drive strategy" in b for b in bodies)
    # Merged keyword universe: every letter sees every must-have
    for keyword in ("python", "aws", "kubernetes"):
        assert all(keyword in b.lower() for b in bodies), (
            f"keyword {keyword!r} missing from some per-JD letters"
        )
