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

## Part 4: Industry RFC Standards

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

| RFC | Name | Purpose |
|-----|------|---------|
| 9728 | Protected Resource Metadata | Find auth server from MCP URL |
| 8414 | AS Metadata | Find OAuth endpoints |
| 8707 | Resource Indicators | Bind token to one server |
| 7591 | Dynamic Registration | Auto-register OAuth client |

---

## Part 5: RBAC (Role-Based Access Control)

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

## Part 6: Tool Policies & Security

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

## Part 7: How Everything Fits Together

### Outbound: Orchestrator → External MCP

```
1. Admin creates MCP connection (URL + auth)
2. OAuth login OR static token stored encrypted
3. Test: tools/list → discover tools
4. Builder binds tools to agent
5. Runtime: agent calls tools/call
6. Policy: RBAC + allowlist + audit
```

### Inbound: External Client → Orchestrator MCP

```
1. Client reads /.well-known/oauth-protected-resource
2. User authenticates (OAuth or API key)
3. Client calls tools/list
4. Client calls tools/call (e.g. invoke_agent)
5. Orchestrator validates token, checks RBAC, executes
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

---

*Orchestrator Platform — Backend Concepts Guide*
