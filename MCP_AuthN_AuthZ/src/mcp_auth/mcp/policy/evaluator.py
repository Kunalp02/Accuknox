import time
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from mcp_auth.auth.context import AuthContext
from mcp_auth.db.models import McpConnection, McpToolInvocation
from mcp_auth.rbac import has_permission, has_scope
from mcp_auth.security import hash_arguments


@dataclass
class InvokeContext:
    direction: str = "outbound"
    agent_id: str | None = None


class PolicyDenied(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class ToolPolicyEvaluator:
    def can_invoke(
        self,
        auth: AuthContext,
        connection: McpConnection | None,
        tool_name: str,
        *,
        direction: str = "outbound",
    ) -> None:
        permission = "mcp:server:invoke" if direction == "inbound" else "mcp:invoke"
        if auth.is_api_key:
            if not has_scope(auth.scopes or [], permission):
                raise PolicyDenied("API key missing required scope")
        elif not auth.role or not has_permission(auth.role, permission):
            raise PolicyDenied("Role lacks permission")

        if connection and connection.organization_id != auth.org_id:
            raise PolicyDenied("Connection not in organization")

        if connection and connection.tool_allowlist:
            if tool_name not in connection.tool_allowlist:
                raise PolicyDenied(f"Tool '{tool_name}' not on allowlist")


async def audit_invocation(
    session: AsyncSession,
    auth: AuthContext,
    *,
    tool_name: str,
    status: str,
    direction: str = "outbound",
    connection_id: str | None = None,
    arguments: dict | None = None,
    error_message: str | None = None,
    latency_ms: int | None = None,
) -> McpToolInvocation:
    record = McpToolInvocation(
        id=str(uuid.uuid4()),
        organization_id=auth.org_id,
        connection_id=connection_id,
        tool_name=tool_name,
        direction=direction,
        principal_type=auth.principal_type,
        principal_id=auth.principal_id,
        status=status,
        arguments_hash=hash_arguments(arguments or {}),
        error_message=error_message,
        latency_ms=latency_ms,
    )
    session.add(record)
    await session.commit()
    return record


class TimedInvocation:
    def __init__(self):
        self.start = time.perf_counter()

    @property
    def latency_ms(self) -> int:
        return int((time.perf_counter() - self.start) * 1000)
