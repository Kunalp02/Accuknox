# MCP AuthN/AuthZ — Step-by-Step Backend Implementation Guide

This document explains **why** and **in what order** the `MCP_AuthN_AuthZ` backend was built. It is written for someone who wants to understand the thinking behind each layer — not just what files exist.

---

## 0. Start with the problem (before writing code)

We wanted a backend that does three things:

1. **Authenticate** callers — who are you? (JWT users, API keys)
2. **Authorize** actions — what may you do? (RBAC roles, scopes, tool allowlists)
3. **Connect to MCP** in both directions:
   - **Outbound:** our app calls external MCP servers as a client
   - **Inbound:** external apps (Cursor, agents) call us as an MCP server

Every design decision flows from that.

```
                    ┌─────────────────────────────┐
                    │   MCP AuthN/AuthZ Backend   │
                    └─────────────────────────────┘
           ▲ inbound MCP                    outbound MCP ▼
    (Cursor calls POST /mcp)          (we call external servers)
```

**Rule used throughout:** build from the inside out — identity → permissions → data → MCP → policy → audit.

---

## Phase 1 — Project skeleton

### Step 1.1: Define the folder layout

**Thinking:** Separate concerns so auth, MCP, and HTTP routes do not tangle.

```
MCP_AuthN_AuthZ/
├── src/mcp_auth/
│   ├── config.py          # env vars
│   ├── security.py        # crypto + JWT + API key hashing
│   ├── rbac.py            # roles → permissions
│   ├── auth/              # who is calling?
│   ├── db/                # what do we store?
│   ├── mcp/
│   │   ├── client/        # outbound MCP
│   │   ├── server/        # inbound MCP
│   │   └── policy/        # can this call happen?
│   ├── routes/            # HTTP API
│   └── main.py            # FastAPI app
└── tests/
```

### Step 1.2: `config.py` + `.env.example`

**Thinking:** Every secret and URL in one place before anything else.

| Setting | Why |
|---------|-----|
| `DATABASE_URL` | SQLite for standalone dev; swap to Postgres in prod |
| `JWT_SECRET` | Sign user tokens |
| `ENCRYPTION_KEY` | Encrypt MCP passwords/tokens at rest |
| `MCP_SERVER_RESOURCE_URI` | RFC 9728 — what resource our MCP server represents |
| `BASE_URL` | OAuth metadata URLs |

### Step 1.3: `main.py` — empty FastAPI app

**Thinking:** Prove the app boots before adding complexity.

- `lifespan` → calls `init_db()` on startup
- `/health` → smoke test
- CORS → frontend can call API later

---

## Phase 2 — Identity & tenancy (who + which org)

### Step 2.1: Ask "who uses this system?"

Two types of principals:

| Principal | Use case | Auth mechanism |
|-----------|----------|----------------|
| **Human user** | Dashboard, admin UI | Email/password → JWT |
| **Machine/script** | CI, agents, integrations | API key (`mak_...`) |

Both belong to an **organization** (tenant). Company A must never see Company B's MCP connections.

### Step 2.2: Design tables (bottom-up)

#### Table: `organizations`

**Why:** Root tenant boundary. Every resource hangs off `organization_id`.

```
organizations
├── id (UUID)
├── name
├── slug (unique, for URLs)
└── created_at
```

#### Table: `users`

**Why:** Humans log in. Each user belongs to exactly one org.

```
users
├── id
├── organization_id  → FK organizations
├── email          (unique per org)
├── password_hash  (never store plain password)
├── role           → used by RBAC (owner/admin/builder/viewer)
├── is_active
└── created_at
```

**Thinking:** `UniqueConstraint(organization_id, email)` — same email could exist in two companies in a real SaaS.

#### Table: `api_keys`

**Why:** Machines don't log in with passwords. They use long-lived keys with **scopes** (subset of permissions).

```
api_keys
├── id
├── organization_id  → FK organizations
├── name             (human label: "CI pipeline")
├── key_prefix       (mak_abc1 — for display)
├── key_hash         (SHA-256 of full key — never store full key)
├── scopes           (JSON list: ["mcp:invoke", "mcp:read"])
├── is_active
└── created_at
```

**Thinking:** On create, return full key **once**. After that, only hash exists — same pattern as GitHub/AWS keys.

### Step 2.3: `security.py`

**Functions and why:**

| Function | Purpose |
|----------|---------|
| `hash_password` / `verify_password` | bcrypt for users |
| `create_access_token` / `decode_access_token` | JWT with `sub`, `org_id`, `role`, `iss` |
| `generate_api_key` / `hash_api_key` | Create `mak_` keys, store hash only |
| `encrypt_secret` / `decrypt_secret` | Fernet for MCP credentials in DB |
| `hash_arguments` | Audit log — hash tool args, don't store PII |

