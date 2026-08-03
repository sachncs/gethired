# Changelog

All notable changes to gethired will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **New module `gethired/serialize.py`** — single source of truth for JSON ↔ domain-model coercion (`coerce_master_from_dict`, `coerce_tailored_from_dict`, `load_master_from_json`, `master_to_snapshot`, `render_json`, `tailored_to_snapshot_dict`, `MasterSnapshot`). Previously triplicated across `tailor.read_master_json`, `audit.__coerce_tailored`/`__coerce_master`, and inline code in `cli.validate`. `tailor.py` and `cli.py` now re-export `coerce_bullets` / `read_master_json` / `to_tailored` from `serialize.py` for backward compatibility.
- **PDF-artefact guard helper** — `validator.pdf_artefact_status()` consolidates the `if pdf_path is None / not exists` guard previously repeated in `gate_pdf_compiles`, `gate_pdf_text_extractable`, `gate_pdf_text_matches_txt`, and `gate_length_within_limit`. Each gate now calls the helper and proceeds with its real check on the happy path.
- **Property-based tests** (`tests/test_normalize_property.py`) — `hypothesis`-driven coverage for `normalise_whitespace` (idempotence, no double-spaces), `canonicalize_numeric` (always returns a set of ints), `tokenize_for_overlap` (lowercase roundtrip), `extract_ngrams` (length preservation), and `MasterResume.content_hash` (determinism, sensitivity to input). `hypothesis>=6.100` added to dev dependencies.
- **CLI end-to-end tests** (`tests/test_cli.py`) — `typer.testing.CliRunner` coverage for `--help`, `ingest`, `show master`, `show jd` (error path), `validate` (tex vs json, error path), `trace` (error path), `audit` (error path), `diff` (error path), `fetch` (with monkeypatched retriever).
- **Module-level `Logger` type alias** in `observability.py` for annotating logger parameters. `fetcher.__fetch_with_retry` now takes `logger: Logger` instead of an untyped `logger` parameter.
- **New `Final` constants** for previously-inlined magic values: `TOKEN_ESTIMATE_BASE` (2500), `TOKENS_PER_BULLET` (150), `VOICE_DRIFT_NORMALIZER` (100), `JOB_RATIONALE_PREVIEW_CHARS` (100), `DROP_REASON_RATIONALE_CHARS` (80), `KEYWORD_EXTRACTION_LIMIT` (40), `MUST_HAVE_FALLBACK_KEYWORDS` (15). `description.py` now exposes `RESPONSIBILITY_MARKERS`, `SENIORITY_KEYWORDS`, `SENIORITY_RANK`, `UNKNOWN_ROLE_LABEL`, `UNSPECIFIED_SENIORITY_LABEL` as module-level `Final` constants (the in-function `seniority_rank` literal is gone).
- **Tri-state ATS gates** — `AtsGateResult` now carries a `status` (`pass`/`fail`/`skip`); `GateStatus` and `GateTier` enums added. PDF-dependent gates `skip` when `LATEX_ENGINE=none` and no PDF artefact exists, so runs without a LaTeX engine are not falsely blocked.
- **Gate tiers** — `AtsGate.tier` splits the 12 gates into `HARD_GATES` (9) and `ADVISORY_GATES` (3). `AtsGateReport.hard_failed_gates` / `advisory_failed_gates` / `skipped_gates`; `all_passed` tolerates `skip` and `outcome_from_ats` blocks only on hard failures. `tailor audit` reports the hard/advisory/skipped breakdown.
- **Compile-based page counting** — `gate_length_within_limit` measures the compiled PDF's actual `page_count` via PyMuPDF against `MAX_PAGES`.

### Changed

