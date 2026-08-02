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


def resolve_api_key(explicit: str | None = None) -> str:
    """Resolve API key from explicit arg, then ``API_KEY``, then ``ANTHROPIC_API_KEY``."""
    if explicit:
        return explicit
    api_key = os.environ.get("API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "API_KEY (or ANTHROPIC_API_KEY) not set. Required for Anthropic-compatible APIs."
        )
    return api_key


def resolve_base_url(explicit: str | None = None) -> str | None:
    """Resolve base URL from explicit arg, then ``BASE_URL``, then ``ANTHROPIC_BASE_URL``."""
    if explicit:
        return explicit
    return os.environ.get("BASE_URL") or os.environ.get("ANTHROPIC_BASE_URL")


def resolve_model(
    model_string: str | None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> ResolvedModel:
    """Resolve a model string into a Pydantic AI model instance.

    Supports the following formats:
    - ``MiniMax-M3`` / ``MiniMax-M2.7`` / ... → MiniMax platform (Anthropic-compatible API)
    - ``anthropic:claude-...`` → Anthropic native
    - ``openai:gpt-...`` → OpenAI native

    Environment variables (in priority order):
    - ``API_KEY`` / ``ANTHROPIC_API_KEY`` — provider auth token
    - ``BASE_URL`` / ``ANTHROPIC_BASE_URL`` — provider base URL
    - ``MODEL`` — default model identifier

    When the model name starts with ``MiniMax-``, gethired automatically
    routes through the MiniMax Anthropic-compatible base URL
    (``https://api.minimax.io/anthropic``).

    Args:
        model_string: The model identifier (env var ``MODEL`` if None).
        api_key: Override API key.
        base_url: Override base URL.

    Returns:
        A ``ResolvedModel`` containing the constructed model and a display name.
    """

    raw = model_string or os.environ.get("MODEL", "")
    if not raw:
        raise ValueError(
            "No model specified. Set MODEL env var or pass model_string."
        )

    provider_name, _, model_name = raw.partition(":")
    model_name = model_name or provider_name
    provider_name = provider_name.lower() if provider_name else ""

    if __is_minimax(model_name, provider_name):
        resolved_url = resolve_base_url(base_url) or MINIMAX_BASE_URL
        return build_anthropic_model(
            model_name=model_name,
            api_key=resolve_api_key(api_key),
            base_url=resolved_url,
            display_label="MiniMax",
        )

    if provider_name in ("anthropic", ""):
        return build_anthropic_model(
            model_name=model_name,
            api_key=resolve_api_key(api_key),
            base_url=resolve_base_url(base_url),
            display_label="Anthropic",
        )

    if provider_name == "openai":
        return build_openai_model(model_name, api_key)

    raise ValueError(
        f"Unsupported model string {raw!r}. Use 'MiniMax-M3' (MiniMax platform), "
        "'anthropic:NAME' (Anthropic), or 'openai:NAME' (OpenAI)."
    )


def __is_minimax(model_name: str, provider_name: str) -> bool:
    """Heuristic: MiniMax model names start with MiniMax-."""
    if provider_name == "minimax":
        return True
    if model_name.startswith("MiniMax-") or model_name.startswith("MiniMax"):
        return True
    return False


def build_anthropic_model(
    model_name: str,
    api_key: str,
    base_url: str | None,
    display_label: str,
) -> ResolvedModel:
    from pydantic_ai.models.anthropic import AnthropicModel
    from pydantic_ai.providers.anthropic import AnthropicProvider

    provider_kwargs: dict[str, str] = {"api_key": api_key}
    if base_url is not None:
        provider_kwargs["base_url"] = base_url
    provider = AnthropicProvider(
        api_key=provider_kwargs.get("api_key"),
        base_url=provider_kwargs.get("base_url"),
    )
    model = AnthropicModel(model_name, provider=provider)
    return ResolvedModel(
        model=model,
        display_name=f"{display_label}:{model_name}",
    )


def build_openai_model(model_name: str, api_key: str | None) -> ResolvedModel:
    """Construct an OpenAI provider model."""
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not resolved_key:
        raise ValueError("OPENAI_API_KEY not set. Required for OpenAI models.")
    provider = OpenAIProvider(api_key=resolved_key)
    model = OpenAIChatModel(model_name, provider=provider)
    return ResolvedModel(model=model, display_name=f"OpenAI:{model_name}")


__all__ = ["MINIMAX_BASE_URL", "ResolvedModel", "resolve_model"]

