<p align="center">
  <h1 align="center">gethired</h1>
  <p align="center">Production-grade multi-agent CV tailoring system grounded in a master resume and verified against ATS gates.</p>
  <p align="center">
    <a href="#installation"><img src="https://img.shields.io/badge/python-3.12%20%7C%203.13-blue" alt="Python"></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
    <a href="https://github.com/gethired/gethired/actions"><img src="https://img.shields.io/github/actions/workflow/status/gethired/gethired/ci.yml?branch=master" alt="CI"></a>
    <a href="https://pypi.org/project/gethired/"><img src="https://img.shields.io/pypi/v/gethired" alt="PyPI"></a>
    <a href="https://github.com/gethired/gethired/stargazers"><img src="https://img.shields.io/github/stars/gethired/gethired" alt="Stars"></a>
  </p>
</p>

**Production-grade multi-agent CV tailoring built on Pydantic AI.**

gethired is a layered, multi-agent pipeline that rewrites a candidate's
master resume against one or more job descriptions while staying
strictly grounded in the master, blocking fabrication, and verifying
the result against 12 ATS-compliance gates (9 hard-blocking, 3 advisory).
Every collaborator
(parser, fetcher, description, writer, critic, profiler,
validator, renderer) is replaceable through small, well-typed
interfaces; the default wiring uses Anthropic-compatible APIs.

The framework is fully typed (PEP 484 + PEP 695 modern syntax), fully
documented (Google-style docstrings on every public function), and
ships with a loguru-backed central logger plus structured per-step
trace events. Production defaults: every rewrite is grounded
against the master via `GroundedCitation`, every batch is traced
via `Job.id = uuid4()`, every output is run through grounding, style,
plagiarism, and 12 ATS gates (9 hard-blocking, 3 advisory) before render.