- **AGENTS.md §843-856 visibility compliance** — every `self._x` single-underscore instance attribute has been renamed to its public form (`self.x`). Affected classes: `Tailor` (12 attributes), `Critic` (2), `Fetcher` (2), `Writer` (4), `Tracer` (3), `JsonlSink` (3), `ActiveSpan` (3). The class is the encapsulation boundary; attributes are part of the object's public state. Internal helpers (`_x` module-level) in `plain_text.py` and `serialize.py` renamed to public forms too (the `_heading_index` → `find_heading_index` rename avoids a collision with the `heading_index` local variable in `extract_experiences` etc.). `tracing.py`'s private classes `_ActiveSpan` and `_JsonlSink` are now public `ActiveSpan` and `JsonlSink`; `_TRACE_PATH_ENV` is now `TRACE_PATH_ENV`; module-level `_new_span_id` → `new_span_id`, `_now_iso` → `now_iso`, `_noop_cm` → `null_span_cm`. The ContextVar `_current_tracer` in `writer.py` is now `current_tracer` and is part of `writer.__all__`. The module-level double-underscore helpers in `audit.py` and `provider.py` (`__load_tailored_and_master`, `__is_minimax`) remain "true private" per AGENTS.md.
- **CLI `__all__` and `trace.jsonl` schemas unchanged** — on-disk snapshots remain byte-compatible because the `serialize.py` JSON shape matches the previous `renderer.render_json` output exactly.

### Removed

- **Dead code: `models.StepType` enum** — the 8-member `StepType(StrEnum)` was defined and exported in `models.py:42-53` and `__init__.py` but never read by any caller. Removed along with the `test_step_type_enum_values` test.
- **Unwired `gethired/search.py` and its three constants** (`MAX_WEBSEARCH_PER_RUN`, `WEBSEARCH_PROVIDER_ENV_VAR`, `WEBSEARCH_DEFAULT_PROVIDER`) — the `Search` class was never invoked; Pydantic AI's `WebSearch` capability is not registered in the writer. YAGNI: removed both the module and the orphan constants. The architecture table in `README.md` now notes the search sub-agent as "(planned)".
- **Local JSON-coercion duplication** — `tailor.read_master_json`, `tailor.to_tailored`, `cli.master_to_snapshot`, the inline `finalize` coercion, `audit.__coerce_tailored`/`__coerce_master`, and `renderer.render_json` all delegate to `serialize.py`.
- **Inline magic numbers** in `tailor.py:263,295` (`2_500 + bullets * 150`), `tailor.py:311` (`/ 100`), `writer.py:222` (`rationale[:100]`), `writer.py:543` (`rationale[:80]`), `fetcher.py:300` (`most_common(40)`), `fetcher.py:320` (`extract_keywords(text)[:15]`), `description.py:98-106` (`seniority_rank` dict), `description.py:130-138` (`RESPONSIBILITY_MARKERS`), `description.py:146-153` (`SENIORITY_KEYWORDS`) — all replaced by named constants (see Added).



### Changed

- **Breaking**: missing contact fields in a master resume now raise `MasterParsingError` at parse time instead of being silently tolerated.
- **Breaking**: `parse_text` is production-ready: stricter handling of math delimiters, multiple education entries, skill category boundaries, and residual TeX commands.
- Critic re-runs against the compiled PDF exactly once per run; `merge_critic_jobs` drops all prior validation jobs before appending the authoritative pass.
- Fetcher retries now sleep with exponential backoff between attempts; cache persistence uses `dataclasses.asdict`.
- Writer drops are applied: entries listed in `WriterOutput.dropped` are removed from the tailored resume instead of only being recorded.
- Removed dead code: `rank_experiences`, `FINAL_TAILORED_TO_TEXT`/`FINAL_GROUNDING` aliases, unused constants (`MAX_RETRIES`, `MAX_VOICE_DEVIATION`, `MAX_BULLET_LENGTH_RATIO`, `DRAFT_MODEL_ENV_VAR`), `render_diff`, and the `normalizer_helpers` shim.

## [0.5.0] - 2026-08-02

### Added

