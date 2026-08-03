"""Module-level constants for gethired.

All values are ``UPPER_CASE`` per AGENTS.md. Every magic literal in the
codebase is defined here with a rationale docstring.
"""

from __future__ import annotations

PAGES: int = 1
"""Maximum resume length in pages for candidates with under ten years of experience."""

MODEL_VAR: str = "MODEL"
"""Environment variable name used to read the default model identifier."""

QUANTIFY: float = 0.7
"""Minimum fraction of bullets that must contain a digit, percent, or dollar sign.

The 70% threshold follows the standard resume-advice heuristic: a resume in
which the majority of bullets quantify impact (numbers, percentages, dollar
amounts) is materially more persuasive to recruiters and passes ATS scoring
hueristics that look for quantified accomplishments.
"""

CACHE_DAYS: int = 7
"""Maximum age in days before a cached job description is re-fetched."""

RETRIES: int = 3
"""Maximum number of attempts when fetching a job description URL."""

CONSENT_PATH: str = "~/.config/gethired/consent.json"
"""Path to the persistent PII consent record."""

CONSENT_DAYS: int = 90
"""Days after which the user is re-prompted for PII consent."""

CONSENT: str = (
    "gethired will send your master resume, job description URLs, and tailoring "
    "outputs to the configured model provider (e.g. Anthropic, OpenAI). "
    "This data leaves your machine. Continue? [y/N]"
)
"""Banner text shown before the first LLM call."""

TIMESTAMP: str = "%Y-%m-%dT%H:%M:%S.%fZ"
"""ISO-8601 UTC timestamp format with millisecond precision."""

DATA_DIR: str = "data"
"""Default directory for master.json and JD cache."""

OUTPUT_DIR: str = "tailored"
"""Default directory for tailored run outputs."""

CACHE_DIR: str = "data/jd_cache"
"""Default subdirectory for cached JDs."""

MASTER: str = "data/master.json"
"""Default path for the master JSON snapshot."""

TECTONIC: str = "tectonic"
"""Binary name for the tectonic LaTeX engine (preferred)."""

PDFLATEX: str = "pdflatex"
"""Binary name for the pdflatex LaTeX engine (fallback)."""

LATEX_VAR: str = "LATEX_ENGINE"
"""Environment variable selecting the LaTeX engine (defaults to ``tectonic``)."""

COMPILE_TIMEOUT: int = 60
"""Maximum wall time for a single PDF compilation subprocess run."""

TOKENS_BASE: int = 2500
"""Fixed overhead tokens for a tailoring run (system prompt, tool definitions, analysis)."""

TOKENS_BULLET: int = 150
"""Approximate tokens consumed by the LLM when rewriting a single bullet."""

DRIFT_SCALE: int = 100
"""Denominator used to scale the voice-drift-risk ratio into [0, 1]."""

RATIONALE_CHARS: int = 100
"""Character budget for the per-Job rationale preview string."""

DROP_CHARS: int = 80
"""Character budget for the drop-reason rationale preview string."""

KEYWORDS_MAX: int = 40
"""Maximum number of top-frequency keywords returned from a JD for coverage analysis."""

KEYWORDS_FALLBACK: int = 15
"""Top-N most-frequent keywords used as must-haves when the JD has no explicit list."""