### Step 2.4: `auth/context.py` — `AuthContext`

**Thinking:** After authentication, every route needs the same object:

```python
AuthContext(
    org_id=...,
    user_id=... or None,
    role=... or None,
    api_key_id=... or None,
    scopes=... or None,
)
```

Properties:
- `principal_type` → `"user"` or `"api_key"`
- `principal_id` → who to put in audit logs

### Step 2.5: `auth/deps.py` — `get_auth_context`

**Thinking:** One FastAPI dependency used on every protected route.

```
Request headers
    │
    ├─ X-API-Key: mak_...     → lookup api_keys by hash
    ├─ Authorization: Bearer mak_...  → same (API key)
    └─ Authorization: Bearer eyJ...   → decode JWT
                │
                ▼
          AuthContext or 401
```

### Step 2.6: `routes/auth.py`

**Endpoints built in this order:**

| Endpoint | Why now |
|----------|---------|
| `POST /v1/auth/signup` | Creates org + owner user in one transaction |
| `POST /v1/auth/login` | Returns JWT |
| `GET /v1/auth/me` | Verify auth pipeline works |
| `POST /v1/auth/api-keys` | Machine access (needs logged-in user with `api_key:write`) |

**Signup flow thinking:**
1. Check email not taken
2. Create `Organization`
3. Create `User` with `role=owner`
4. Return JWT immediately (no extra login step)

---

## Phase 3 — Authorization (what can you do?)

### Step 3.1: `rbac.py`

**Thinking:** Don't check `"is admin"` in every route. Map **roles → permissions**.

```
owner   → mcp:read, mcp:write, mcp:invoke, api_key:write, audit:read, ...
admin   → almost same as owner
builder → can build and invoke, no api_key:write
viewer  → read only
```

Permissions are strings like `mcp:invoke`. Routes call:

```python
require_permission(auth, "mcp:write")
```

**Two paths in `require_permission`:**
- JWT user → `has_permission(role, permission)`
- API key → `has_scope(scopes, permission)`

Same permission names for both — simpler mental model.

### Step 3.2: When to check what

| Layer | Question | Where |
|-------|----------|-------|
| L1 AuthN | Valid token/key? | `get_auth_context` |
| L2 Tenant | Same org? | Queries filter `organization_id == auth.org_id` |
| L3 RBAC | Role/scope allows action? | `require_permission` |
| L4 Tool policy | Tool on allowlist? | `ToolPolicyEvaluator` (later) |
| L5 Audit | Who did what? | `audit_invocation` (later) |

---

## Phase 4 — MCP connections (outbound client data)

### Step 4.1: Ask "what do we store about external MCP servers?"

Admins register connections: GitHub MCP, Grafana MCP, etc.

#### Table: `mcp_connections`

```
mcp_connections
├── id
├── organization_id     → tenant isolation
├── name                ("GitHub Prod")
├── base_url            (https://mcp.example.com)
├── auth_type           (bearer | api_key_header | oauth2 | oauth2_obo)
├── auth_config         (JSON: client_id, scopes, OAuth URLs)
├── auth_credentials_encrypted  (static secrets)
├── token_encrypted             (OAuth access token)
├── refresh_token_encrypted     (OAuth refresh)
├── token_expires_at
├── tool_allowlist      (JSON: ["search", "create_issue"] or [] = all)
├── discovered_tools    (cached from tools/list)
├── health_status       (healthy | unhealthy | unknown)
├── last_error
└── timestamps
```

**Thinking per auth type:**

| auth_type | Stored in | Used when calling MCP |
|-----------|-----------|------------------------|
| `bearer` | `auth_credentials_encrypted` | `Authorization: Bearer ...` |
| `api_key_header` | `auth_credentials_encrypted` as `Header:value` | Custom header |
| `oauth2` | `token_encrypted` + refresh | Bearer access token |
| `oauth2_obo` | exchange at runtime | Per-user downstream token |

### Step 4.2: `routes/connections.py` — CRUD

**Order of endpoints:**

1. `GET /v1/mcp-connections` — list (needs `mcp:read`)
2. `POST /v1/mcp-connections` — create (needs `mcp:write`, encrypt credentials)
3. `PATCH /{id}` — update
4. `DELETE /{id}` — remove
5. `POST /{id}/test` — call `tools/list`, cache `discovered_tools`

**Every query includes:**
```python
McpConnection.organization_id == auth.org_id
```

---

## Phase 5 — MCP client (outbound HTTP)