- **OpenTelemetry-compatible tracing** in `gethired/tracing.py`. `Tracer` emits JSONL spans to `tailored/<run-id>/trace.jsonl`. `tracer_for_run()` factory; opt-out via `GETHIRED_TRACE_PATH=off`. ContextVar-based active span so tool/llm spans emit without threading the tracer through call sites. New module includes `TraceSpan` dataclass with `name`, `kind` (`agent`/`tool`/`llm`/`validate`), `started_at`, `ended_at`, `duration_ms`, `attributes`, `parent_id`, `span_id`.
- **Deepeval-style agent-evaluation graders** in `evals/graders/code.py`:
  - Component layer: `code_tool_correctness` (ToolCorrectnessMetric), `code_argument_correctness` (ArgumentCorrectnessMetric).
  - Reasoning layer: `code_plan_adherence` (PlanAdherenceMetric), `code_plan_quality` (PlanQualityMetric).
  - Overall execution: `code_task_completion` (TaskCompletionMetric), `code_step_efficiency` (StepEfficiencyMetric).
  - All consume the trace.jsonl emitted by the tracer. `WRITER_TOOL_NAMES` exposes the agent's tool set as the canonical reference.
- `parse_image()` now wires to a vision-capable Pydantic AI agent. Reads the file, sends bytes to a multimodal model named in `IMAGE_MODEL` (or `MODEL`), pipes the extracted text through the TeX parser. The `path` argument is now actually used.
- `jobs_from_tool_calls(result)` signature simplified: dropped the unused `master` parameter that was declared for a planned master-aware extraction.

### Changed

- **Breaking**: `job()` factory split into focused builders: `job_tailor`, `job_validate`, `job_lookup`, plus the generic `job()`. All callers updated. A new `JobEnvelope` dataclass carries the shared fields (model, tool_name, status, timestamps). Resolves the `PLR0913` and `A002` noqa suppressions.
- **Breaking**: `grounding_check()` no longer accepts a `quantification_threshold` parameter — quantification is enforced by `style_check` and `gate_bullets_quantified` instead.
- **Breaking**: `gate_length_within_limit()` now uses the structured `TailoredResume` (sum of experiences+projects bullets) alongside the TeX `re.findall` bullet count, cross-checking the two sources.
- **Breaking**: `parse_task()` no longer accepts an unused `source` parameter.
- Inline `_bullet`/`_bullets` helpers in `cli.py` and `tailor.py` replaced by a module-level `coerce_bullets()` helper. Resolves the visibility-noise introduced by the AGENTS.md §824-856 single-underscore prohibition.
- `evals/harness.py` exception handler retained as `except Exception` but with the per-file `BLE001` suppression centralised in `pyproject.toml` rather than scattered as inline `noqa: BLE001` comments.

### Removed

- **`# noqa:` and `# type: ignore` suppressions: 9 → 0** across `gethired/`, `tests/`, `evals/`. Each suppression was either replaced by a real fix (split factory, dropped parameter, removed dead code) or centralised into `pyproject.toml` per-file-ignores. The codebase now passes `mypy --strict` and `ruff check` with zero suppressions outside `pyproject.toml`.
- `tests/test_models.py`: the no-op `if f.default is not f.default_factory or True` filter that always included every field is gone. The test now actually constructs each model from defaults and verifies frozen semantics.
- Defensive `try/except ImportError` for `pymupdf`, `trafilatura`, `WebSearch` (pydantic_ai) removed — these are now hard dependencies declared in `pyproject.toml`.

## [0.4.0] - 2026-08-02

### Added

- **PDF compilation via tectonic** with pdflatex fallback (`LATEX_ENGINE` env var). New module `gethired/render_pdf.py`. Constants: `TECTONIC_BINARY`, `PDFLATEX_BINARY`, `LATEX_ENGINE_ENV_VAR`, `PDF_COMPILE_TIMEOUT_SECONDS`. New exception: `PdfCompilationError`.
- **Multi-JD consolidated run**: `Tailor(job_description=(jd_a, jd_b))`. New `description.analyze_multiple()` consolidates analyses (union of must-haves, intersection of nice-to-haves, highest seniority, deduplicated responsibilities).
- **`tailor audit <run-dir>`**: new CLI command + new module `gethired/audit.py`. Re-runs grounding, style, plagiarism, and ATS gates against a previous run; emits `audit.json` + `audit.md`.
- **Cover-letter tailoring**: new models `CoverLetter` + `CoverLetterParagraph`; new module `gethired/cover_letter.py`. `Tailor(..., produce_cover_letter=True)` writes `cover_letter.md`.
- **Streaming intermediate output**: new module `gethired/streaming.py` with `ProgressEvent` + `progress_reporter` context manager. `Writer.tailor(..., on_progress=...)` emits events at step boundaries.
- **`--dry-run preflight`**: new method `Tailor.preflight()` + new CLI command. Returns `PreflightReport` with token estimate, expected gates, JD keyword coverage, voice drift risk, missing must-haves — no LLM call.
- `Tailor.__init__` accepts `model_instance: object | None` for dependency-injected test models.
- New CLI commands: `audit`, `cover`, `preflight`.