| Concern | Library |
|---|---|
| Agent framework | [Pydantic AI](https://github.com/pydantic/pydantic-ai) |
| Data validation | [Pydantic 2](https://github.com/pydantic/pydantic) |
| HTTP | [httpx](https://github.com/encode/httpx) (sync client) |
| Web extraction | [trafilatura](https://github.com/adbar/trafilatura) + JSON-LD |
| PDF extraction | [PyMuPDF](https://github.com/pymupdf/pymupdf) |
| Templates | [Jinja2](https://github.com/pallets/jinja) |
| CLI | [Typer](https://github.com/tiangolo/typer) |
| Logging | [loguru](https://github.com/Delgan/loguru) |
| Retries | [tenacity](https://github.com/jd/tenacity) |
| Tests | pytest |

## Features

- **No fabrication** — Every rewrite traces back to a `GroundedCitation` (master path + verbatim span + sha256 of master). The validator refuses the output if any cited span isn't actually in `master.json`.
- **Multi-agent architecture** — parser, fetcher, description, writer, critic. Each is a small class with a focused responsibility and a clean dependency contract.
- **ATS hard contract** — 12 tri-state gates (pass/fail/skip) run after every run: 9 hard-blocking (PDF compiles, PDF text extractable, PDF text matches txt, standard section headings, no layout tables, no images, no colours, 10–12 pt font, length within limit) and 3 advisory (keyword coverage, bullet quantification, action verbs). A failed hard gate blocks the run; advisory failures and skipped PDF gates (when `LATEX_ENGINE=none`) never block.
- **Anti-AI language** — Banned-word list with verb-stem matching; parallelism detector; voice-profile drift check; punctuation-density normalisation.
- **Anti-plagiarism** — 5-gram overlap detector against the JD corpus, minus a curated `TECHNICAL_NGRAMS_ALLOWLIST` so common jargon doesn't false-positive.
- **Voice preservation** — Per-master fingerprint (avg bullet length, std-dev, opening verbs, punctuation density, sentence count) injected into the writer's prompt so rewrites stay in the candidate's voice.
- **Traceability** — Every pipeline step emits a `Job` value object (`Job.id = uuid4()`). The full Job trail appears in `match_report.md` for every run.
- **Multi-format input** — Master resumes accepted as `text`, `pdf`, `image` (vision-capable model), or `tex`. Output is always TeX.
- **Model-agnostic** — Anthropic native, OpenAI native, and the **MiniMax platform** (Anthropic-API-compatible at `https://api.minimax.io/anthropic`) all work out of the box. `MODEL=MiniMax-M3` auto-routes.
- **CLI uniform pattern** — `tailor <verb> <noun>`: `ingest`, `fetch`, `run`, `plan`, `show`, `validate`, `trace`, `diff`, `edit`, `finalize`. Each command is single-purpose and scriptable.
- **PII consent** — First run prompts for consent (`y/N`); recorded in `~/.config/gethired/consent.json`; re-prompted every 90 days.
- **PDF compilation via tectonic** — Compiles the TeX into a PDF; falls back to `pdflatex`. Set `LATEX_ENGINE=pdflatex` to override.
- **Multi-JD consolidated run** — `Tailor(job_description=(jd_a, jd_b))` merges analyses (union of must-haves, intersection of nice-to-haves).
- **`tailor audit <run-dir>`** — Re-runs all four validators against a previous run; emits `audit.json` + `audit.md`.
- **Cover-letter tailoring** — `Tailor(..., produce_cover_letter=True)` writes `cover_letter.md`.
- **Streaming intermediate output** — `Writer.tailor(..., on_progress=...)` emits `ProgressEvent`s as the pipeline runs.
- **`--dry-run preflight`** — `gethired preflight <urls>` prints cost estimate + gate prediction without an LLM call.

## Installation

### From source

```bash
git clone https://github.com/gethired/gethired.git
cd gethired
uv sync
```

### From PyPI (planned)

```bash
pip install gethired
```

Core deps only: pydantic-ai, pydantic, httpx, trafilatura, readability-lxml, pymupdf, jinja2, typer, rich, loguru, python-dotenv, tenacity. Optional dev deps add pytest, pytest-asyncio, pytest-cov, mypy, ruff, types-requests.

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

### Tracing (v0.5.0+)

Every `Tailor.run()` emits OpenTelemetry-compatible spans to `tailored/<run-id>/trace.jsonl`. The deepeval-style graders in `evals/graders/code.py` consume this trace to score component-level behaviour (tool selection, argument correctness), reasoning-layer behaviour (plan quality, plan adherence), and overall-execution outcomes (task completion, step efficiency). Set `GETHIRED_TRACE_PATH=off` to disable.

### CLI

```bash
# Set up once
uv sync
cp .env.example .env
# Edit .env: set API_KEY=<your-MiniMax-key>, MODEL=MiniMax-M3, BASE_URL=https://api.minimax.io/anthropic

# Parse master, fetch JD, run full pipeline
gethired ingest sample.tex
gethired run https://example.com/jd
gethired show master
gethired trace <run-id>
```

Every `gethired run` writes a `tailored/<run-id>/` directory containing `tailored.tex`, `tailored.txt`, `tailored.json`, and `match_report.md`.

### Programmatic Tailor entry

```python
from gethired import Tailor
from gethired.tailor import Tailor

tailor = Tailor(
    resume=master_resume,            # Master or path to .tex
    job_description=job_description, # Job or URL string
    debug=True,                      # verbose loguru output
)
result = tailor.run()
```

The CLI uses the same `Tailor` class under the hood; the public surface is identical.

## Configuration

Settings live in `.env` (gitignored). The CLI loads them at startup.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_KEY` | yes (for LLM) | unset | Auth token (preferred). Falls back to `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` |
| `BASE_URL` | no | auto | API base URL. Auto-set to `https://api.minimax.io/anthropic` for MiniMax models |
| `MODEL` | no | unset | Model identifier (e.g. `MiniMax-M3`, `anthropic:claude-sonnet-4-5`, `openai:gpt-5`) |
| `OPENAI_API_KEY` | no | unset | Required only if `MODEL` starts with `openai:` |
| `DRAFT_MODEL` | no | unset | Optional cheap model for preflight drafts |
| `WEBSEARCH_PROVIDER` | no | `duckduckgo` | One of `duckduckgo`, `anthropic`, `openai` |
| `RESUME_TAILOR_CONSENT` | no | unset | Set automatically after first-run consent |

Precedence: constructor arguments → `.env` → built-in defaults. Without `MODEL` and without an injected `model_instance`, `Tailor(...)` raises `ConfigurationError` immediately.

## Commands

| Command | Purpose |
|---|---|
| `gethired ingest <tex>` | parse master resume into `data/master.json` |
| `gethired fetch <urls>` | fetch + cache JDs (sync httpx, content-hash invalidation) |
| `gethired run <urls>` | full pipeline: parser → fetcher → description → profiler → writer → critic → renderer |
| `gethired plan <urls>` | cost estimate only (no LLM call) |
| `gethired show master` | print `data/master.json` |
| `gethired show jd --url URL` | print a cached JD |
| `gethired validate <path>` | run ATS gates against a `tailored.json` |
| `gethired trace <run-id>` | pretty-print Job trail from a previous run |
| `gethired diff <a> <b>` | diff two tailored runs (markdown) |
| `gethired audit <run-dir>` | re-run all 4 validators against a previous run; emit `audit.json` + `audit.md` |
| `gethired cover <urls>` | run pipeline + write `cover_letter.md` |
| `gethired preflight <urls>` | dry-run: cost + gate prediction, no LLM call |

## Traceability

Every pipeline step emits a `Job` value object (`Job.id = uuid4()`) with `type`, `started_at`, `completed_at`, `status`, `inputs`, `outputs`, `rationale`, `model`, `tool_name`, and typed `metadata`. `Job.description()` returns a serialisable `JobData` for the audit trail.

Every rewritten bullet carries a `GroundedCitation` (tailored path + master path + verbatim span + `job_id`). The grounding validator refuses the output if any cited span isn't actually in `master.json`. Run output:

```
tailored/<run-id>/
├── tailored.tex       # ATS-compliant LaTeX source
├── tailored.txt       # plain-text ATS version
├── tailored.json      # full Tailored with traceability
├── tailored.pdf       # compiled (when pdflatex is available)
└── match_report.md    # Run Description · Job Trail · ATS Gates · Keyword Coverage
```

## Multi-Agent Architecture

| Agent | File | Responsibility |
|---|---|---|
| Parser | `parser.py` | text/pdf/image/tex → `Master` |
| Fetcher | `fetcher.py` | URL → `Job` (sync httpx, content-hash cache) |
| Description | `description.py` | structured JD analysis (role, seniority, must-have skills) |
| Writer | `writer.py` | main tailoring (Pydantic AI + 7 read-only tools) |
| Critic | `critic.py` | validation pipeline (grounding/style/plagiarism/ATS) |
| Search | (planned) | WebSearch sub-agent (duckduckgo default) |

The `Tailor` class orchestrates them: `parse → fetch → describe → profile → write → critique → render`. Every step emits a `Job`; render is gated on the ATS report (a failed hard gate blocks the run, advisory and skipped gates do not).

## Project Structure

```
gethired/
├── parser         # text/pdf/image/tex → Master
├── fetcher        # URL → Job
├── description    # JD analysis
├── writer         # main tailoring agent
├── critic         # validator agent
├── profiler       # voice fingerprint
├── rubric         # CHECKLIST + GROUNDING + ANTI_AI + PLAGIARISM
├── validator      # deterministic checks
├── renderer       # Tailored → tex/txt/match_report
├── tailor         # Tailor orchestrator
├── provider       # model resolution (Anthropic / OpenAI / MiniMax)
├── serialize      # JSON ↔ Master/Tailored coercion
├── models         # frozen dataclasses (Run/Job/Job)
├── normalize      # canonical numeric / latex-strip / tokenize
├── observability  # loguru central logging
├── tracing        # OpenTelemetry-compatible JSONL span emitter
├── exceptions     # *Error hierarchy
├── constants      # UPPER_CASE module constants
└── cli            # typer CLI
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

The suite covers: parser (against the real `sample.tex`), normalisation (canonical numeric / latex-strip / tokenize), voice profiler, rubric, provider resolution (Anthropic / OpenAI / MiniMax), writer (LLM path with `TestModel`), all four validators (grounding, style, plagiarism, ATS with hard/advisory tiers and tri-state PDF gates), end-to-end pipeline runs, multi-JD consolidated runs, audit, cover letter, streaming, preflight, PDF compile, fetcher retries, and drop application. Current count: 230 tests (208 unit/integration + 9 property-based + 10 CLI end-to-end + 3 misc).

## Smoke test against real LLM

```bash
uv run python tests/smoke_e2e.py
```

Runs the full pipeline with the configured model on a synthetic JD; emits `tailored/<run-id>/{tailored.tex,tailored.txt,tailored.json,match_report.md}`.

## Tech Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.12+ |
| Agent framework | Pydantic AI |
| Data validation | Pydantic 2 |
| Logging | loguru |
| CLI | Typer + Rich |
| HTTP | httpx (sync) |
| Web extraction | trafilatura + JSON-LD |
| PDF extraction | PyMuPDF |
| Templates | Jinja2 |
| Retries | tenacity |
| Tests | pytest, pytest-asyncio, pytest-cov, respx |

## Roadmap

- **v0.1.0** — Scaffold + parser + models + normalised text utilities. 40 tests.
- **v0.2.0** — Multi-agent pipeline (parser, fetcher, description, writer, critic, tailor, renderer). CLI. Validator (grounding, style, plagiarism, 11 ATS gates). 67 tests.
- **v0.3.0** — MiniMax provider integration. `Tailor(resume=…, job_description=…, debug=True)` programmatic API. LLM-backed writer via Pydantic AI. 81 tests.
- **v0.4.0** — PDF compile via `tectonic` (pdflatex fallback), multi-JD consolidated run, `tailor audit <run-dir>`, cover-letter tailoring, streaming intermediate output, `--dry-run` preflight visualisation. 129 tests.
- **v0.5.0** — OpenTelemetry-compatible tracing (`gethired/tracing.py`, JSONL span emission). Six deepeval-style agent-evaluation graders (component / reasoning / overall-execution layers). `parse_image` wired to a vision-capable model. `job()` factory split into focused builders. **Zero `# noqa:` / `# type: ignore` suppressions** across the codebase. 150 tests.
- **v0.6.0** — Production-ready plain-text `parse_text`, 12 tri-state ATS gates split into 9 hard-blocking + 3 advisory, compile-based PDF page counting, PDF-gate `skip` when `LATEX_ENGINE=none`, missing contact fields fail fast with `MasterParsingError`, critic re-validates the compiled PDF exactly once, `tailor audit` reports hard/advisory/skipped breakdowns, fetcher exponential-backoff retries, dropped entries actually removed from the tailored resume. 208 tests.
- **v0.7.0** — Planned: tectonic CI integration, multi-JD ranked output, web UI for audit reports, full Golden adapter for deepeval's `assert_test`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Code of Conduct

This project follows the [Contributor Covenant v2.1](CODE_OF_CONDUCT.md).

## Security

Vulnerability reporting, supported versions, and the disclosure timeline live in [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) © 2026 Maintainer
