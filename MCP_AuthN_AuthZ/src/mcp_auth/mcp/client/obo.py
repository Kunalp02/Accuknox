"""OBO (On-Behalf-Of) / RFC 8693 token exchange."""

from dataclasses import dataclass

import httpx

from mcp_auth.mcp.client.oauth import OAuthTokenSet


@dataclass
class OboExchangeRequest:
    token_endpoint: str
    client_id: str
    subject_token: str
    audience: str
    scopes: list[str]
    client_secret: str | None = None
    grant_type: str = "token_exchange"


async def exchange_token_rfc8693(request: OboExchangeRequest) -> OAuthTokenSet:
    """Generic RFC 8693 token exchange."""
    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "client_id": request.client_id,
        "subject_token": request.subject_token,
        "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "audience": request.audience,
        "scope": " ".join(request.scopes),
    }
    if request.client_secret:
        data["client_secret"] = request.client_secret

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(request.token_endpoint, data=data)
        response.raise_for_status()
        payload = response.json()
        return OAuthTokenSet(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_in=payload.get("expires_in"),
            token_type=payload.get("token_type", "Bearer"),
        )


async def exchange_token_entra_obo(
    token_endpoint: str,
    client_id: str,
    client_secret: str,
    user_assertion: str,
    scopes: list[str],
) -> OAuthTokenSet:
    """Microsoft Entra On-Behalf-Of flow."""
    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "client_id": client_id,
        "client_secret": client_secret,
        "assertion": user_assertion,
        "scope": " ".join(scopes),
        "requested_token_use": "on_behalf_of",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(token_endpoint, data=data)
        response.raise_for_status()
        payload = response.json()
        return OAuthTokenSet(
            access_token=payload["access_token"],
            expires_in=payload.get("expires_in"),
            token_type=payload.get("token_type", "Bearer"),
        )