### Removed

- **Deterministic writer fallback**. `Writer` no longer ships an in-process identity-style transform. `Tailor(...)` raises `ConfigurationError` at construction when `MODEL` is unset and `model_instance` is None.

### Changed

- **Breaking**: callers relying on the silent deterministic fallback must now set `MODEL` + `API_KEY`, or inject a `TestModel`. The eval harness flag `deterministic: true` is renamed to `use_test_model: true`.

### Fixed

- Repo-wide cleanup: single-underscore identifiers converted to true-private (`__`) in `writer.py`, `tailor.py`, `fetcher.py`, `provider.py`, `cli.py`.
- Fixed `UnboundLocalError` in `renderer.render_tex` (local `env` shadowed `env()` function).
- Wrapped several lines exceeding the 100-char ruff limit.

## [Unreleased]

### Added

- Plug-and-play library API: `parse`, `fetch`, and the standalone
  `grounding`/`style`/`plagiarism`/`ats` validators. `import gethired`
  is now lazy — heavy dependencies (pymupdf, trafilatura, pydantic_ai)
  are only imported when a public symbol that needs them is accessed.
- `gethired.parse` convenience entry point that dispatches by file
  extension (`parse_tex`, `parse_text`, `parse_pdf`, `parse_image`).
- `gethired.fetch` convenience entry point that wraps the Fetcher with
  a default cache directory.
- `gethired.serialize` module: single source of truth for JSON ↔
  domain-model coercion (replaces 3x duplication across tailor, audit,
  cli).
- `gethired.version` module exporting `__version__` (now `0.6.0`).
- `tests/test_grounding_round_trip.py`: 4 new tests verifying the
  citation round-trip property (real span passes, fabricated span
  fails, partial span passes, end-to-end pipeline produces valid
  grounding).
- `.github/workflows/ci.yml`: ruff lint, ruff format check, mypy, and
  pytest with 85% coverage gate.
- `.github/workflows/release.yml`: build and publish wheel to PyPI
  on version tag push.
- `LICENSE` (MIT) and `py.typed` marker (PEP 561).
- `CONTRIBUTING.md` and `SECURITY.md`.

### Changed

- **Single-word public naming across the entire codebase.** Every
  domain model, constant, validator gate, and public function now
  uses a single-word name. Module name disambiguates where needed
  (e.g. `parse_tex` becomes `gethired.parser.tex`). All renames are
  traceable in the per-module commits.
- **No semi-private identifiers.** All `_x` single-underscore module
  aliases and `self._x` instance attributes were removed or renamed to
  public. True-private (`__x`, name-mangled) names remain in two
  helpers per AGENTS.md.
- `gethired/__init__.py` exposes a 6-name public surface: `Tailor`,
  `Master`, `Tailored`, `Job`, `parse`, `fetch`. All other symbols
  are loaded lazily via `__getattr__`.
- `gethired.parser.dispatch` and `gethired.render.tex` are now the
  public single-word names; the original multi-word names
  (`parse_tex`, `render_tex`) remain as backward-compat aliases.
- The `WebSearch` dataclass was deleted (was unreferenced dead code).
- Tests now verify the data process end-to-end: contact round-trips,
  no fabricated skills, citation spans match the master, on-disk
  artefacts persist, and the full Step trail includes all expected
  validation kinds.

### Removed

- `gethired/search.py` (was an unwired stub for a Pydantic AI
  WebSearch sub-agent).
- All `# noqa:` and `# type: ignore` suppressions across the
  codebase remain at zero.

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
