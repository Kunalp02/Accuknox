from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx


@dataclass
class OAuthTokenSet:
    access_token: str
    refresh_token: str | None = None
    expires_in: int | None = None
    token_type: str = "Bearer"


async def exchange_authorization_code(
    token_endpoint: str,
    client_id: str,
    code: str,
    redirect_uri: str,
    code_verifier: str,
    client_secret: str | None = None,
    resource: str | None = None,
) -> OAuthTokenSet:
    data: dict[str, str] = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }
    if client_secret:
        data["client_secret"] = client_secret
    if resource:
        data["resource"] = resource

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(token_endpoint, data=data)
        response.raise_for_status()
        payload = response.json()
        return OAuthTokenSet(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_in=payload.get("expires_in"),
            token_type=payload.get("token_type", "Bearer"),
        )


async def refresh_access_token(
    token_endpoint: str,
    client_id: str,
    refresh_token: str,
    client_secret: str | None = None,
    resource: str | None = None,
) -> OAuthTokenSet:
    data: dict[str, str] = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
    }
    if client_secret:
        data["client_secret"] = client_secret
    if resource:
        data["resource"] = resource

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(token_endpoint, data=data)
        response.raise_for_status()
        payload = response.json()
        return OAuthTokenSet(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token", refresh_token),
            expires_in=payload.get("expires_in"),
            token_type=payload.get("token_type", "Bearer"),
        )


def build_authorization_url(
    authorization_endpoint: str,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    scopes: list[str],
    state: str,
    resource: str | None = None,
) -> str:
    params: dict[str, str] = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
        "scope": " ".join(scopes),
    }
    if resource:
        params["resource"] = resource
    return f"{authorization_endpoint}?{urlencode(params)}"


def generate_pkce_pair() -> tuple[str, str]:
    import base64
    import hashlib
    import secrets

    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge
