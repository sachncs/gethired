"""Web search sub-agent.

Wraps Pydantic AI's ``WebSearch`` capability with provider-agnostic defaults
and audit logging.
"""

from __future__ import annotations

import os

from pydantic_ai.capabilities import WebSearch

from gethired.constants import WEBSEARCH_DEFAULT_PROVIDER, WEBSEARCH_PROVIDER_ENV_VAR
from gethired.observability import step_logger


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

    def capability(self) -> WebSearch:
        """Return a configured WebSearch capability for a Pydantic AI Agent.

        The ``provider`` name is recorded as a description for audit logging;
        the underlying tool selection is delegated to Pydantic AI.
        """
        return WebSearch(description=f"gethired web search ({self._provider})")


__all__ = ["Search"]
