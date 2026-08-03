"""Convenience entry point: fetch a job description URL with caching + retry.

Standalone usage::

    from gethired import fetch
    jd = fetch("https://example.com/job")

The cache lives in ``~/.cache/gethired/jd_cache/`` by default. Override
``cache_dir`` for a custom location.
"""

from __future__ import annotations

import os
from pathlib import Path

from gethired.fetcher import Fetcher
from gethired.models import Job

__all__ = ["fetch"]


def fetch(url: str, cache_dir: str | Path | None = None) -> Job:
    """Fetch and cache a job description.

    Args:
        url: The job description URL.
        cache_dir: Optional cache directory (defaults to ``~/.cache/gethired/jd_cache``).

    Returns:
        A populated ``Job`` (the JD).
    """
    resolved_cache_dir = Path(cache_dir) if cache_dir is not None else _default_cache()
    retriever = Fetcher(cache_dir=resolved_cache_dir)
    return retriever.retrieve(url)


def _default_cache() -> Path:
    override = os.environ.get("GETHIRED_CACHE_DIR")
    if override:
        return Path(override)
    return Path(os.path.expanduser("~/.cache/gethired/jd_cache"))
