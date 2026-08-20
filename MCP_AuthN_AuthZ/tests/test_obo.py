"""Tests for OBO token exchange."""

from unittest.mock import AsyncMock, patch

import pytest

from mcp_auth.mcp.client.obo import OboExchangeRequest, exchange_token_entra_obo, exchange_token_rfc8693


@pytest.mark.asyncio
async def test_rfc8693_exchange():
    mock_response = AsyncMock()
    mock_response.raise_for_status = lambda: None
    mock_response.json = lambda: {
        "access_token": "downstream-token",
        "expires_in": 3600,
        "token_type": "Bearer",
    }

    with patch("mcp_auth.mcp.client.obo.httpx.AsyncClient") as client_cls:
        client_cls.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        result = await exchange_token_rfc8693(
            OboExchangeRequest(
                token_endpoint="https://auth.example.com/token",
                client_id="client",
                subject_token="user-token",
                audience="https://downstream.example.com",
                scopes=["read"],
            )
        )
    assert result.access_token == "downstream-token"


@pytest.mark.asyncio
async def test_entra_obo_exchange():
    mock_response = AsyncMock()
    mock_response.raise_for_status = lambda: None
    mock_response.json = lambda: {
        "access_token": "graph-token",
        "expires_in": 3600,
        "token_type": "Bearer",
    }

    with patch("mcp_auth.mcp.client.obo.httpx.AsyncClient") as client_cls:
        client_cls.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        result = await exchange_token_entra_obo(
            "https://login.microsoftonline.com/tenant/oauth2/v2.0/token",
            "client-id",
            "client-secret",
            "user-assertion-jwt",
            ["https://graph.microsoft.com/User.Read"],
        )
    assert result.access_token == "graph-token"
