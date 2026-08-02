# gethired

Multi-agent Pydantic AI system for crafting CVs against job descriptions, grounded in a master resume and verified against ATS gates.

## Status

v0.1.0 — scaffold + foundation modules + TeX parser. Implementation in progress; see `todo.md` for the atomic checklist.

## Architecture (one-word modules)

```
gethired/
├── parser         # text/pdf/image/tex → MasterResume
├── fetcher        # URL → JobDescription (sync httpx)
├── description    # JD analysis (multi-agent)
├── writer         # main tailoring agent
├── critic         # validator agent (grounding/style/plagiarism/ATS)
├── search         # WebSearch sub-agent
├── profiler       # voice fingerprint
├── rubric         # CHECKLIST + GROUNDING + ANTI_AI + PLAGIARISM rules
├── validator      # deterministic checks (grounding/style/plagiarism/ATS)
├── renderer       # TailoredResume → tex/txt/json/match_report
├── tailor         # Tailor orchestrator (entry point)
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
| `gethired audit <run-dir>` | full audit (grounding+style+plagiarism+ATS) |
| `gethired edit` | open tailored.json in $EDITOR |
| `gethired finalize` | re-render edited JSON |
| `gethired diff <a> <b>` | diff two tailored runs |
| `gethired trace <run-id>` | pretty-print Job trail |

## Programmatic API

```python
from gethired import Tailor, MasterResume, JobDescription

tailor = Tailor(
    resume=master_resume,            # or path to .tex
    job_description=job_description, # or URL string
    debug=True,
)
result = tailor.run()                # TailoredResume
```

## Environment

See `.env.example`. `MODEL` env var selects any pydantic-ai-supported model string (`anthropic:claude-sonnet-4-5`, `openai:gpt-5`, `minimax:MiniMax-M3`, etc.).

## License

MIT.
