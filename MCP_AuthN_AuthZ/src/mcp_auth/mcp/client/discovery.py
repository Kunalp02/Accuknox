"""RFC 9728 Protected Resource Metadata discovery."""

from typing import Any

import httpx


async def fetch_protected_resource_metadata(base_url: str) -> dict[str, Any]:
    url = base_url.rstrip("/")
    candidates = [
        f"{url}/.well-known/oauth-protected-resource",
        f"{url}/.well-known/oauth-protected-resource/mcp",
    ]
    async with httpx.AsyncClient(timeout=15.0) as client:
        for candidate in candidates:
            response = await client.get(candidate)
            if response.status_code == 200:
                return response.json()
    raise RuntimeError("Protected resource metadata not found (RFC 9728)")


async def fetch_authorization_server_metadata(auth_server_url: str) -> dict[str, Any]:
    base = auth_server_url.rstrip("/")
    url = f"{base}/.well-known/oauth-authorization-server"
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
