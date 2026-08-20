# MCP Client & Server — Authentication, Authorization & RBAC

**A beginner-friendly guide to every concept used in building secure MCP backends.**

> PDF version: [mcp_auth_rbac_concepts_guide.pdf](./mcp_auth_rbac_concepts_guide.pdf)

---

## Part 1: MCP Basics

### What is MCP (Model Context Protocol)?

MCP is an open standard that lets AI applications (chatbots, agents) connect to external tools and data sources in a consistent way.

**Analogy:** MCP is like USB-C for AI tools. Before USB-C, every device had a different charger. MCP gives AI apps one standard way to discover and use tools.

### MCP Client vs MCP Server

| Role | Who | What they do |
|------|-----|--------------|
| **MCP Client** | The AI application | Asks "what tools do you have?" and "please run this tool" |
| **MCP Server** | The tool provider | Answers with tool list and executes tools when asked |

**In your Orchestrator platform:**
- **Outbound:** Orchestrator is the MCP **Client** — connects to external servers (GitHub, Linear, etc.)
- **Inbound:** Orchestrator can **be** the MCP Server — exposes agents/workflows as tools to Cursor and other clients

### What is a Tool?

A callable function with:
- **name** — e.g. `create_issue`
- **description** — helps the AI decide when to use it
- **input schema** — what arguments it accepts (JSON Schema)

### JSON-RPC — How MCP Messages Work

MCP uses JSON-RPC 2.0. Every message is JSON:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

**Key methods:**
- `tools/list` — discover available tools
- `tools/call` — execute a tool with arguments

### HTTP Transport (Streamable HTTP)

Remote MCP servers communicate over HTTP POST with JSON bodies. "Streamable HTTP" supports streaming for long operations.

```
POST /mcp
Content-Type: application/json
Authorization: Bearer <token>
```

---

## Part 2: Authentication vs Authorization

| | Authentication (AuthN) | Authorization (AuthZ) |
|---|------------------------|------------------------|
| **Question** | Who are you? | What can you do? |
| **When** | First (at login) | After identity is known |
| **Example** | Email + password → JWT | Can this Builder delete an agent? |

**Analogy:**
- **Authentication** = showing your ID at a building entrance
- **Authorization** = your employee badge deciding which floors you can access

---

## Part 3: Authentication Methods

### JWT (JSON Web Token)

A signed string containing user info (user ID, org ID, role). Sent as:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

- Signed with a secret — tampering is detected
- Has expiry (`exp`) — tokens expire automatically
- Used for dashboard users after login

**Example payload (decoded):**
```json
{
  "sub": "user-uuid",
  "org_id": "org-uuid",
  "role": "builder",
  "exp": 1724000000
}
```

### API Keys

Long random strings for machine-to-machine access.

- Format in Orchestrator: `oak_<prefix>_<secret>`
- Stored as **hashes** in the database (never plain text)
- Can have scopes, rate limits, and expiry

**Analogy:** A hotel key card for a cleaning robot — works 24/7 without human login, but only opens specific doors.

### Bearer Tokens

Any secret sent as `Authorization: Bearer <token>`. Both JWTs and OAuth access tokens use this format.

> Whoever **bears** (holds) the token gets access. Keep it secret!

### OAuth 2.1 — Industry Standard for MCP

OAuth 2.1 lets a user grant an app access to a service **without sharing their password**.

**Four roles:**

| Role | Example |
|------|---------|
| **Resource Owner** | The human user |
| **Client** | Orchestrator MCP client |
| **Authorization Server (AS)** | Keycloak, Auth0, Entra ID |
| **Resource Server (RS)** | The MCP server (e.g. GitHub MCP) |

**Authorization Code Flow (with PKCE):**

1. Client discovers auth server from MCP metadata (RFC 9728)
2. Client redirects user to login page
3. User approves permissions (scopes)
4. Auth server returns a short-lived authorization code
5. Client exchanges code for access token + refresh token
6. Client calls MCP server: `Authorization: Bearer <access_token>`

