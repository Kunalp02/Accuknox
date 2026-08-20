from dataclasses import dataclass
from typing import Any

import httpx
from orchestrator_core.models import McpConnection
from orchestrator_core.security import decrypt_secret


@dataclass
class McpAuth:
    auth_type: str  # bearer | api_key_header
    credentials: str  # plaintext after decrypt


@dataclass
class McpHttpOptions:
    """Per-connection HTTP client settings (self-signed certs, corporate proxy)."""

    verify_ssl: bool = True
    trust_env: bool = False


@dataclass
class McpTool:
    name: str
    description: str
    input_schema: dict


class McpHttpClient:
    """Minimal MCP client over HTTP JSON-RPC (Streamable HTTP / legacy HTTP)."""

    def __init__(
        self,
        base_url: str,
        auth: McpAuth | None = None,
        timeout: float = 30.0,
        http_options: McpHttpOptions | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth = auth
        self.timeout = timeout
        self.http_options = http_options or McpHttpOptions()
        self._request_id = 0

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if not self.auth:
            return headers
        if self.auth.auth_type == "bearer":
            headers["Authorization"] = f"Bearer {self.auth.credentials}"
        elif self.auth.auth_type == "api_key_header":
            # credentials format: header_name:value
            if ":" in self.auth.credentials:
                name, value = self.auth.credentials.split(":", 1)
                headers[name.strip()] = value.strip()
        return headers

    def _http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            verify=self.http_options.verify_ssl,
            trust_env=self.http_options.trust_env,
            timeout=self.timeout,
        )

    async def _rpc(self, method: str, params: dict | None = None) -> Any:
        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {},
        }
        async with self._http_client() as client:
            response = await client.post(
                self.base_url,
                json=payload,
                headers=self._headers(),
            )
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
        if parts:
            return "\n".join(parts)
        return str(result)


def auth_from_encrypted(auth_type: str, encrypted: str | None) -> McpAuth | None:
    if not encrypted or not auth_type:
        return None
    return McpAuth(auth_type=auth_type, credentials=decrypt_secret(encrypted))


def http_options_from_connection(connection: McpConnection) -> McpHttpOptions:
    return McpHttpOptions(
        verify_ssl=connection.verify_ssl,
        trust_env=connection.trust_env,
    )


def client_from_connection(connection: McpConnection) -> McpHttpClient:
    auth = auth_from_encrypted(connection.auth_type or "", connection.auth_credentials_encrypted)
    return McpHttpClient(
        connection.base_url,
        auth,
        http_options=http_options_from_connection(connection),
    )


async def test_connection(
    base_url: str,
    auth: McpAuth | None,
    http_options: McpHttpOptions | None = None,
) -> tuple[bool, list[McpTool], str]:
    try:
        client = McpHttpClient(base_url, auth, http_options=http_options)
        tools = await client.list_tools()
        return True, tools, "healthy"
    except Exception as e:
        return False, [], str(e)
