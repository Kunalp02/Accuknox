from enum import StrEnum


class UserRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    BUILDER = "builder"
    VIEWER = "viewer"


ROLE_PERMISSIONS: dict[str, set[str]] = {
    UserRole.OWNER: {
        "agent:read", "agent:write", "agent:invoke", "agent:publish",
        "workflow:read", "workflow:write", "workflow:invoke", "workflow:publish",
        "kb:read", "kb:write",
        "mcp:read", "mcp:write",
        "api_key:read", "api_key:write",
        "run:read",
        "org:read", "org:write", "user:invite",
    },
    UserRole.ADMIN: {
        "agent:read", "agent:write", "agent:invoke", "agent:publish",
        "workflow:read", "workflow:write", "workflow:invoke", "workflow:publish",
        "kb:read", "kb:write",
        "mcp:read", "mcp:write",
        "api_key:read", "api_key:write",
        "run:read",
        "org:read", "user:invite",
    },
    UserRole.BUILDER: {
        "agent:read", "agent:write", "agent:invoke", "agent:publish",
        "workflow:read", "workflow:write", "workflow:invoke", "workflow:publish",
        "kb:read", "kb:write",
        "mcp:read", "mcp:write",
        "run:read",
    },
    UserRole.VIEWER: {
        "agent:read",
        "workflow:read",
        "kb:read",
        "mcp:read",
        "run:read",
    },
}


def has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())
