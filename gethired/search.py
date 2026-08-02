"""Web search sub-agent.

Wraps Pydantic AI's ``WebSearch`` capability with provider-agnostic defaults
and audit logging.
"""

from __future__ import annotations

from gethired.constants import WEBSEARCH_DEFAULT_PROVIDER, WEBSEARCH_PROVIDER_ENV_VAR
from gethired.observability import step_logger

import os


class Search:
    """Wrapper around Pydantic AI's WebSearch capability with audit logging."""

    def __init__(self, provider: str | None = None) -> None:
        self._provider = provider or os.environ.get(
            WEBSEARCH_PROVIDER_ENV_VAR, WEBSEARCH_DEFAULT_PROVIDER
        )
        self._logger = step_logger("search")

    @property
    def provider(self) -> str:
        return self._provider

    def capability(self):
        """Return a configured WebSearch capability for a Pydantic AI Agent.

        Importing pydantic_ai lazily to keep this module dependency-free for
        unit tests that don't need the WebSearch capability itself.
        """
        try:
            from pydantic_ai.capabilities import WebSearch  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - pydantic_ai always present
            raise RuntimeError("pydantic-ai is required for WebSearch capability") from exc
        return WebSearch(provider=self._provider)


__all__ = ["Search"]
