# gethired — Agent Conventions

This file documents the conventions referenced from code docstrings and
`CONTRIBUTING.md`. It is the canonical reference for any automated
agent (LLM-based or otherwise) that contributes to or audits this repo.

## 1. Module and package layout

- One concept per module. Module names are single-word (`parser`,
  `tailor`, `critic`); they disambiguate public names.
- Subpackages live under `gethired/`. Public surface is re-exported from
  `gethired/__init__.py` via `__getattr__` for lazy loading.
- The CLI entry point is `gethired.cli:app`. Importing `gethired.cli`
  loads the full dependency graph (pymupdf, pydantic_ai, trafilatura),
  but `import gethired` itself stays cheap.

## 2. Naming

- Public functions, classes, methods, constants: single-word
  `snake_case`. Use the module name as the disambiguator
  (`parser.tex`, `validator.style`, `serialize.snapshot`).
- Single-underscore instance attributes (`self._x`) are forbidden on
  classes; attributes are either public (`self.x`) or true-private
  (`self.__x`, name-mangled).
- Module-level "private" helpers may keep `_x` if they're true helpers,
  but prefer renaming to a single-word public name plus a more specific
  verb.

## 3. Data models

- All domain models in `gethired/models.py` are `@dataclass(frozen=True,
  slots=True)`.
- Field names use single-word snake_case for simple fields
  (`name`, `email`) and short compounds for complex ones
  (`master_path`, `verbatim_span`).
- `Tailored` and `Resume` share the same field layout for the common
  sections (name, email, summary, skills, experience, projects,
  education, awards). `Tailored` adds `dropped`, `rationale`,
  `grounding`, `jobs`, `run_result`.
- New fields must have safe defaults so existing JSON snapshots
  deserialise without modification.

## 4. Configuration objects

- Functions that accept many parameters prefer a configuration dataclass
  over a long positional list. See `StepEnv` in `gethired/models.py` for
  the canonical pattern.

## 5. Constants

- All magic literals live in `gethired/constants.py` and are
  `UPPER_CASE`. Code references the constant; the rationale for the
  value lives in the constant's docstring.

## 6. Exceptions

- Every exception inherits from `Exception` and ends with `Error`
  (`TailorError`, `ParseError`, `FetchError`, etc.).
- Module-level exceptions live in `gethired/exceptions.py`.

## 7. Error suppression

- No `# type: ignore` and no `# noqa:` comments in source code or
  tests. Fix the underlying issue or configure the linter via
  `pyproject.toml` per-file-ignores.
- The CI fails on any new suppression.

## 8. CLI

- Uniform `verb noun` command pattern: `ingest`, `fetch`, `run`,
  `cover`, `plan`, `preflight`, `validate`, `show`, `trace`, `audit`,
  `diff`.
- Each command is implemented as a Typer `@app.command()` decorated
  function with explicit type-annotated arguments.

## 9. Testing

- Tests live in `tests/` and mirror the module layout
  (`tests/test_parser.py` covers `gethired/parser.py`).
- Property-based tests use `hypothesis`. They declare a section header
  in their docstring referencing this file.
- Tests verify data round-trips and content is correct, not merely that
  types match (`isinstance` / `is not None` placeholders are not
  accepted).

## 10. Dependency hygiene

- New runtime deps go in `[project.dependencies]` in `pyproject.toml`.
- New dev-only deps go in `[project.optional-dependencies].dev`.
- The lockfile is `uv.lock`; regenerate with `uv lock` after dep
  changes.
