# gethired Evaluation Framework

Implements the patterns described in Anthropic's
[Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents).

## Quick start

```bash
# Run the full suite (27 tasks across 6 categories)
uv run gethired-eval

# Run a single category
uv run gethired-eval --category parser

# Run with multiple trials for pass@k metrics
uv run gethired-eval --trials 3

# Override the model for LLM-based tasks
uv run gethired-eval --model MiniMax-M3
```

Results are written to `evals/results/<suite>-<timestamp>.{md,json}`.

## Layout

```
evals/
├── harness.py           # EvalHarness, task loader, runners, aggregation
├── cli.py               # gethired-eval entrypoint
├── graders/
│   ├── code.py          # Deterministic graders (string match, structure, plagiarism)
│   ├── model.py         # LLM-as-judge graders
│   └── registry.py      # Grader name → callable
├── tasks/               # YAML task definitions
│   ├── parser/          # 6 tasks
│   ├── fetcher/         # 4 tasks
│   ├── description/     # 4 tasks
│   ├── writer/          # 6 tasks
│   ├── critic/          # 4 tasks
│   └── tailor/          # 3 tasks (end-to-end multi-agent)
├── transcripts/         # Per-trial outputs (gitignored)
└── results/             # Markdown + JSON reports (gitignored)
```

## Task schema

```yaml
task:
  id: parser_basic_001
  desc: Parser extracts contact fields from the canonical sample.tex
  category: parser
  type: parser                          # runner key in harness._REGISTRY
  tags: [capability, regression]        # classification
  input:
    tex_path: sample.tex
  graders:
    - name: code.field_present          # grader registered name
      args:
        name: contact.name_present      # display name in report
        resume: $master                 # $master resolves from runner output
        path: contact.name              # dotted path on the object
    - name: code.text_contains
      args:
        name: has_kubernetes
        text: Kubernetes
        substring: kubernetes
```

### Tags

- `capability` — pass rate should climb over time
- `regression` — must stay near 100%

### Runners

| Runner key | Description |
|---|---|
| `parser` | parses TeX files (deterministic) |
| `fetcher` | constructs JobDescription from cached inputs |
| `description` | analyses JD with the heuristic `Description` agent |
| `writer` | runs the Writer agent |
| `critic` | runs the validator suite against a TailoredResume |
| `tailor` | end-to-end pipeline via the `Tailor` orchestrator |
| `code` | uses precomputed `__output__` from task input |
| `model` | model-based task (LLM judge) |

### Placeholders

Inside grader args, prefix with `$` to reference runner output keys:

| Placeholder | Resolves to |
|---|---|
| `$master` | parsed MasterResume (shared, loaded once) |
| `$tailored` | produced TailoredResume |
| `$text` | joined summary + bullets text |
| `$jd_text` | JobDescription full text |
| `$output` | entire output dict |
| `$analysis` | DescriptionAnalysis object |

## Graders

### Code-based (deterministic)

- `code.equal(actual, expected)`
- `code.field_present(resume, path)` — supports dataclass + dict access
- `code.field_length(resume, path, expected)`
- `code.text_contains(text, substring, case_insensitive=True)`
- `code.text_not_contains(text, forbidden)`
- `code.no_banned_words(text, banned)`
- `code.no_jd_plagiarism(tailored_text, jd_text, technical_allowlist)`
- `code.numbers_in_master(tailored_text, master)`
- `code.json_round_trip(tailored)`

### Model-based (LLM judge)

- `model.grade(name, rubric, output, threshold=0.7)` — see `evals/graders/model.py`

## Metrics

Per the article, every task reports:

- **`pass@1`** — fraction of trials that passed (passes / trials)
- **`pass^k`** — 1.0 if all trials passed, else 0.0
- **`pass_rate`** — pass@1 in this implementation (alias)
- **`avg_duration_ms`** — mean wall time per trial

For multiple trials (`--trials 3`), pass@k vs pass^k diverge as expected:
a single failing trial drops pass^k to 0% even if pass@1 is 67%.

## Deterministic vs LLM-backed runs

Each `writer` and `tailor` task accepts an `input.deterministic: true` flag.
When set, the runner pops `MODEL` and `DRAFT_MODEL` from the environment so
the writer falls back to its deterministic identity-style transform.

This makes the eval reproducible without API keys. Mark LLM-dependent
behaviour with `tags: [capability]` to signal a hill-to-climb (not a
regression gate).

## Adding new tasks

1. Pick the right `category` (`parser`, `fetcher`, `description`, `writer`,
   `critic`, `tailor`).
2. Pick the right `type` (matches the runner key).
3. Write graders referencing output via `$placeholder` placeholders.
4. Tag as `capability` (improving) or `regression` (must not regress).
5. Run `uv run gethired-eval --category <your_category>` to verify.

## See also

- [Anthropic: Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- [gethired README](../README.md) — architecture overview
