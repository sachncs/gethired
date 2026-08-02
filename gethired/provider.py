"""Model provider resolution.

Constructs Pydantic AI ``Model`` instances for any supported provider. Includes
special handling for the MiniMax platform (Anthropic-API-compatible at
``https://api.minimax.io/anthropic``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final

MINIMAX_BASE_URL: Final[str] = "https://api.minimax.io/anthropic"
"""MiniMax platform Anthropic-compatible base URL."""


@dataclass(frozen=True, slots=True)
class ResolvedModel:
    """A resolved model ready to pass to a Pydantic AI Agent."""

    model: object  # pydantic_ai.models.Model
    display_name: str


def resolve_model(
    model_string: str | None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> ResolvedModel:
    """Resolve a model string into a Pydantic AI model instance.

    Supports the following formats:
    - ``anthropic:MiniMax-M3`` → MiniMax platform via Anthropic API
    - ``anthropic:claude-...`` → Anthropic native
    - ``openai:gpt-...`` → OpenAI native
    - ``minimax:MiniMax-M3`` → alias for ``anthropic:MiniMax-M3``
    - ``MiniMax-M3`` → bare model name → MiniMax platform via Anthropic API

    Args:
        model_string: The model identifier (env var ``MODEL`` if None).
        api_key: Override API key (defaults to env var).
        base_url: Override base URL (defaults to provider-specific).

    Returns:
        A ``ResolvedModel`` containing the constructed model and a display name.
    """
    from pydantic_ai.models.anthropic import AnthropicModel
    from pydantic_ai.providers.anthropic import AnthropicProvider

    raw = model_string or os.environ.get("MODEL", "")
    if not raw:
        raise ValueError(
            "No model specified. Set MODEL env var or pass model_string."
        )

    provider_name, _, model_name = raw.partition(":")
    model_name = model_name or provider_name
    provider_name = provider_name.lower() if provider_name else ""

    if _is_minimax(model_name, provider_name):
        return _build_anthropic_model(
            model_name=model_name,
            api_key=api_key,
            base_url=base_url or os.environ.get("ANTHROPIC_BASE_URL") or MINIMAX_BASE_URL,
            display_label="MiniMax",
        )

    if provider_name in ("anthropic", ""):
        return _build_anthropic_model(
            model_name=model_name,
            api_key=api_key,
            base_url=base_url or os.environ.get("ANTHROPIC_BASE_URL"),
            display_label="Anthropic",
        )

    raise ValueError(
        f"Unsupported model string {raw!r}. Use 'anthropic:NAME', 'openai:NAME', "
        "or 'MiniMax-M3' (MiniMax platform)."
    )


def _is_minimax(model_name: str, provider_name: str) -> bool:
    """Heuristic: MiniMax model names start with MiniMax-."""
    if provider_name in ("minimax", "minimax"):
        return True
    if model_name.startswith("MiniMax-") or model_name.startswith("MiniMax"):
        return True
    return False


def _build_anthropic_model(
    model_name: str,
    api_key: str | None,
    base_url: str | None,
    display_label: str,
) -> ResolvedModel:
    from pydantic_ai.models.anthropic import AnthropicModel
    from pydantic_ai.providers.anthropic import AnthropicProvider

    resolved_api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not resolved_api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not set. Required for Anthropic-compatible APIs "
            "(Anthropic, MiniMax)."
        )
    resolved_base_url = base_url or os.environ.get("ANTHROPIC_BASE_URL")
    provider_kwargs: dict[str, str] = {"api_key": resolved_api_key}
    if resolved_base_url:
        provider_kwargs["base_url"] = resolved_base_url
    provider = AnthropicProvider(**provider_kwargs)
    model = AnthropicModel(model_name, provider=provider)
    return ResolvedModel(
        model=model,
        display_name=f"{display_label}:{model_name}",
    )


__all__ = ["MINIMAX_BASE_URL", "ResolvedModel", "resolve_model"]