### Step 5.1: `mcp/client/http.py`

**Thinking:** MCP over HTTP is JSON-RPC 2.0.

```json
POST base_url
{ "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {} }
{ "jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": { "name": "...", "arguments": {} } }
```

**Classes:**
- `McpAuth` — auth_type + decrypted credentials
- `McpTool` — name, description, input_schema
- `McpHttpClient` — `_rpc()`, `list_tools()`, `call_tool()`

**`_headers()` thinking:** Switch on `auth_type` → build Authorization or custom header.

### Step 5.2: `mcp/client/discovery.py`

**Thinking:** Before OAuth, client must discover where to authenticate (RFC 9728).

```
GET {base_url}/.well-known/oauth-protected-resource
→ { "authorization_servers": ["https://auth.example.com"] }
```

### Step 5.3: `mcp/client/oauth.py`

**Thinking:** For `auth_type=oauth2` connections.

- `generate_pkce_pair()` — code_verifier + code_challenge (S256)
- `build_authorization_url()` — redirect user to login
- `exchange_authorization_code()` — code + verifier → tokens
- `refresh_access_token()` — new access token without re-login

Include `resource` parameter (RFC 8707) when requesting tokens.

### Step 5.4: `mcp/client/obo.py`

**Thinking:** For per-user delegation (`oauth2_obo`).

Two formats:
- **RFC 8693** — `grant_type=token-exchange`, `subject_token`, `audience`
- **Entra OBO** — `grant_type=jwt-bearer`, `assertion`, `requested_token_use=on_behalf_of`

Exposed via `POST /v1/mcp-connections/obo/exchange`.

### Step 5.5: `POST /v1/mcp-connections/{id}/invoke`

**Full outbound flow:**

```
1. require_permission(auth, "mcp:invoke")
2. Load connection (same org)
3. ToolPolicyEvaluator.can_invoke()  ← RBAC + allowlist
4. Build McpHttpClient from encrypted creds
5. client.call_tool(name, arguments)
6. audit_invocation(success|denied|error)
7. Return result
```

---

## Phase 6 — Policy & audit

### Step 6.1: Table `mcp_tool_invocations`

**Why:** Compliance and debugging — who called which tool?

```
mcp_tool_invocations
├── organization_id
├── connection_id (nullable for inbound)
├── tool_name
├── direction       (inbound | outbound)
├── principal_type  (user | api_key)
├── principal_id
├── status          (success | denied | error)
├── arguments_hash  (NOT raw args — may contain secrets)
├── error_message
├── latency_ms
└── created_at
```

### Step 6.2: `mcp/policy/evaluator.py`

**`ToolPolicyEvaluator.can_invoke()` checks:**

1. Permission: `mcp:invoke` (outbound) or `mcp:server:invoke` (inbound)
2. Tenant: `connection.organization_id == auth.org_id`
3. Allowlist: if `tool_allowlist` non-empty, tool must be listed

Raises `PolicyDenied` → route returns 403 + audit row with `status=denied`.

**`TimedInvocation`** — measure latency for audit.

### Step 6.3: `routes/audit.py`

`GET /v1/audit/invocations` — list recent calls (needs `audit:read`).

---

## Phase 7 — MCP server (inbound)

### Step 7.1: Ask "what if Cursor calls us?"

We become the **resource server**. External clients need:

1. Discovery metadata (RFC 9728)
2. JSON-RPC endpoint
3. Same auth as rest of API (JWT / API key)

### Step 7.2: Well-known routes

```
GET /.well-known/oauth-protected-resource
GET /.well-known/oauth-authorization-server
```

Implemented in `routes/mcp_server.py` + `mcp/server/handlers.py`.

Returns issuer, token endpoint, supported scopes/grants.

### Step 7.3: `POST /mcp` — JSON-RPC handler

**Methods handled:**

| Method | Permission | Action |
|--------|------------|--------|
| `initialize` | (auth required) | Return protocol version + capabilities |
| `tools/list` | `mcp:server:read` | Return built-in tools |
| `tools/call` | `mcp:server:invoke` | Execute tool + audit |

**Built-in tools (`handlers.py`):**
- `health_check` — liveness
- `whoami` — returns principal + org (proves auth works)
- `list_connections` — lists org's MCP connections

### Step 7.4: Inbound request flow

```
Client POST /mcp + Authorization: Bearer JWT
        │
        ▼
get_auth_context()           ← L1 AuthN
        │
        ▼
require_permission(...)      ← L3 RBAC
        │
        ▼
handle_tools_call(...)       ← business logic
        │
        ▼
audit_invocation(inbound)    ← L5 Audit
        │
        ▼
JSON-RPC response
```

