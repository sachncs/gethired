<div align="center">

# gethired

**Production-grade multi-agent CV tailoring system grounded in a master resume and verified against ATS gates.**

[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/sachncs/gethired/ci.yml?branch=master)](https://github.com/sachncs/gethired/actions)
[![Stars](https://img.shields.io/github/stars/sachncs/gethired)](https://github.com/sachncs/gethired/stargazers)

</div>

gethired is a layered, multi-agent pipeline that rewrites a candidate's
master resume against one or more job descriptions while staying
strictly grounded in the master, blocking fabrication, and verifying
the result against 12 ATS-compliance gates (9 hard-blocking, 3
advisory). Every collaborator (parser, fetcher, description, writer,
critic, profiler, validator, renderer) is replaceable through small,
well-typed interfaces; the default wiring uses Anthropic-compatible
APIs.

The framework is fully typed (PEP 484 + PEP 695 modern syntax), fully
documented (Google-style docstrings on every public function), and
ships with a loguru-backed central logger plus structured per-step
trace events. Production defaults: every rewrite is grounded against
the master via `GroundedCitation`; every batch is traced via
`Job.id = uuid4()`; every output passes through grounding, style,
plagiarism, and the 12 ATS gates before render.

| Concern | Library |
|---|---|
| Agent framework | [Pydantic AI](https://github.com/pydantic/pydantic-ai) |
| Data validation | [Pydantic 2](https://github.com/pydantic/pydantic) |
| HTTP | [httpx](https://github.com/encode/httpx) (sync client) |
| Web extraction | [trafilatura](https://github.com/adbar/trafilatura) + JSON-LD |
| PDF extraction | [PyMuPDF](https://github.com/pymupdf/pymupdf) |
| Templates | [Jinja2](https://github.com/pallets/jinja) |
| CLI | [Typer](https://github.com/tiangolo/typer) + [Rich](https://github.com/Textualize/rich) |
| Logging | [loguru](https://github.com/Delgan/loguru) |
| Retries | [tenacity](https://github.com/jd/tenacity) |
| Config | [python-dotenv](https://github.com/theskumar/python-dotenv) |
| Tests | [pytest](https://github.com/pytest-dev/pytest), [respx](https://github.com/ndy2/respx), [hypothesis](https://github.com/HypothesisWorks/hypothesis) |

## Features

- **No fabrication** — every rewrite carries a `GroundedCitation` (tailored path, master path, verbatim span, sha256 of master). The grounding validator refuses output where any cited span is not present in the master.
- **Multi-agent architecture** — parser, fetcher, description, writer, critic, profiler, validator, renderer. Each is a small class with one responsibility and a typed dependency contract.
- **ATS contract** — 12 tri-state gates (pass / fail / skip) run after every run: 9 hard-blocking (PDF compiles, PDF text extractable, PDF text matches `.txt`, standard section headings, no layout tables, no images, no colours, 10–12 pt font, length within page limit) and 3 advisory (keyword coverage, bullet quantification, action verbs). A failed hard gate blocks the run; advisory failures and skipped PDF gates (when `LATEX_ENGINE=none`) never block.
- **Anti-AI language** — banned-word list with verb-stem matching, parallelism detector, voice-profile drift check, punctuation-density normalisation.
- **Anti-plagiarism** — 5-gram overlap detector against the JD corpus, minus a curated `TECHNICAL_NGRAMS_ALLOWLIST` so common jargon does not false-positive.
- **Voice preservation** — per-master fingerprint (avg bullet length, std-dev, opening verbs, punctuation density, sentence count) injected into the writer prompt so rewrites stay in the candidate's voice.
- **Traceability** — every pipeline step emits a `Job` value object (`Job.id = uuid4()`). The full job trail appears in `match_report.md` for every run; structured spans land in `tailored/<run-id>/trace.jsonl`.
- **Multi-format input** — master resumes accepted as `text`, `pdf`, `image` (vision-capable model), or `tex`. Output is always TeX.
- **Model-agnostic** — Anthropic native, OpenAI native, and the **MiniMax platform** (Anthropic-API-compatible) all work out of the box. `MODEL=MiniMax-M3` auto-routes.
- **Single CLI surface** — `gethired <verb>`: `ingest`, `fetch`, `show`, `plan`, `run`, `cover`, `preflight`, `validate`, `trace`, `audit`, `diff`. Each command is single-purpose and scriptable.
- **PII consent** — first run prompts for consent (`y/N`); recorded in `~/.config/gethired/consent.json`; re-prompted every 90 days.
- **PDF compilation** — compiles the TeX into a PDF via `tectonic` (default) or `pdflatex` (fallback). Set `LATEX_ENGINE=none` to skip.
- **Multi-JD consolidated run** — `Tailor(job_description=(jd_a, jd_b))` merges analyses via an LLM-driven merger (`gethired.merger.safe_merge`) with a programmatic fallback to `description.consolidate`. Must-haves are unioned, nice-to-haves intersected, and the LLM reasons about seniority, role specificity, and responsibility overlap rather than naive set union. Even a single-URL run goes through the merger for consistency.
- **Multi-URL CLI** — `gethired run <url1> <url2> <url3>` fetches every URL, runs the LLM merger, and tailors once against the consolidated analysis.
- **Per-URL cover letters** — `gethired cover <url1> <url2> <url3>` writes one `cover_letter_<index>_<slug>.md` per JD, each with its own role/seniority/company/responsibilities but the merged keyword universe. Single-URL `cover` writes `cover_letter.md` (backward-compatible).
- **Anti-bot recovery** — when a fetch is blocked by Cloudflare / AWS WAF (HTTP 403 + WAF marker headers), the CLI prints a recovery command; if stdin is a TTY, an inline paste prompt ingests the JD text and the run continues.
- **Paste-fallback flag** — `--pasted-jd <file>` or `--pasted-jd -` (stdin) skips the fetcher entirely for jobs behind anti-bot walls.
- **`tailor audit <run-dir>`** — re-runs all four validators against a previous run; emits `audit.json` + `audit.md` with hard / advisory / skipped breakdowns.
- **Cover-letter tailoring** — `Tailor(..., produce_cover_letter=True)` writes `cover_letter.md`.
- **Streaming intermediate output** — `Writer.tailor(..., on_progress=...)` emits `ProgressEvent`s as the pipeline runs.
- **`preflight` dry-run** — `gethired preflight <urls>` prints cost estimate + gate prediction without an LLM call; union of must-haves across URLs is reflected in `missing_must_haves`.

## Installation

### From source

```bash
git clone https://github.com/sachncs/gethired.git
cd gethired
uv sync
```

### From PyPI (planned)

```bash
pip install gethired
```

Runtime deps: `pydantic-ai`, `pydantic`, `httpx`, `trafilatura`, `readability-lxml`, `pymupdf`, `jinja2`, `typer`, `rich`, `loguru`, `python-dotenv`, `tenacity`, `pyyaml`.
Dev deps add `pytest`, `pytest-asyncio`, `pytest-cov`, `mypy`, `ruff`, `types-requests`, `respx`, `hypothesis`.

## Quick Start

### Python API (orchestrator)

```python
from gethired import Tailor, Master, Job

tailor = Tailor(
    resume="sample.tex",
    job_description="https://example.com/jd",
    debug=True,
    model="MiniMax-M3",
)
result = tailor.run()      # Tailored
print(result.summary)      # rewritten, JD-targeted
```

Always requires an LLM. Set `MODEL` (e.g. `MiniMax-M3`) and `API_KEY` (or `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`) — otherwise `Tailor(...)` raises `ConfigError` immediately. Tests inject a `TestModel` via `Tailor(..., model_instance=TestModel())`.

### Library API (plug-and-play, no orchestrator required)

You don't need `Tailor` if you only need one piece of the pipeline. Every agent is independently importable:

```python
# Parse a master resume from any supported format
from gethired import parse
master = parse("sample.tex")             # or parse_text, parse_pdf, parse_image

# Fetch a job description URL (with content-hash cache + retry)
from gethired import fetch
job = fetch("https://example.com/jd")     # returns a Job (the JD)

# Profile the candidate's voice from a master
from gethired.profiler import build
voice = build(master)

# Run a single validator against a tailored resume
from gethired.validator import grounding, style, plagiarism, ats
violations = grounding(tailored, master)
report = ats(tailored, tex_source, pdf_path, txt_source, (job,))

# Render a Tailored resume to TeX or plain text
from gethired.renderer import tex, text
tex_source = tex(tailored)
txt_source = text(tailored)
```

All imports are lazy — `import gethired` does not require `pymupdf`,
`trafilatura`, or `pydantic_ai` to be installed. The heavy dependencies
are only imported when you access a public symbol that needs them.

### Tracing

Every `Tailor.run()` emits OpenTelemetry-compatible spans to `tailored/<run-id>/trace.jsonl`. The deepeval-style graders in `evals/graders/code.py` consume this trace to score component-level behaviour (tool selection, argument correctness), reasoning-layer behaviour (plan quality, plan adherence), and overall-execution outcomes (task completion, step efficiency). Set `GETHIRED_TRACE_PATH=off` to disable.

### CLI

```bash
# Set up once
uv sync
cp .env.example .env
# Edit .env: set API_KEY=<your-key>, MODEL=MiniMax-M3, BASE_URL=https://api.minimax.io/anthropic

# Parse master, fetch JD, run full pipeline
gethired ingest sample.tex
gethired run https://example.com/jd
gethired show master
gethired trace <run-id>
```

Multi-URL runs consolidate requirements across every JD via an LLM merger:

```bash
gethired run https://example.com/jd-a https://example.com/jd-b
gethired cover https://example.com/jd-a https://example.com/jd-b   # one letter per JD
```

Anti-bot / paste-fallback (when a JD is blocked by Cloudflare or AWS WAF):

```bash
gethired run --pasted-jd jd.txt                # read JD from file
gethired run --pasted-jd - < jd.txt            # read JD from stdin
gethired run --no-tty-prompt <blocked-url>     # never auto-prompt; print recovery only
```

Every `gethired run` writes a `tailored/<run-id>/` directory containing `tailored.tex`, `tailored.txt`, `tailored.json`, and `match_report.md`. `gethired cover` adds `cover_letter.md` (single URL) or `cover_letter_<index>_<slug>.md` per JD (multi-URL).

### Programmatic Tailor entry

```python
from gethired import parse, fetch, Tailor

master = parse("sample.tex")
job = fetch("https://example.com/jd")

tailor = Tailor(
    resume=master,            # Master or path to .tex
    job_description=job,      # Job or URL string
    debug=True,               # verbose loguru output
)
result = tailor.run()
```

The CLI uses the same `Tailor` class under the hood; the public surface is identical.

## Configuration

Settings live in `.env` (gitignored). The CLI loads them at startup.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_KEY` | yes (for LLM) | unset | Auth token. Falls back to `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` |
| `BASE_URL` | no | auto | API base URL. Auto-set for MiniMax models; otherwise passthrough |
| `MODEL` | no | unset | Model identifier (e.g. `MiniMax-M3`, `anthropic:claude-sonnet-4-5`, `openai:gpt-5`) |
| `OPENAI_API_KEY` | no | unset | Required only if `MODEL` starts with `openai:` |
| `ANTHROPIC_BASE_URL` | no | unset | Override base URL when `MODEL` starts with `anthropic:` |
| `IMAGE_MODEL` | no | unset | Vision model for `parse_image` |
| `LATEX_ENGINE` | no | `tectonic` | One of `tectonic`, `pdflatex`, `none` |
| `GETHIRED_CACHE_DIR` | no | system default | Override the JD cache directory |
| `GETHIRED_TRACE_PATH` | no | `tailored/<run-id>/trace.jsonl` | Set to `off` to disable tracing |

Precedence: constructor arguments → `.env` → built-in defaults. Without `MODEL` and without an injected `model_instance`, `Tailor(...)` raises `ConfigurationError` immediately.

## Commands

| Command | Purpose |
|---|---|
| `gethired ingest <tex>` | parse master resume into `data/master.json` |
| `gethired fetch <urls>` | fetch + cache JDs (sync httpx, content-hash invalidation); multiple URLs supported |
| `gethired run <urls>` | full pipeline: parser → fetcher → description → profiler → writer → critic → renderer; multiple URLs consolidated via the LLM merger |
| `gethired cover <urls>` | full pipeline + cover-letter production (`cover_letter.md` for N=1, one `cover_letter_<index>_<slug>.md` per JD for N≥2) |
| `gethired preflight <urls>` | dry-run: cost + gate prediction, no LLM call |
| `gethired plan <urls>` | cost estimate only (no LLM call) |
| `gethired show master` | print `data/master.json` |
| `gethired show jd --url URL` | print a cached JD |
| `gethired validate <path>` | run ATS gates against a `tailored.json` |
| `gethired trace <run-id>` | pretty-print Job trail from a previous run |
| `gethired audit <run-dir>` | re-run all 4 validators against a previous run; emit `audit.json` + `audit.md` |
| `gethired diff <a> <b>` | diff two tailored runs (markdown) |

Flags available on `run`, `cover`, `plan`, and `preflight`:

- `--pasted-jd <path>` (or `-` for stdin) — bypass the fetcher and use a JD pasted from disk / stdin.
- `--no-tty-prompt` — never auto-launch the paste prompt on anti-bot detection; print the recovery command instead.

## Traceability

Every pipeline step emits a `Job` value object (`Job.id = uuid4()`) with `type`, `started_at`, `completed_at`, `status`, `inputs`, `outputs`, `rationale`, `model`, `tool_name`, and typed `metadata`. `Job.description()` returns a serialisable `JobData` for the audit trail.

Every rewritten bullet carries a `GroundedCitation` (tailored path + master path + verbatim span + `job_id`). The grounding validator refuses the output if any cited span is not actually in `master.json`. Run output:

```
tailored/<run-id>/
├── tailored.tex       # ATS-compliant LaTeX source
├── tailored.txt       # plain-text ATS version
├── tailored.json      # full Tailored with traceability
├── tailored.pdf       # compiled (when LATEX_ENGINE != none)
└── match_report.md    # Run Description · Job Trail · ATS Gates · Keyword Coverage
```

## Multi-Agent Architecture

| Agent | File | Responsibility |
|---|---|---|
| Parser | `parser.py`, `parse.py`, `plain_text.py` | text / pdf / image / tex → `Master` |
| Fetcher | `fetcher.py`, `fetch.py` | URL → `Job` (sync httpx, content-hash cache, exponential backoff) |
| Description | `description.py` | structured JD analysis (role, seniority, must-have skills) |
| Profiler | `profiler.py` | per-master voice fingerprint |
| Writer | `writer.py` | main tailoring (Pydantic AI + 7 read-only tools) |
| Critic | `critic.py` | validation pipeline (grounding / style / plagiarism / ATS) |
| Validator | `validator.py` | deterministic checks (the 12 ATS gates) |
| Renderer | `renderer.py`, `render_pdf.py` | `Tailored` → tex / txt / pdf / match_report |
| Tailor | `tailor.py` | orchestrator: parse → fetch → describe → profile → write → critique → render |

The `Tailor` class is the only collaborator that holds all the others. Every step emits a `Job`; render is gated on the ATS report (a failed hard gate blocks the run, advisory and skipped gates do not).

## Project Structure

```
gethired/
├── parser         # text/pdf/image/tex → Master
├── parse          # public parse() facade
├── plain_text     # parse_text() production path
├── fetcher        # URL → Job (sync httpx + cache + retry)
├── fetch          # public fetch() facade
├── description    # JD analysis
├── profiler       # voice fingerprint
├── writer         # main tailoring agent (Pydantic AI)
├── critic         # validator pipeline
├── validator      # the 12 deterministic ATS gates
├── renderer       # Tailored → tex / txt / match_report
├── render_pdf     # tectonic / pdflatex wrapper
├── cover_letter   # cover-letter production
├── streaming      # ProgressEvent emission
├── tailor         # Tailor orchestrator (the only public entry)
├── provider       # model resolution (Anthropic / OpenAI / MiniMax)
├── serialize      # JSON ↔ Master / Tailored coercion
├── models         # frozen dataclasses (Run / Job / Step / Master / Tailored / ...)
├── normalize      # canonical numeric / latex-strip / tokenize
├── consent        # PII-consent record management
├── observability  # loguru central logging
├── tracing        # OpenTelemetry-compatible JSONL span emitter
├── exceptions     # *Error hierarchy
├── constants      # UPPER_CASE module constants
└── cli            # typer CLI surface
```

## Development

```bash
uv sync
```

Linting and type-checking:

```bash
ruff check gethired/ tests/
mypy gethired/
```

## Testing

```bash
uv run --with pytest --with pytest-asyncio pytest tests/ -q
uv run --with pytest --with pytest-asyncio pytest tests/ --cov=gethired --cov-report=term-missing
```

The suite covers: parser (against the real `sample.tex`), plain-text `parse_text` production path, normalisation (canonical numeric / latex-strip / tokenize), voice profiler, rubric, provider resolution (Anthropic / OpenAI / MiniMax), writer (LLM path with `TestModel`), all four validators (grounding, style, plagiarism, ATS with hard/advisory tiers and tri-state PDF gates), end-to-end pipeline runs, multi-JD consolidated runs, audit, cover letter, streaming, preflight, PDF compile, fetcher retries, drop application, and property-based checks via `hypothesis`. Current count: **303 tests** (~265 unit / integration + 9 property-based + 10 CLI end-to-end + ~19 adversarial / corpus).

## Smoke test against real LLM

```bash
uv run python tests/smoke_e2e.py
```

Runs the full pipeline with the configured model on a synthetic JD; emits `tailored/<run-id>/{tailored.tex, tailored.txt, tailored.json, match_report.md}`.

## Roadmap

- **v0.1.0** — Scaffold + parser + models + normalised text utilities. 40 tests.
- **v0.2.0** — Multi-agent pipeline (parser, fetcher, description, writer, critic, tailor, renderer). CLI. Validator (grounding, style, plagiarism, 11 ATS gates). 67 tests.
- **v0.3.0** — MiniMax provider integration. `Tailor(resume=…, job_description=…, debug=True)` programmatic API. LLM-backed writer via Pydantic AI. 81 tests.
- **v0.4.0** — PDF compile via `tectonic` (pdflatex fallback), multi-JD consolidated run, `tailor audit <run-dir>`, cover-letter tailoring, streaming intermediate output, `--dry-run` preflight visualisation. 129 tests.
- **v0.5.0** — OpenTelemetry-compatible tracing (`gethired/tracing.py`, JSONL span emission). Six deepeval-style agent-evaluation graders (component / reasoning / overall-execution layers). `parse_image` wired to a vision-capable model. `job()` factory split into focused builders. **Zero `# noqa:` / `# type: ignore` suppressions** across the codebase. 150 tests.
- **v0.6.0** — Production-ready plain-text `parse_text`, 12 tri-state ATS gates split into 9 hard-blocking + 3 advisory, compile-based PDF page counting, PDF-gate `skip` when `LATEX_ENGINE=none`, missing contact fields fail fast with `MasterParsingError`, critic re-validates the compiled PDF exactly once, `tailor audit` reports hard/advisory/skipped breakdowns, fetcher exponential-backoff retries, dropped entries actually removed from the tailored resume. 208 tests.
- **v0.7.0** — Planned: tectonic CI integration, multi-JD ranked output, web UI for audit reports, full Golden adapter for deepeval's `assert_test`. 303 tests.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Code of Conduct

This project follows the [Contributor Covenant v2.1](CODE_OF_CONDUCT.md).

## Security

Vulnerability reporting, supported versions, and the disclosure timeline live in [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) © 2026 Maintainer