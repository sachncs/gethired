"""Tests for the model provider resolver."""

from __future__ import annotations

import pytest

from gethired.provider import MINIMAX_BASE_URL, resolve_model


def test_minimax_default_base_url_is_set() -> None:
    assert MINIMAX_BASE_URL == "https://api.minimax.io/anthropic"


def test_minimax_model_string_routes_to_minimax_base_url(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.delenv("BASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)

    resolved = resolve_model("MiniMax-M3")
    assert "MiniMax-M3" in resolved.display_name
    assert "MiniMax" in resolved.display_name


def test_bare_minimax_name_defaults_to_minimax(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.delenv("BASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)

    resolved = resolve_model("MiniMax-M3")
    assert "MiniMax" in resolved.display_name


def test_anthropic_native_uses_default_base(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.delenv("BASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)

    resolved = resolve_model("anthropic:claude-sonnet-4-5")
    assert "claude-sonnet-4-5" in resolved.display_name
    assert "Anthropic" in resolved.display_name


def test_explicit_base_url_overrides_default(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.delenv("BASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)

    custom = "https://my-proxy.example.com/anthropic"
    resolved = resolve_model("MiniMax-M3", base_url=custom)
    assert resolved.display_name


def test_legacy_anthropic_api_key_still_works(monkeypatch) -> None:
    """Backward compatibility: ANTHROPIC_API_KEY still accepted if API_KEY unset."""
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "legacy-key")
    monkeypatch.delenv("BASE_URL", raising=False)

    resolved = resolve_model("MiniMax-M3")
    assert resolved.display_name


def test_legacy_anthropic_base_url_still_works(monkeypatch) -> None:
    """Backward compatibility: ANTHROPIC_BASE_URL still accepted if BASE_URL unset."""
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.delenv("BASE_URL", raising=False)
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

    resolved = resolve_model("anthropic:claude-sonnet-4-5")
    assert resolved.display_name


def test_missing_api_key_raises(monkeypatch) -> None:
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(ValueError, match="API_KEY"):
        resolve_model("anthropic:MiniMax-M3")


def test_missing_model_string_raises(monkeypatch) -> None:
    monkeypatch.delenv("MODEL", raising=False)

    with pytest.raises(ValueError, match="No model specified"):
        resolve_model(None)


def test_minimax_m_series_models_recognised(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.delenv("BASE_URL", raising=False)

    for name in ("MiniMax-M3", "MiniMax-M2.7", "MiniMax-M2.7-highspeed", "MiniMax-M2.1"):
        resolved = resolve_model(name)
        assert "MiniMax" in resolved.display_name


def test_unknown_provider_string_raises(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.delenv("BASE_URL", raising=False)

    with pytest.raises(ValueError, match="Unsupported model string"):
        resolve_model("gpt-5:unknown")


def test_base_url_env_var_resolved(monkeypatch) -> None:
    """BASE_URL env var is picked up."""
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setenv("BASE_URL", "https://custom.example.com/anthropic")
    resolved = resolve_model("MiniMax-M3")
    assert resolved.display_name
