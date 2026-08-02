"""Module-level constants for gethired.

All values are ``UPPER_CASE`` per AGENTS.md. Every magic literal in the
codebase should be defined here with a rationale in the docstring.
"""

from __future__ import annotations

MAX_RETRIES: int = 2
"""Maximum number of retry attempts after the first agent run."""

MAX_VOICE_DEVIATION: float = 0.6
"""Maximum allowed voice profile deviation score (0 = identical, 1 = fully divergent)."""

MAX_BULLET_LENGTH_RATIO: float = 2.0
"""Tailored bullets may not exceed this multiple of the master bullet length."""

MAX_PAGES: int = 1
"""Maximum resume length in pages for candidates with under ten years of experience."""

MAX_WEBSEARCH_PER_RUN: int = 3
"""Maximum WebSearch capability invocations per tailoring run."""

MODEL_ENV_VAR: str = "MODEL"
"""Environment variable name used to read the default model identifier."""

DRAFT_MODEL_ENV_VAR: str = "DRAFT_MODEL"
"""Environment variable name used to read the optional draft model identifier."""

WEBSEARCH_PROVIDER_ENV_VAR: str = "WEBSEARCH_PROVIDER"
"""Environment variable name used to read the WebSearch provider name."""

WEBSEARCH_DEFAULT_PROVIDER: str = "duckduckgo"
"""Default WebSearch provider; chosen for provider-agnostic operation without API keys."""

BULLET_QUANTIFICATION_THRESHOLD: float = 0.7
"""Minimum fraction of bullets that must contain a digit, percent, or dollar sign.

The 70% threshold follows the standard resume-advice heuristic: a resume in
which the majority of bullets quantify impact (numbers, percentages, dollar
amounts) is materially more persuasive to recruiters and passes ATS scoring
hueristics that look for quantified accomplishments.
"""

CACHE_MAX_AGE_DAYS: int = 7
"""Maximum age in days before a cached job description is re-fetched."""

JD_FETCH_MAX_ATTEMPTS: int = 3
"""Maximum number of attempts when fetching a job description URL."""

CONSENT_FILE_PATH: str = "~/.config/gethired/consent.json"
"""Path to the persistent PII consent record."""

CONSENT_RE_PROMPT_DAYS: int = 90
"""Days after which the user is re-prompted for PII consent."""

CONSENT_TEXT: str = (
    "gethired will send your master resume, job description URLs, and tailoring "
    "outputs to the configured model provider (e.g. Anthropic, OpenAI). "
    "This data leaves your machine. Continue? [y/N]"
)
"""Banner text shown before the first LLM call."""

TIMESTAMP_ISO_FORMAT: str = "%Y-%m-%dT%H:%M:%S.%fZ"
"""ISO-8601 UTC timestamp format with millisecond precision."""

DEFAULT_DATA_DIR: str = "data"
"""Default directory for master.json and JD cache."""

DEFAULT_TAILORED_DIR: str = "tailored"
"""Default directory for tailored run outputs."""

DEFAULT_CACHE_DIR: str = "data/jd_cache"
"""Default subdirectory for cached JDs."""

DEFAULT_MASTER_JSON: str = "data/master.json"
"""Default path for the master JSON snapshot."""
