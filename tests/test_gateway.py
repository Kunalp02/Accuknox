"""Gateway API key resolution tests."""

import pytest

from orchestrator_llm.client import (
    GatewayConfig,
    effective_api_key,
    is_cloud_gateway,
    normalize_model_for_gateway,
    resolve_gateway_api_key,
)


def test_cloud_gateway_rejects_placeholder_key():
    assert resolve_gateway_api_key("https://ollama.com/v1", None, "ollama") == ""


def test_local_gateway_allows_placeholder_key():
    assert resolve_gateway_api_key("http://localhost:11434/v1", None, "ollama") == "ollama"


def test_stored_key_takes_precedence():
    assert resolve_gateway_api_key("https://ollama.com/v1", "real-key", "ollama") == "real-key"


def test_is_cloud_gateway():
    assert is_cloud_gateway("https://ollama.com/v1") is True
    assert is_cloud_gateway("http://localhost:11434/v1") is False


def test_normalize_cloud_model_strips_suffix():
    assert normalize_model_for_gateway("gpt-oss:120b-cloud", "https://ollama.com/v1") == "gpt-oss:120b"
    assert normalize_model_for_gateway("gpt-oss:120b", "https://ollama.com/v1") == "gpt-oss:120b"
    assert normalize_model_for_gateway("gpt-oss:120b-cloud", "http://localhost:11434/v1") == "gpt-oss:120b-cloud"


def test_effective_api_key_local_placeholder():
    cfg = GatewayConfig(
        base_url="http://localhost:11434/v1",
        api_key="",
        default_model="llama3.2",
        embed_model="nomic-embed-text",
    )
    assert effective_api_key(cfg) == "ollama"


def test_effective_api_key_cloud_requires_key():
    cfg = GatewayConfig(
        base_url="https://ollama.com/v1",
        api_key="",
        default_model="gpt-oss:120b",
        embed_model="nomic-embed-text",
    )
    with pytest.raises(ValueError, match="API key required"):
        effective_api_key(cfg)
