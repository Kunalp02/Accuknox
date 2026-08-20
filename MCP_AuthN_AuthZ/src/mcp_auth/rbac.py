from enum import StrEnum


class UserRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    BUILDER = "builder"
    VIEWER = "viewer"


ROLE_PERMISSIONS: dict[str, set[str]] = {
    UserRole.OWNER: {
        "mcp:read",
        "mcp:write",
        "mcp:connect",
        "mcp:invoke",
        "mcp:server:read",
        "mcp:server:invoke",
        "api_key:read",
        "api_key:write",
        "audit:read",
        "org:read",
    },
    UserRole.ADMIN: {
        "mcp:read",
        "mcp:write",
        "mcp:connect",
        "mcp:invoke",
        "mcp:server:read",
        "mcp:server:invoke",
        "api_key:read",
        "api_key:write",
        "audit:read",
        "org:read",
    },
    UserRole.BUILDER: {
        "mcp:read",
        "mcp:write",
        "mcp:connect",
        "mcp:invoke",
        "mcp:server:read",
        "mcp:server:invoke",
        "audit:read",
    },
    UserRole.VIEWER: {
        "mcp:read",
        "mcp:server:read",
        "audit:read",
    },
}


def has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


def has_scope(scopes: list[str], permission: str) -> bool:
    return permission in scopes
