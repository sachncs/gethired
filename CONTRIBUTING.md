# Contributing to gethired

Thanks for your interest in contributing! This document covers the basics.

## Setup

```bash
git clone https://github.com/gethired/gethired.git
cd gethired
uv sync
```

## Development workflow

1. Create a branch from `master`.
2. Make focused commits. Each commit should pass `ruff check`, `mypy`,
   and `pytest` independently.
3. Add tests for any new behaviour. Tests are the contract — if a test
   only checks `isinstance` or `is not None`, it's not testing the
   behaviour. Verify the data round-trips and the content is correct.
4. Update the CHANGELOG with a short note in the `[Unreleased]` section.
5. Open a pull request with a clear description of the change.

## Quality gates

Run all four before pushing:

```bash
uv run ruff check gethired/ tests/
uv run ruff format --check gethired/ tests/
uv run mypy gethired/
uv run pytest tests/ --cov=gethired
```

The coverage gate is 85% (`fail_under = 85` in `pyproject.toml`).

## Coding conventions

gethired follows the conventions in `AGENTS.md` at the repo root. The
short version:

- **Single-word public names.** No multi-word `snake_case` for public
  functions, methods, classes, or constants. Internal helpers may keep
  their descriptive names, but the public surface should be a single
  word per concept. Use the module name as the disambiguator.
- **No semi-private identifiers.** Single-underscore prefixes (`_x`) are
  forbidden. Use either public names or true-private (`__x`, name-mangled
  inside classes).
- **Frozen dataclasses with `slots=True`.** All domain models live in
  `gethired/models.py` and follow this shape.
- **No `# type: ignore` or `# noqa`.** Fix the underlying issue or
  configure the linter. The CI fails on any new suppression.
- **Test the data, not the type.** A test that asserts `x is not None`
  or `isinstance(x, Foo)` is a placeholder, not a test. Verify the
  content round-trips, the fields are populated, and the side effects
  match the contract.

## Adding a new agent

The existing agents (`Writer`, `Critic`, `Fetcher`, `Profiler`, `Parser`,
`Renderer`) are wired into the `Tailor` orchestrator. To add a new agent:

1. Create `gethired/<name>.py` with a single public class.
2. Use single-word public names; module name is the disambiguator.
3. Emit a `Step` (the traceable unit of work) for each significant
   action.
4. Add the agent to `Tailor.__init__` and `Tailor.run`.
5. Write tests that exercise the agent's data path end-to-end.

## Reporting issues

Please open a GitHub issue with a minimal reproduction. If the issue is a
bug, include the expected vs actual behaviour and the relevant section of
`trace.jsonl` if available.
