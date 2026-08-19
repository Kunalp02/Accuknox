# MCP AuthN AuthZ

Standalone backend project for **MCP client and server** with industry-standard **authentication**, **authorization**, **RBAC**, and **OBO token exchange**.

## Features

| Module | Description |
|--------|-------------|
| **MCP Client (outbound)** | HTTP JSON-RPC client with `bearer`, `api_key_header`, `oauth2`, `oauth2_obo` auth |
| **MCP Server (inbound)** | `POST /mcp` JSON-RPC endpoint with `tools/list` and `tools/call` |
| **RFC 9728** | `/.well-known/oauth-protected-resource` discovery |
| **RFC 8414** | `/.well-known/oauth-authorization-server` metadata |
| **OAuth client** | Authorization code + PKCE helpers, token refresh |
| **OBO / RFC 8693** | Token exchange + Microsoft Entra OBO format |
| **RBAC** | Roles: owner, admin, builder, viewer with fine-grained permissions |
| **Policy engine** | Tool allowlist + permission checks at invoke time |
| **Audit log** | Records inbound/outbound tool invocations |

## Quick start

```bash
cd MCP_AuthN_AuthZ
cp .env.example .env

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

uvicorn mcp_auth.main:app --reload --host 0.0.0.0 --port 8100
```

Open http://localhost:8100/docs for the interactive API.

## Auth types for MCP connections

| `auth_type` | Use case |
|-------------|----------|
| `none` | No auth (dev only) |
| `bearer` | Static bearer token (org-level) |
| `api_key_header` | Custom header (`Header-Name:value`) |
| `oauth2` | OAuth access token stored per connection |
| `oauth2_obo` | Per-user OBO token exchange before tool calls |

## API overview

| Endpoint | Description |
|----------|-------------|
| `POST /v1/auth/signup` | Create org + owner user |
| `POST /v1/auth/login` | JWT login |
| `POST /v1/auth/api-keys` | Create scoped API key (`mak_...`) |
| `CRUD /v1/mcp-connections` | Manage outbound MCP connections |
| `POST /v1/mcp-connections/{id}/invoke` | Call tool with RBAC + allowlist + audit |
| `POST /v1/mcp-connections/obo/exchange` | RFC 8693 or Entra OBO token exchange |
| `POST /mcp` | Inbound MCP JSON-RPC server |
| `GET /.well-known/oauth-protected-resource` | RFC 9728 metadata |
| `GET /v1/audit/invocations` | Tool invocation audit trail |

## Example: inbound MCP call

```bash
TOKEN=$(curl -s -X POST http://localhost:8100/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"password123","org_name":"Demo"}' \
  | jq -r .access_token)

curl -s -X POST http://localhost:8100/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"whoami","arguments":{}}}'
```

## Project layout

```
MCP_AuthN_AuthZ/
├── src/mcp_auth/
│   ├── auth/           # JWT, API key, AuthContext
│   ├── db/             # SQLAlchemy models + session
│   ├── mcp/
│   │   ├── client/     # HTTP client, OAuth, OBO, discovery
│   │   ├── server/     # Inbound MCP handlers
│   │   └── policy/     # RBAC enforcement + audit
│   ├── routes/         # FastAPI routers
│   ├── rbac.py
│   ├── security.py
│   └── main.py
└── tests/
```

## Tests

```bash
pytest -q
```

## Related docs

See `../docs/mcp_auth_rbac_concepts_guide.md` in the parent repo for the full concepts guide (OAuth, OBO, RBAC, RFC standards).
