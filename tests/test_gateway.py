"""Gateway API key resolution tests."""

from orchestrator_llm.client import is_cloud_gateway, resolve_gateway_api_key


def test_cloud_gateway_rejects_placeholder_key():
    assert resolve_gateway_api_key("https://ollama.com/v1", None, "ollama") == ""


def test_local_gateway_allows_placeholder_key():
    assert resolve_gateway_api_key("http://localhost:11434/v1", None, "ollama") == "ollama"


def test_stored_key_takes_precedence():
    assert resolve_gateway_api_key("https://ollama.com/v1", "real-key", "ollama") == "real-key"


def test_is_cloud_gateway():
    assert is_cloud_gateway("https://ollama.com/v1") is True
    assert is_cloud_gateway("http://localhost:11434/v1") is False