### PKCE (Proof Key for Code Exchange)

Prevents attackers from stealing authorization codes.

1. Client generates random `code_verifier`
2. Sends hashed `code_challenge` to auth server
3. When exchanging code, client must prove it has the original verifier

**Mandatory in MCP OAuth flows.**

**Analogy:** A two-part ticket — you need both halves to collect your prize.

### Refresh Tokens

Access tokens expire quickly (e.g. 1 hour). Refresh tokens get new access tokens without re-login.

### Client Credentials (Machine-to-Machine)

Client authenticates with `client_id` + `client_secret` directly — no human user. For background workers.

---

## Part 4: OBO (On-Behalf-Of) Token Exchange

### What is OBO?

**OBO (On-Behalf-Of)** is a delegation pattern where a **middle-tier service** (like Orchestrator or an MCP server) receives a **user's access token**, then **exchanges it** for a **new token** scoped to a **downstream API** — while still acting **as that user**.

The downstream service sees: *"User Alice is calling, via Service Orchestrator."*

**Analogy:** A receptionist does not use their own master key. They take your ID, get a **temporary pass in your name**, and escort you to the right room. The room's security log shows **you**, not the receptionist.

### OBO vs What Orchestrator Uses Today

| | **Current (Orchestrator)** | **OBO / Token Exchange** |
|---|---------------------------|--------------------------|
| **Who is authenticated?** | The **organization** (shared credentials) | The **individual user** |
| **Token owner** | Admin-configured MCP connection token | User's identity propagated downstream |
| **Permissions** | Whatever the shared token allows | User's own scopes (e.g. only their GitHub repos) |
| **Flow** | Store token → pass directly to MCP | Receive user token → exchange → new downstream token |
| **Use case** | Org-wide shared MCP connection | Per-user access to GitHub, Graph, Slack, etc. |
| **In codebase today?** | Yes (`bearer`, `api_key_header`) | Not yet — planned for per-user delegation |

> **Short answer:** OBO is **not** the same as your current bearer/API-key approach. Your current model is correct for **org-level** connections. OBO is needed when each user must call downstream APIs **with their own identity and permissions**.

### When You Need OBO

**You do NOT need OBO if:**
- One org-wide MCP connection is enough (shared bot/service account)
- All builders share the same external tool permissions
- Direct OAuth with stored refresh tokens per connection is sufficient

**You DO need OBO if:**
- Each user calls GitHub, Microsoft Graph, or Slack **with their own account**
- Downstream APIs must enforce **per-user** permissions and audit trails
- You have a chain: **User → Orchestrator → MCP Server → Downstream API**
- Compliance requires: *"User Alice invoked tool X"* with **her** identity downstream

### OBO Flow (Step by Step)

```
1. User logs into Client (e.g. Cursor, dashboard)
2. Client sends request to Middle-tier (Orchestrator MCP server)
   → Authorization: Bearer <user-token>   (audience = Orchestrator)
3. Middle-tier needs to call Downstream API (e.g. Microsoft Graph)
4. Middle-tier calls Auth Server with OBO / Token Exchange:
   → "Give me a token for Graph, on behalf of this user"
5. Auth Server returns new access token
   → audience = Graph, subject = User
6. Middle-tier calls Downstream API with the new token
7. Downstream API enforces User's own permissions
```

### OBO Chain Through MCP (Real-World Example)

```
User (Entra ID login)
  → Cursor MCP Client
    → Orchestrator MCP Server  (validates user token, aud = Orchestrator)
      → Token Exchange / OBO
        → Microsoft Graph API  (token aud = Graph, sub = User)
```

**Critical rule:** Never pass the user's token straight through to downstream APIs. The MCP server must **mint a new token** for each downstream service via OBO. Tokens are **audience-bound** (RFC 8707) — a token issued for Orchestrator cannot be used at Graph.

### Standards Behind OBO

