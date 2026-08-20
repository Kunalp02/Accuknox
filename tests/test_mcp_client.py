"""Tests for MCP HTTP client options."""

from unittest.mock import AsyncMock, patch

import pytest

from orchestrator_mcp.client import McpHttpClient, McpHttpOptions


@pytest.mark.asyncio
async def test_http_client_uses_connection_options():
    captured: dict = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"result": {"tools": []}}

    async def fake_post(url, json, headers):
        return FakeResponse()

    with patch("orchestrator_mcp.client.httpx.AsyncClient") as client_cls:
        instance = AsyncMock()
        instance.post = fake_post
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        client_cls.side_effect = lambda **kwargs: (captured.update(kwargs) or instance)

        client = McpHttpClient(
            "https://mcp.example.com",
            http_options=McpHttpOptions(verify_ssl=False, trust_env=False),
        )
        await client.list_tools()

    assert captured["verify"] is False
    assert captured["trust_env"] is False
