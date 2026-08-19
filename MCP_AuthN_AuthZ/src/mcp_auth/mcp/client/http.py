from dataclasses import dataclass
from typing import Any

import httpx

from mcp_auth.security import decrypt_secret


@dataclass
class McpAuth:
    auth_type: str
    credentials: str


@dataclass
class McpTool:
    name: str
    description: str
    input_schema: dict


class McpHttpClient:
    """MCP client over HTTP JSON-RPC with pluggable auth."""

    def __init__(self, base_url: str, auth: McpAuth | None = None, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.auth = auth
        self.timeout = timeout
        self._request_id = 0

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if not self.auth:
            return headers
        if self.auth.auth_type in ("bearer", "oauth2", "oauth2_obo"):
            headers["Authorization"] = f"Bearer {self.auth.credentials}"
        elif self.auth.auth_type == "api_key_header":
            if ":" in self.auth.credentials:
                name, value = self.auth.credentials.split(":", 1)
                headers[name.strip()] = value.strip()
        return headers

    async def _rpc(self, method: str, params: dict | None = None) -> Any:
        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.base_url, json=payload, headers=self._headers())
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                raise RuntimeError(data["error"].get("message", str(data["error"])))
            return data.get("result", {})

    async def list_tools(self) -> list[McpTool]:
        result = await self._rpc("tools/list")
        tools = result.get("tools", [])
        return [
            McpTool(
                name=t.get("name", ""),
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", t.get("input_schema", {})),
            )
            for t in tools
        ]

    async def call_tool(self, name: str, arguments: dict) -> str:
        result = await self._rpc("tools/call", {"name": name, "arguments": arguments})
        content = result.get("content", [])
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts) if parts else str(result)


def auth_from_connection(
    auth_type: str | None,
    encrypted_credentials: str | None,
    encrypted_token: str | None = None,
) -> McpAuth | None:
    if encrypted_token and auth_type in ("oauth2", "oauth2_obo", "bearer"):
        return McpAuth(auth_type=auth_type or "bearer", credentials=decrypt_secret(encrypted_token))
    if encrypted_credentials and auth_type:
        return McpAuth(auth_type=auth_type, credentials=decrypt_secret(encrypted_credentials))
    return None


async def test_connection(base_url: str, auth: McpAuth | None) -> tuple[bool, list[McpTool], str]:
    try:
        client = McpHttpClient(base_url, auth)
        tools = await client.list_tools()
        return True, tools, "healthy"
    except Exception as e:
        return False, [], str(e)