| Standard | Name | Role |
|----------|------|------|
| **RFC 8693** | OAuth 2.0 Token Exchange | Generic standard for exchanging one token for another |
| **RFC 7523** | JWT Bearer Grant | Used by Microsoft Entra OBO under the hood |
| **Microsoft OBO** | On-Behalf-Of Flow | Entra-specific implementation of delegation |
| **RFC 8707** | Resource Indicators | Binds exchanged token to specific downstream URL |

Same **intent** (user token in → new audience-bound token out), different wire format per identity provider.

### Microsoft Entra OBO Request Format

Used when Orchestrator (registered as an Entra app) calls Microsoft Graph on behalf of a user:

```http
POST https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token
Content-Type: application/x-www-form-urlencoded

grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer
client_id=<orchestrator-app-client-id>
client_secret=<orchestrator-app-secret>
assertion=<user-access-token-issued-TO-orchestrator>
scope=https://graph.microsoft.com/User.Read
requested_token_use=on_behalf_of
```

**Key parameters:**

| Parameter | Meaning |
|-----------|---------|
| `grant_type` | `jwt-bearer` — presenting a JWT as proof |
| `assertion` | The user's token that was issued **to Orchestrator** (check `aud` claim) |
| `scope` | Permissions needed on the **downstream** API (Graph) |
| `requested_token_use` | Must be `on_behalf_of` for Entra OBO |

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "https://graph.microsoft.com/User.Read"
}
```

### RFC 8693 Token Exchange Format (Generic / IdP-agnostic)

Used by AWS Cognito, Keycloak, Okta, and other providers that support standard token exchange:

```http
POST https://auth.example.com/token
Content-Type: application/x-www-form-urlencoded

