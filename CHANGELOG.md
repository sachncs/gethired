# Changelog

All notable changes to gethired will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- End-to-end smoke test (`tests/smoke_e2e.py`) that exercises the full pipeline against the configured LLM (MiniMax-M3 verified) and emits `tailored/<run-id>/` with a rewritten, grounded summary.
- Typed `JobMetadata` dataclass replacing the previous primitive `dict[str, str]`.
- Per-step loguru trace events via `step_logger(step_name, run_id, **fields)`.
- Auto-detection of MiniMax models: `MODEL=MiniMax-M3` (or any `MiniMax-*`) auto-routes to `https://api.minimax.io/anthropic`.
- Simplified env vars: `API_KEY` (preferred) / `ANTHROPIC_API_KEY` (fallback), `BASE_URL` / `ANTHROPIC_BASE_URL`.

### Changed

- `WriterOutput` switched from nested Pydantic models (`BulletDraft`) to flat `dict[str, list[str]]` to satisfy MiniMax-M3's tool-use JSON schema validation.
- `TailoredResume.run_result` is now `Optional[RunResult]` so the LLM can construct the model without supplying an internal field.
- CLI quick-start now uses `API_KEY` instead of `ANTHROPIC_API_KEY` in the example.

### Removed

- Logfire integration and `LOGFIRE_TOKEN_ENV_VAR` (replaced with pure loguru central logging).

## [0.3.0] - 2026-08-02

### Added

- **MiniMax platform provider**: bare-name routing for `MiniMax-M3` and the M-series; `ANTHROPIC_BASE_URL` automatically set to the MiniMax Anthropic-compatible endpoint.
- `gethired/provider.py` with `resolve_model()` for any provider string.
- 9 provider-resolution tests; 2 writer LLM-path tests.

### Changed

- Writer now uses a Pydantic AI `Agent` with 7 read-only tools when a model is configured. Falls back to the deterministic writer when no model is set.
- All grounding / style / plagiarism / ATS outputs flow through the deterministic validator before render.

### Fixed

- `JobType.LOOKUP` enum added so tool-call Jobs render correctly in `match_report.md`.
- `TailoredResume.run_result` made Optional so Pydantic AI can construct it from the LLM output.

## [0.2.0] - 2026-08-02

### Added

- **Multi-agent architecture**: parser, fetcher, description, writer, critic, search, profiler, rubric, validator, renderer, tailor, models, normalize, observability, exceptions, constants, cli. One-word module names per AGENTS.md.
- **Tailor orchestrator** with `Tailor(resume, job_description, debug, model, draft_model, data_dir, tailored_dir)`.
- **CLI** (`typer`): `ingest`, `fetch`, `run`, `plan`, `show master`, `show jd`, `validate`, `trace`, `diff`. Uniform verb-noun pattern.
- **Validators**: grounding (no fabrication), style (banned-word list with verb-stem matching, parallelism detector, bullet quantification), plagiarism (5-gram overlap minus `TECHNICAL_NGRAMS_ALLOWLIST`).
- **11 ATS gates**: `PDF_COMPILES`, `PDF_TEXT_EXTRACTABLE`, `PDF_TEXT_MATCHES_TXT`, `SECTION_HEADINGS_STANDARD`, `NO_TABLES_FOR_LAYOUT`, `NO_IMAGES`, `NO_COLORS`, `FONT_SIZE_10_12`, `LENGTH_WITHIN_LIMIT`, `KEYWORDS_COVERED`, `BULLETS_QUANTIFIED`, `ACTION_VERBS_FIRST`.
- **Traceability**: `Job` value object (`Job.id = uuid4()`), `Job.description()` returning `JobDescriptionData`; `RunResult.jobs`; `websearch_calls` as derived property.
- **TeX parser** handles all resume macros (`\resumeSubheading`, `\resumeItem`, `\resumeProjectHeading`, `\href`, `\textbf`, `$O(1)$`, `R\&D`).
- **Renderer**: TeX (Jinja2), plain text, JSON, match_report.md.
- **Voice profile builder**: avg bullet length, std-dev, opening verbs, punctuation density, sentence count.
- **Fetcher**: sync httpx, content-hash cache with `CACHE_MAX_AGE_DAYS`, retry with exponential backoff.
- 67 tests passing.

## [0.1.0] - 2026-08-02

### Added

- Scaffold: `.gitignore`, `.env.example`, `pyproject.toml` with pinned dependency lower bounds, `uv.lock`.
- Models: 21 frozen dataclasses with `slots=True`, `WebSearch` (renamed from `WebSearchCall`), `Run.id = uuid4()`, `SourceReference` with `.description()`, `job(...)` factory.
- Normalisation: `canonicalize_numeric` (handles `10K`, `10,000+`, `ten thousand`), `strip_latex_commands`, `tokenize_for_overlap`, `normalise_whitespace`, `is_action_verb`.
- Parser against the existing `resume.tex` (10 experiences, 3 projects, 1 education, 2 awards).
- Central loguru logging via `observability.py` with `configure_logging(debug, log_file, run_id)`.
- Exceptions: `ResumeTailoringError`, `GroundingViolationError`, `StyleViolationError`, `PlagiarismViolationError`, `AtsGateFailureError`, `MasterParsingError`, `JobDescriptionRetrievalError`, `ConfigurationError`.
- 40 tests passing.
