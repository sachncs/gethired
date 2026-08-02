# gethired

Multi-agent Pydantic AI system for crafting CVs against job descriptions, grounded in a master resume and verified against ATS gates.

## Status

v0.2.0 — full pipeline operational with model-agnostic provider (Anthropic, OpenAI, **MiniMax platform**). 78 tests passing.

## Supported models

- **Anthropic** (native): `anthropic:claude-sonnet-4-5`, `anthropic:claude-opus-4-1`, …
- **OpenAI** (native): `openai:gpt-5`, `openai:gpt-4o`, …
- **MiniMax platform** (Anthropic-API-compatible at `https://api.minimax.io/anthropic`): `MiniMax-M3`, `MiniMax-M2.7`, `MiniMax-M2.7-highspeed`, `MiniMax-M2.5`, `MiniMax-M2.1`, `MiniMax-M2`

When the model name starts with `MiniMax-`, gethired automatically routes through the MiniMax Anthropic-compatible API. Set `API_KEY` to your MiniMax key and the rest works out of the box.

## Architecture (one-word modules)

```
gethired/
├── parser         # text/pdf/image/tex → MasterResume
├── fetcher        # URL → JobDescription (sync httpx, content_hash cache)
├── description    # JD analysis
├── writer         # main tailoring agent (Pydantic AI + read-only tools)
├── critic         # validator agent (grounding/style/plagiarism/ATS)
├── search         # WebSearch sub-agent (duckduckgo default)
├── profiler       # voice fingerprint
├── rubric         # CHECKLIST + GROUNDING + ANTI_AI + PLAGIARISM rules
├── validator      # deterministic checks (grounding/style/plagiarism/ATS)
├── renderer       # TailoredResume → tex/txt/json/match_report
├── tailor         # Tailor orchestrator (entry point)
├── provider       # model resolution (Anthropic / OpenAI / MiniMax)
├── models         # frozen dataclasses, Run/Job/JobDescription
├── normalize      # canonical numeric / latex-strip / tokenize
├── observability  # loguru central logging
├── exceptions     # *Error hierarchy
├── constants      # UPPER_CASE module constants
└── cli            # typer CLI
```

## Quick start

```bash
uv sync
cp .env.example .env
# Set ANTHROPIC_API_KEY to your MiniMax key (or Anthropic / OpenAI key)
export $(grep -v '^#' .env | xargs)
uv run gethired --help
```

## Commands (uniform verb-noun pattern)

| Command | Purpose |
|---|---|
| `gethired ingest <tex>` | parse master resume into `data/master.json` |
| `gethired fetch <urls>` | fetch + cache JDs |
| `gethired run <urls>` | full tailoring pipeline |
| `gethired plan <urls>` | cost estimate only |
| `gethired show master` | print master.json |
| `gethired show jd <url>` | print cached JD |
| `gethired validate <path>` | run ATS gates |
| `gethired trace <run-id>` | pretty-print Job trail |
| `gethired diff <a> <b>` | diff two tailored runs |

## Programmatic API

```python
from gethired import Tailor, MasterResume, JobDescription

tailor = Tailor(
    resume=master_resume,            # or path to .tex
    job_description=job_description, # or URL string
    debug=True,
    model="MiniMax-M3",              # optional; defaults to MODEL env var
)
result = tailor.run()                # TailoredResume
```

## Traceability

Every pipeline step emits a `Job` value object (`Job.id = uuid4()`).
Use `tailored.run_result.jobs` to inspect, or `tailor.trace <run-id>` to
pretty-print. Each tailored claim carries a `GroundedCitation` pointing
back to a master span; the validator enforces that every span is verbatim
present in `master.json`.

## License

MIT.