grant_type=urn:ietf:params:oauth:grant-type:token-exchange
client_id=<middle-tier-client-id>
client_secret=<middle-tier-secret>
subject_token=<user-access-token>
subject_token_type=urn:ietf:params:oauth:token-type:access_token
audience=https://downstream-api.example.com
scope=read:issues write:issues
```

**Key parameters:**

| Parameter | Meaning |
|-----------|---------|
| `grant_type` | `token-exchange` — RFC 8693 grant |
| `subject_token` | Token representing the **user** (who we act on behalf of) |
| `subject_token_type` | Format of the subject token (usually access_token) |
| `audience` | The **downstream** resource the new token is for |
| `actor_token` | *(Optional)* Token for the middle-tier service itself (delegation chain) |

**Response:**
```json
{
  "access_token": "eyJ...",
  "issued_token_type": "urn:ietf:params:oauth:token-type:access_token",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

### OBO vs Direct Bearer (Side-by-Side)

**Direct Bearer (what Orchestrator does today for MCP outbound):**
```
Orchestrator ──[org-level bearer token]──► External MCP Server
              (same token for all users in the org)
```

**OBO / Token Exchange (per-user delegation):**
```
User ──[user token]──► Orchestrator ──[OBO exchange]──► Auth Server
                                              │
                                              ▼
                                    [user-scoped downstream token]
                                              │
                                              ▼
                                        External API / MCP
                              (permissions = this user's scopes only)
```

### Token Claims in OBO Tokens

Exchanged tokens often carry delegation metadata so downstream APIs know **who** acted and **via whom**:

| Claim | Meaning |
|-------|---------|
| `sub` | The user (subject) — who the action is on behalf of |
| `aud` | The downstream API this token is valid for |
| `scp` / `scope` | Permissions granted for this downstream call |
| `act` (RFC 8693) | The middle-tier service acting on behalf of `sub` |
| `azp` (Entra) | Authorized party — Entra's equivalent of the acting app |

### OBO in Orchestrator Architecture (Planned)

When implemented, OBO would fit into the backend like this:

| Component | Responsibility |
|-----------|----------------|
| `packages/mcp/client/oauth.py` | Perform token exchange before `tools/call` |
| `packages/mcp/server/auth.py` | Accept user token inbound; trigger OBO for downstream |
| `McpConnection.auth_type` | New value: `oauth2_obo` for per-user delegation connections |
| Audit log | Record both `user_id` (subject) and `connection_id` (actor) |

**Proposed auth types on `McpConnection`:**

| `auth_type` | Delegation model |
|-------------|-----------------|
| `none` | No auth (dev only) |
| `bearer` | Org-level static token (current) |
| `api_key_header` | Org-level custom header (current) |
| `oauth2` | Org-level OAuth with stored refresh token (planned) |
| `oauth2_obo` | Per-user token exchange on each tool call (planned) |

### Security Rules for OBO

1. **Validate `aud` on every token** — only accept tokens issued for your app
2. **Never pass tokens through** — always exchange for a new downstream-scoped token
3. **Use least-privilege scopes** — request only the downstream permissions needed for the tool
4. **Bind tokens to resource** — include RFC 8707 `resource` / `audience` parameter
5. **Audit both identities** — log the user (subject) and the service (actor) on every call
6. **Short-lived tokens** — exchanged tokens should have minimal TTL

---

## Part 5: Industry RFC Standards

### RFC 9728 — Protected Resource Metadata

Every MCP server MUST expose:

```
GET /.well-known/oauth-protected-resource
```

```json
{
  "resource": "https://mcp.example.com",
  "authorization_servers": ["https://auth.example.com"]
}
```

Tells clients: "To access me, authenticate at these authorization servers."

### RFC 8414 — Authorization Server Metadata

Auth server publishes its endpoints:
- `authorization_endpoint` — login page URL
- `token_endpoint` — exchange code for token
- Supported grant types

### RFC 8707 — Resource Indicators (Critical Security)

Client MUST include `resource` parameter = MCP server URL when requesting tokens.

**Why:** Binds token to ONE specific server. Prevents fake MCP servers from stealing tokens.

**Analogy:** Writing the delivery address on a package — token can only be used at that exact address.

### RFC 7591 — Dynamic Client Registration

Optional: clients auto-register with auth server to get a `client_id` without manual setup.

### RFC 8693 — OAuth 2.0 Token Exchange (OBO Standard)

Defines how a service exchanges an inbound token for a new token scoped to a different downstream resource. This is the **generic standard** behind OBO delegation.

- `grant_type`: `urn:ietf:params:oauth:grant-type:token-exchange`
- `subject_token`: the user's token (who we act on behalf of)
- `audience`: the downstream API the new token targets
- `act` claim in issued token: identifies the middle-tier service

See **Part 4** for full OBO request/response examples.

| RFC | Name | Purpose |
|-----|------|---------|
| 9728 | Protected Resource Metadata | Find auth server from MCP URL |
| 8414 | AS Metadata | Find OAuth endpoints |
| 8707 | Resource Indicators | Bind token to one server |
| 7591 | Dynamic Registration | Auto-register OAuth client |
| 8693 | Token Exchange (OBO) | Exchange user token for downstream token |

---

## Part 6: RBAC (Role-Based Access Control)

### What is RBAC?

Assign permissions to **roles**, roles to **users**. Easier than managing 50 permissions per person.

**Analogy:** Job titles in a company. "Manager" can approve expenses; "Intern" cannot.

### Roles in Orchestrator

| Role | Level | Typical use |
|------|-------|-------------|
| `owner` | Highest | Org creator, full control |
| `admin` | High | Manage users and settings |
| `builder` | Medium | Create agents, workflows, MCP |
| `viewer` | Low | Read-only |

### Permissions

Fine-grained action strings checked in code:

| Permission | Meaning |
|------------|---------|
| `mcp:read` | View MCP connections and tools |
| `mcp:write` | Create/update/delete connections |
| `mcp:invoke` | Call MCP tools at runtime |
| `agent:invoke` | Run an agent |
| `api_key:write` | Create API keys |

### Scopes (for API Keys)

API key equivalent of permissions. A key with only `agent:invoke` cannot manage MCP connections.

### Multi-Tenancy (Organization Isolation)

Every resource has `org_id`. User in Org A can never access Org B's data — even when authenticated.

---

## Part 7: Tool Policies & Security

### Tool Allowlist

List of permitted tool names. If set, only those tools can be called. Prevents agents from using dangerous tools like `delete_database`.

### 5-Layer Security Model

| Layer | Check |
|-------|-------|
| 1. Transport Auth | Valid JWT, API key, or OAuth token? |
| 2. Tenant Isolation | Resource belongs to user's org? |
| 3. RBAC | Role has required permission? |
| 4. Tool Policy | Tool on allowlist and bound to agent? |
| 5. Audit Log | Record who called what, when, result |

### Audit Logging

Log every MCP tool invocation: principal, tool name, connection, success/failure, latency. Do NOT log raw arguments if they contain PII — use a hash.

### Encryption at Rest

OAuth tokens and MCP credentials encrypted (Fernet) before database storage. Encryption key in environment variables.

---

## Part 8: How Everything Fits Together

### Outbound: Orchestrator → External MCP (Org-Level — Current)

```
1. Admin creates MCP connection (URL + auth)
2. OAuth login OR static bearer token stored encrypted
3. Test: tools/list → discover tools
4. Builder binds tools to agent
5. Runtime: agent calls tools/call with org-level token
6. Policy: RBAC + allowlist + audit
```

### Outbound with OBO: Orchestrator → External API (Per-User — Planned)

```
1. User logs in and their token reaches Orchestrator
2. Agent triggers MCP tool that needs downstream API (e.g. Graph)
3. Orchestrator exchanges user token via OBO (RFC 8693 / Entra OBO)
4. Orchestrator calls downstream API with user-scoped token
5. Audit: log user (subject) + service (actor) + tool + result
```

### Inbound: External Client → Orchestrator MCP

```
1. Client reads /.well-known/oauth-protected-resource
2. User authenticates (OAuth or API key)
3. Client calls tools/list
4. Client calls tools/call (e.g. invoke_agent)
5. Orchestrator validates token, checks RBAC, executes
```

### Inbound with OBO Chain: User → Orchestrator → Downstream

```
1. User (Entra ID) → Cursor → Orchestrator MCP server
2. Orchestrator validates user token (aud = Orchestrator)
3. Tool needs Microsoft Graph → Orchestrator does OBO exchange
4. Graph receives user-scoped token (aud = Graph, sub = User)
5. Graph enforces User's own permissions and Conditional Access
```

---

## Glossary

| Term | Definition |
|------|------------|
| **MCP** | Model Context Protocol — AI tool integration standard |
| **Client** | App that requests and calls tools |
| **Server** | System that exposes and runs tools |
| **JSON-RPC** | Message format for remote method calls |
| **OAuth 2.1** | Standard for delegated authorization |
| **PKCE** | Security extension preventing code interception |
| **JWT** | Signed token with user identity and role |
| **API Key** | Long-lived secret for machine access |
| **RBAC** | Permissions assigned via roles |
| **Scope** | Permission on API key or OAuth token |
| **Allowlist** | Explicit list of permitted tools |
| **Tenant** | One organization's isolated data space |
| **AS** | Authorization Server — issues tokens |
| **RS** | Resource Server — accepts tokens (MCP server) |
| **RFC 9728** | MCP server discovery document |
| **RFC 8707** | Binds OAuth token to specific server URL |
| **RFC 8693** | OAuth Token Exchange — generic OBO standard |
| **OBO** | On-Behalf-Of — exchange user token for downstream-scoped token |
| **Token Exchange** | RFC 8693 mechanism; same intent as OBO, IdP-agnostic format |
| **Subject token** | The user's token presented in an OBO exchange |
| **Actor** | The middle-tier service acting on behalf of the user |
| `act` claim | RFC 8693 claim identifying the acting service in a delegated token |
| `oauth2_obo` | Planned Orchestrator auth type for per-user delegation connections |

---

*Orchestrator Platform — Backend Concepts Guide*