### Step 7.5: Minimal OAuth token endpoint

`POST /v1/oauth/token` — stub for:
- `client_credentials`
- `token-exchange` (RFC 8693)

Full OAuth UI flow can be added later; JWT login covers dev/MVP.

---

## Phase 8 — Wire everything in `main.py`

**Router registration order:**

```python
app.include_router(well_known_router)           # no prefix
app.include_router(auth_router, prefix="/v1")
app.include_router(connections_router, prefix="/v1")
app.include_router(audit_router, prefix="/v1")
app.include_router(mcp_router)                    # POST /mcp
app.include_router(oauth_router, prefix="/v1")
```

---

## Phase 9 — Tests (prove each layer)

| Test file | What it proves |
|-----------|----------------|
| `test_api.py` | signup, JWT, well-known, inbound MCP, RBAC, allowlist |
| `test_obo.py` | RFC 8693 + Entra OBO exchange (mocked HTTP) |
| `conftest.py` | `init_db()` before tests |

---

## Complete request flows (reference)

### Flow A: User signs up and lists connections

```
POST /v1/auth/signup
  → INSERT organizations, users
  → RETURN JWT

GET /v1/mcp-connections
  → Header: Authorization: Bearer JWT
  → get_auth_context → AuthContext(org_id, user_id, role=owner)
  → require_permission(mcp:read) → OK for owner
  → SELECT * FROM mcp_connections WHERE organization_id = auth.org_id
```

### Flow B: API key invokes external MCP tool

```
POST /v1/mcp-connections/{id}/invoke
  → Header: X-API-Key: mak_...
  → get_auth_context → AuthContext(org_id, api_key_id, scopes=[...])
  → require_permission(mcp:invoke) → check scopes
  → ToolPolicyEvaluator → allowlist check
  → McpHttpClient.call_tool()
  → audit_invocation(outbound, success)
```

### Flow C: Cursor calls our MCP server

```
POST /mcp  { "method": "tools/call", "params": { "name": "whoami" } }
  → get_auth_context
  → require_permission(mcp:server:invoke)
  → handle_tools_call → returns principal info
  → audit_invocation(inbound, success)
```

---

## File → responsibility map

| File | One-line purpose |
|------|------------------|
| `config.py` | Environment settings |
| `security.py` | Hashing, JWT, encryption |
| `rbac.py` | Role → permission matrix |
| `auth/context.py` | Who is calling (dataclass) |
| `auth/deps.py` | FastAPI auth dependency |
| `db/models.py` | All SQLAlchemy tables |
| `db/session.py` | Engine + get_session + init_db |
| `mcp/client/http.py` | Outbound MCP JSON-RPC |
| `mcp/client/oauth.py` | OAuth PKCE + refresh |
| `mcp/client/obo.py` | Token exchange |
| `mcp/client/discovery.py` | RFC 9728 fetch |
| `mcp/server/handlers.py` | Inbound tool definitions + logic |
| `mcp/policy/evaluator.py` | Allowlist + audit |
| `routes/auth.py` | Signup, login, API keys |
| `routes/connections.py` | MCP connection CRUD + invoke + OBO |
| `routes/mcp_server.py` | POST /mcp + well-known |
| `routes/audit.py` | Invocation history |
| `main.py` | App assembly |

---

## If you rebuild from scratch — recommended order

```
 1. config + main.py + /health
 2. db/models: Organization, User
 3. security.py: passwords + JWT
 4. auth routes: signup, login
 5. AuthContext + get_auth_context
 6. rbac.py + require_permission
 7. ApiKey model + api-keys route
 8. McpConnection model + CRUD routes
 9. McpHttpClient + test connection
10. ToolPolicyEvaluator + McpToolInvocation + audit route
11. POST /mcp inbound server + well-known
12. oauth.py + obo.py + obo/exchange endpoint
13. invoke endpoint with full policy chain
14. tests for each layer
```

---

## Design principles used

1. **Tenant first** — every table has `organization_id`; every query filters by it.
2. **Never store secrets plain** — passwords hashed, API keys hashed, MCP creds encrypted.
3. **One auth dependency** — `get_auth_context` everywhere.
4. **Permissions as strings** — same names for RBAC roles and API key scopes.
5. **Policy at invoke time** — not just at config time (allowlist enforced when tool runs).
6. **Audit everything sensitive** — tool calls logged with hash, not raw arguments.
7. **MCP spec alignment** — JSON-RPC, RFC 9728 metadata, OBO/RFC 8693 for enterprise.

---

*This guide matches the implementation in `MCP_AuthN_AuthZ/` as of v0.1.0.*
