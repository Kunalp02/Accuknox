#!/usr/bin/env python3
"""Generate MCP Auth & RBAC concepts PDF."""

from fpdf import FPDF


class ConceptsPDF(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(100, 100, 100)
            self.cell(0, 8, "MCP Authentication, Authorization & RBAC - Concepts Guide", align="C")
            self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

    def cover(self):
        self.add_page()
        self.set_font("Helvetica", "B", 24)
        self.set_text_color(20, 60, 120)
        self.ln(40)
        self.multi_cell(0, 12, "MCP Client & Server\nAuthentication, Authorization & RBAC", align="C")
        self.ln(10)
        self.set_font("Helvetica", "", 14)
        self.set_text_color(60, 60, 60)
        self.multi_cell(0, 8, "A beginner-friendly guide to every concept\nused in building secure MCP backends", align="C")
        self.ln(20)
        self.set_font("Helvetica", "", 11)
        self.multi_cell(0, 7, "Covers: MCP protocol, OAuth 2.1, OBO token exchange,\nJWT, API keys, RBAC, RFC standards, and how they fit together.", align="C")
        self.ln(30)
        self.set_font("Helvetica", "I", 10)
        self.cell(0, 8, "Orchestrator Platform - Backend Concepts", align="C")

    def part_title(self, title: str):
        self.add_page()
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(20, 60, 120)
        self.cell(0, 12, title)
        self.ln(14)

    def section(self, title: str):
        self.ln(4)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 8, title)
        self.ln(2)

    def subsection(self, title: str):
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 7, title)
        self.ln(1)

    def body(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def bullet(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        x = self.get_x()
        self.cell(6, 5.5, "-")
        self.multi_cell(0, 5.5, text)
        self.set_x(x)
        self.ln(1)

    def example_box(self, title: str, text: str):
        self.ln(2)
        self.set_fill_color(245, 248, 252)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(20, 60, 120)
        self.cell(0, 7, f"  Example: {title}", ln=True, fill=True)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 5, f"  {text}", fill=True)
        self.ln(3)

    def analogy_box(self, text: str):
        self.ln(1)
        self.set_fill_color(255, 250, 235)
        self.set_font("Helvetica", "I", 10)
        self.set_text_color(80, 60, 20)
        self.multi_cell(0, 5.5, f"Analogy: {text}", fill=True)
        self.ln(3)

    def table_simple(self, headers: list[str], rows: list[list[str]]):
        col_w = (self.w - 2 * self.l_margin) / len(headers)
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(230, 235, 245)
        for h in headers:
            self.cell(col_w, 7, h, border=1, fill=True)
        self.ln()
        self.set_font("Helvetica", "", 9)
        self.set_fill_color(255, 255, 255)
        for row in rows:
            for cell in row:
                self.cell(col_w, 7, cell[:40], border=1)
            self.ln()
        self.ln(3)


def build_pdf(path: str) -> None:
    pdf = ConceptsPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.cover()

    # PART 1 - MCP BASICS
    pdf.part_title("Part 1: MCP Basics")

    pdf.section("What is MCP (Model Context Protocol)?")
    pdf.body(
        "MCP is an open standard that lets AI applications (like chatbots and agents) "
        "connect to external tools and data sources in a consistent way. Think of it as "
        "a universal plug that lets an AI assistant use Gmail, GitHub, databases, or your "
        "own backend APIs without custom integration code for each one."
    )
    pdf.analogy_box(
        "MCP is like USB-C for AI tools. Before USB-C, every device had a different charger. "
        "MCP gives AI apps one standard way to discover and use tools."
    )

    pdf.section("MCP Client vs MCP Server")
    pdf.body("In every MCP interaction there are two sides:")
    pdf.bullet("MCP Client - The AI application that WANTS to use tools. It asks: 'What tools do you have?' and 'Please run this tool.'")
    pdf.bullet("MCP Server - The system that PROVIDES tools. It answers: 'Here are my tools' and executes them when asked.")
    pdf.example_box(
        "In your Orchestrator platform",
        "OUTBOUND: Orchestrator is the MCP Client. It connects to external MCP servers (e.g. GitHub MCP) to use their tools.\n"
        "INBOUND: Orchestrator can also BE an MCP Server, exposing its own agents and workflows as tools to external clients like Cursor."
    )

    pdf.section("What is a Tool in MCP?")
    pdf.body(
        "A tool is a callable function exposed by an MCP server. Each tool has a name, "
        "a description (so the AI knows when to use it), and an input schema (what "
        "arguments it accepts). The AI reads tool descriptions and decides which tool to call."
    )
    pdf.example_box(
        "GitHub MCP tool",
        "Tool name: create_issue\nDescription: Create a new GitHub issue\nInput: { repo: string, title: string, body: string }"
    )

    pdf.section("JSON-RPC - How MCP Messages Work")
    pdf.body(
        "MCP uses JSON-RPC 2.0, a simple message format for remote procedure calls. "
        "Every request is a JSON object with: jsonrpc (always '2.0'), id (request number), "
        "method (what to do), and params (arguments). The server responds with result or error."
    )
    pdf.example_box(
        "tools/list request",
        '{ "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {} }'
    )
    pdf.example_box(
        "tools/call request",
        '{ "jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": { "name": "search", "arguments": { "query": "hello" } } }'
    )

    pdf.section("HTTP Transport (Streamable HTTP)")
    pdf.body(
        "Remote MCP servers communicate over HTTP. The client sends JSON-RPC messages via "
        "POST requests. 'Streamable HTTP' is the modern transport that supports streaming "
        "responses for long-running operations. This is how SaaS MCP servers work over the internet."
    )
    pdf.bullet("POST /mcp - Main endpoint for JSON-RPC messages")
    pdf.bullet("Content-Type: application/json")
    pdf.bullet("Authorization: Bearer <token> - When auth is required")

    # PART 2 - AUTH VS AUTHZ
    pdf.part_title("Part 2: Authentication vs Authorization")

    pdf.section("Authentication (AuthN) - WHO are you?")
    pdf.body(
        "Authentication verifies identity. It answers: 'Are you really who you claim to be?' "
        "Common methods: username/password login, API keys, OAuth tokens, JWT tokens."
    )
    pdf.analogy_box(
        "Authentication is showing your ID card at a building entrance. The guard checks "
        "that the ID is real and belongs to you."
    )

    pdf.section("Authorization (AuthZ) - WHAT can you do?")
    pdf.body(
        "Authorization happens AFTER authentication. It checks whether an authenticated "
        "user is allowed to perform a specific action on a specific resource."
    )
    pdf.analogy_box(
        "Authorization is your employee badge determining which floors you can access. "
        "Your ID proves who you are; your badge level decides what you can do."
    )

    pdf.table_simple(
        ["Concept", "Question", "Example"],
        [
            ["Authentication", "Who are you?", "Login with email/password"],
            ["Authorization", "What can you do?", "Can you delete this agent?"],
            ["RBAC", "What is your role?", "Builder can edit, Viewer cannot"],
        ],
    )

    # PART 3 - AUTH METHODS
    pdf.part_title("Part 3: Authentication Methods")

    pdf.section("JWT (JSON Web Token)")
    pdf.body(
        "A JWT is a signed string that contains user information (claims) like user ID, "
        "organization ID, and role. After login, the server gives the client a JWT. "
        "The client sends it in every request: Authorization: Bearer <jwt>. "
        "The server verifies the signature - no database lookup needed for basic checks."
    )
    pdf.bullet("Signed with a secret key - tampering is detected")
    pdf.bullet("Contains expiry (exp) - tokens expire automatically")
    pdf.bullet("Used for dashboard users in Orchestrator")
    pdf.example_box(
        "JWT payload (decoded)",
        '{ "sub": "user-uuid", "org_id": "org-uuid", "role": "builder", "exp": 1724000000 }'
    )

    pdf.section("API Keys")
    pdf.body(
        "API keys are long random strings for machine-to-machine access. Unlike JWTs from "
        "login, API keys are created by admins and given to scripts, workers, or external "
        "services. They are stored as hashes in the database (never plain text)."
    )
    pdf.bullet("Format in Orchestrator: oak_<prefix>_<secret>")
    pdf.bullet("Can have scopes (permissions) and resource limits")
    pdf.bullet("Can have rate limits and expiry dates")
    pdf.analogy_box(
        "API keys are like a hotel key card given to a cleaning robot. It works 24/7 "
        "without a human logging in, but only opens specific doors."
    )

    pdf.section("Bearer Tokens")
    pdf.body(
        "A Bearer token is any secret sent in the HTTP Authorization header as "
        "'Authorization: Bearer <token>'. Both JWTs and OAuth access tokens use this format. "
        "Whoever bears (holds) the token gets access - so keep it secret!"
    )

    pdf.section("OAuth 2.1 - Industry Standard for MCP")
    pdf.body(
        "OAuth 2.1 is the authorization framework required by the MCP specification for "
        "remote (HTTP) servers. It lets a user grant an application access to a service "
        "WITHOUT sharing their password. The user logs in at the real service (e.g. Google), "
        "approves access, and the app gets a limited access token."
    )
    pdf.subsection("Key OAuth Roles")
    pdf.bullet("Resource Owner - The human user who owns the data")
    pdf.bullet("Client - The app wanting access (e.g. Orchestrator MCP client)")
    pdf.bullet("Authorization Server (AS) - Issues tokens after login (e.g. Keycloak, Auth0)")
    pdf.bullet("Resource Server (RS) - The API/MCP server that accepts tokens (e.g. GitHub MCP)")

    pdf.subsection("Authorization Code Flow (with PKCE)")
    pdf.body("The standard flow for MCP clients connecting to remote servers:")
    pdf.bullet("1. Client discovers auth server URL from MCP server metadata")
    pdf.bullet("2. Client redirects user to login page (Authorization Server)")
    pdf.bullet("3. User logs in and approves requested permissions (scopes)")
    pdf.bullet("4. Auth server redirects back with a short-lived authorization code")
    pdf.bullet("5. Client exchanges code for access token (+ refresh token)")
    pdf.bullet("6. Client calls MCP server with: Authorization: Bearer <access_token>")

    pdf.section("PKCE (Proof Key for Code Exchange)")
    pdf.body(
        "PKCE (pronounced 'pixie') prevents attackers from stealing authorization codes. "
        "Before redirecting the user to login, the client generates a random 'code_verifier' "
        "and sends a hashed version ('code_challenge') to the auth server. When exchanging "
        "the code for a token, the client must prove it has the original verifier. "
        "PKCE is MANDATORY in MCP OAuth flows."
    )
    pdf.analogy_box(
        "PKCE is like a two-part ticket. You get half at the start and must show both "
        "halves to collect your prize. An attacker who steals only one half cannot win."
    )

    pdf.section("Refresh Tokens")
    pdf.body(
        "Access tokens expire quickly (e.g. 1 hour) for security. A refresh token is a "
        "longer-lived secret used to get new access tokens without making the user log in "
        "again. The MCP client should automatically refresh before calling tools."
    )

    pdf.section("Client Credentials Grant (Machine-to-Machine)")
    pdf.body(
        "For server-to-server communication (no human user), the client authenticates "
        "directly with client_id + client_secret to get a token. Useful for background "
        "workers calling MCP servers. Support in MCP spec is evolving."
    )

    # PART 4 - OBO
    pdf.part_title("Part 4: OBO (On-Behalf-Of) Token Exchange")

    pdf.section("What is OBO?")
    pdf.body(
        "OBO (On-Behalf-Of) is a delegation pattern where a middle-tier service (like "
        "Orchestrator or an MCP server) receives a user's access token, then exchanges it "
        "for a new token scoped to a downstream API - while still acting as that user. "
        "The downstream service sees: User Alice is calling, via Service Orchestrator."
    )
    pdf.analogy_box(
        "A receptionist does not use their own master key. They take your ID, get a "
        "temporary pass in your name, and escort you to the right room."
    )

    pdf.section("OBO vs What Orchestrator Uses Today")
    pdf.table_simple(
        ["Aspect", "Current", "OBO"],
        [
            ["Authenticated as", "Organization", "Individual user"],
            ["Token", "Shared org credentials", "User identity downstream"],
            ["In codebase?", "Yes (bearer/api_key)", "Not yet - planned"],
        ],
    )
    pdf.body(
        "Short answer: OBO is NOT the same as your current bearer/API-key approach. "
        "Current model is correct for org-level connections. OBO is needed when each "
        "user must call downstream APIs with their own identity and permissions."
    )

    pdf.section("When You Need OBO")
    pdf.bullet("DO need: each user calls GitHub/Graph with their own account")
    pdf.bullet("DO need: downstream enforces per-user permissions and audit")
    pdf.bullet("DO need: chain User -> Orchestrator -> MCP -> Downstream API")
    pdf.bullet("DO NOT need: one shared org-wide MCP connection is enough")

    pdf.section("OBO Flow (Step by Step)")
    pdf.bullet("1. User logs in; client sends user token to Orchestrator (aud=Orchestrator)")
    pdf.bullet("2. Orchestrator needs downstream API (e.g. Microsoft Graph)")
    pdf.bullet("3. Orchestrator calls Auth Server: exchange token on behalf of user")
    pdf.bullet("4. Auth Server returns new token (aud=Graph, sub=User)")
    pdf.bullet("5. Orchestrator calls downstream with user-scoped token")
    pdf.bullet("6. Never pass user token through - always exchange for new token")

    pdf.section("Microsoft Entra OBO Request Format")
    pdf.example_box(
        "Entra OBO token request",
        "POST /oauth2/v2.0/token\n"
        "grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer\n"
        "client_id=<orchestrator-app-id>\n"
        "client_secret=<secret>\n"
        "assertion=<user-token-issued-TO-orchestrator>\n"
        "scope=https://graph.microsoft.com/User.Read\n"
        "requested_token_use=on_behalf_of"
    )

    pdf.section("RFC 8693 Token Exchange Format (Generic)")
    pdf.example_box(
        "RFC 8693 token exchange",
        "POST /token\n"
        "grant_type=urn:ietf:params:oauth:grant-type:token-exchange\n"
        "subject_token=<user-access-token>\n"
        "subject_token_type=urn:ietf:params:oauth:token-type:access_token\n"
        "audience=https://downstream-api.example.com\n"
        "scope=read:issues write:issues"
    )

    pdf.section("OBO vs Direct Bearer")
    pdf.body(
        "Direct Bearer (current): Orchestrator sends org-level token to MCP - same for all users.\n"
        "OBO (planned): User token -> Orchestrator exchanges -> user-scoped downstream token."
    )

    pdf.section("Token Claims in OBO Tokens")
    pdf.bullet("sub - the user (subject) the action is on behalf of")
    pdf.bullet("aud - the downstream API this token is valid for")
    pdf.bullet("act (RFC 8693) - the middle-tier service acting on behalf of sub")
    pdf.bullet("azp (Entra) - authorized party / acting app in Entra tokens")

    pdf.section("Planned auth_type: oauth2_obo")
    pdf.body(
        "When implemented, McpConnection will support auth_type=oauth2_obo for per-user "
        "delegation. Token exchange runs before each tools/call. Audit logs both user "
        "(subject) and service (actor)."
    )

    pdf.section("Security Rules for OBO")
    pdf.bullet("1. Validate aud on every token - only accept tokens for your app")
    pdf.bullet("2. Never pass tokens through - always exchange")
    pdf.bullet("3. Use least-privilege scopes on downstream calls")
    pdf.bullet("4. Bind tokens to resource (RFC 8707 audience parameter)")
    pdf.bullet("5. Audit both user (subject) and service (actor)")

    # PART 5 - RFC STANDARDS
    pdf.part_title("Part 5: Industry RFC Standards for MCP")

    pdf.section("RFC 9728 - Protected Resource Metadata")
    pdf.body(
        "Every MCP server MUST expose a discovery document at:\n"
        "/.well-known/oauth-protected-resource\n\n"
        "This JSON file tells clients: 'To access me, go to these authorization servers.' "
        "Clients read this BEFORE starting OAuth, so they know where to send users to login."
    )
    pdf.example_box(
        "Protected Resource Metadata",
        '{ "resource": "https://mcp.example.com", "authorization_servers": ["https://auth.example.com"] }'
    )

    pdf.section("RFC 8414 - Authorization Server Metadata")
    pdf.body(
        "The authorization server exposes its own discovery document with endpoints like "
        "authorization_endpoint (login page URL), token_endpoint (exchange code for token), "
        "and supported grant types. Clients use this to know exactly which URLs to call."
    )

    pdf.section("RFC 8707 - Resource Indicators (Critical Security)")
    pdf.body(
        "When requesting a token, the client MUST include a 'resource' parameter set to "
        "the MCP server URL. This binds the token to ONE specific server. Without this, "
        "a malicious fake MCP server could steal tokens meant for the real server."
    )
    pdf.analogy_box(
        "RFC 8707 is like writing the delivery address on a package. The token can only "
        "be delivered to (used at) that exact address, not a lookalike address."
    )

    pdf.section("RFC 7591 - Dynamic Client Registration")
    pdf.body(
        "Optional standard allowing MCP clients to automatically register themselves with "
        "an authorization server (get a client_id) without manual admin setup. Helpful for "
        "SaaS platforms connecting to many different MCP servers."
    )

    pdf.section("RFC 8693 - OAuth 2.0 Token Exchange (OBO Standard)")
    pdf.body(
        "Defines how a service exchanges an inbound token for a new token scoped to a "
        "different downstream resource. This is the generic standard behind OBO delegation. "
        "Uses grant_type token-exchange, subject_token (user), and audience (downstream). "
        "See Part 4 for full request examples."
    )

    pdf.table_simple(
        ["RFC", "Name", "Purpose"],
        [
            ["RFC 9728", "Protected Resource Metadata", "Find auth server from MCP URL"],
            ["RFC 8414", "AS Metadata", "Find OAuth endpoints"],
            ["RFC 8707", "Resource Indicators", "Bind token to one server"],
            ["RFC 7591", "Dynamic Registration", "Auto-register OAuth client"],
            ["RFC 8693", "Token Exchange (OBO)", "Exchange user token for downstream"],
        ],
    )

    # PART 6 - RBAC
    pdf.part_title("Part 6: RBAC (Role-Based Access Control)")

    pdf.section("What is RBAC?")
    pdf.body(
        "RBAC assigns permissions to ROLES, and roles to USERS. Instead of giving each user "
        "individual permissions, you give them a role (like 'Admin' or 'Viewer') and the "
        "role carries a fixed set of permissions. This is easier to manage in teams."
    )
    pdf.analogy_box(
        "RBAC is like job titles in a company. A 'Manager' can approve expenses; an "
        "'Intern' cannot. You assign a title, not 50 individual permissions per person."
    )

    pdf.section("Roles in Orchestrator")
    pdf.table_simple(
        ["Role", "Level", "Typical use"],
        [
            ["owner", "Highest", "Org creator, full control"],
            ["admin", "High", "Manage users and settings"],
            ["builder", "Medium", "Create agents and workflows"],
            ["viewer", "Low", "Read-only access"],
        ],
    )

    pdf.section("Permissions (Fine-grained actions)")
    pdf.body(
        "Permissions are strings like 'mcp:read' or 'agent:invoke'. Code checks: "
        "does this user's role include this permission? The has_permission(role, permission) "
        "function in rbac.py does this lookup."
    )
    pdf.bullet("mcp:read - View MCP connections and discovered tools")
    pdf.bullet("mcp:write - Create, update, delete MCP connections")
    pdf.bullet("mcp:invoke - Allow agents to call MCP tools at runtime")
    pdf.bullet("agent:invoke - Run an agent")
    pdf.bullet("api_key:write - Create API keys")

    pdf.section("Scopes (for API Keys)")
    pdf.body(
        "Scopes are the API key equivalent of permissions. When creating an API key, you "
        "choose which scopes it has. A key with only 'agent:invoke' cannot manage MCP "
        "connections even if the creating user is an admin."
    )

    pdf.section("Multi-Tenancy (Organization Isolation)")
    pdf.body(
        "In a SaaS platform, every resource belongs to an organization (org_id). "
        "Even if User A is authenticated, they can NEVER access Organization B's agents, "
        "MCP connections, or runs. Authentication proves identity; org_id scoping "
        "ensures tenant isolation."
    )

    # PART 7 - TOOL POLICIES
    pdf.part_title("Part 7: Tool Policies & Security Layers")

    pdf.section("Tool Allowlist")
    pdf.body(
        "An allowlist is a list of tool names that ARE permitted. If allowlist is empty, "
        "all discovered tools may be used (depending on policy). If allowlist has entries, "
        "only those tools can be called. This prevents an agent from accidentally using "
        "dangerous tools like 'delete_database'."
    )

    pdf.section("5-Layer Security Model (Recommended)")
    pdf.body("Industry best practice stacks multiple checks:")
    pdf.bullet("Layer 1 - Transport Auth: Valid JWT, API key, or OAuth token?")
    pdf.bullet("Layer 2 - Tenant Isolation: Does resource belong to user's org?")
    pdf.bullet("Layer 3 - RBAC: Does user's role have the required permission?")
    pdf.bullet("Layer 4 - Tool Policy: Is this specific tool on the allowlist?")
    pdf.bullet("Layer 5 - Audit Log: Record who called what, when, and the result")

    pdf.section("Audit Logging")
    pdf.body(
        "Every MCP tool invocation should be logged: who called it, which tool, which "
        "connection, success or failure, and latency. Do NOT log raw arguments if they "
        "may contain passwords or PII - log a hash instead."
    )

    pdf.section("Encryption at Rest")
    pdf.body(
        "Sensitive data like MCP server passwords, OAuth tokens, and API secrets are "
        "encrypted before storing in the database using Fernet symmetric encryption. "
        "The encryption key lives in environment variables, not in the database."
    )

    # PART 8 - HOW IT FITS TOGETHER
    pdf.part_title("Part 8: How Everything Fits Together")

    pdf.section("Outbound Flow: Org-Level (Current)")
    pdf.body(
        "1. Admin creates MCP connection (base_url, auth type)\n"
        "2. OAuth login OR static bearer token stored encrypted\n"
        "3. Test connection: client calls tools/list, stores discovered tools\n"
        "4. Builder binds specific tools to an agent config\n"
        "5. At runtime: agent calls tools/call with org-level token\n"
        "6. Policy engine checks: RBAC + allowlist + audit log"
    )

    pdf.section("Outbound Flow: Per-User OBO (Planned)")
    pdf.body(
        "1. User logs in; their token reaches Orchestrator\n"
        "2. Agent triggers tool needing downstream API (e.g. Graph)\n"
        "3. Orchestrator exchanges user token via OBO (RFC 8693 / Entra OBO)\n"
        "4. Orchestrator calls downstream with user-scoped token\n"
        "5. Audit: log user (subject) + service (actor) + tool + result"
    )

    pdf.section("Inbound Flow: External client uses Orchestrator MCP")
    pdf.body(
        "1. External client (e.g. Cursor) reads /.well-known/oauth-protected-resource\n"
        "2. User authenticates via OAuth (or uses API key for M2M)\n"
        "3. Client calls tools/list on Orchestrator MCP server\n"
        "4. Client calls tools/call (e.g. orchestrator_invoke_agent)\n"
        "5. Orchestrator validates token, checks RBAC, executes internally"
    )

    pdf.section("Inbound OBO Chain: User -> Orchestrator -> Graph")
    pdf.body(
        "1. User (Entra ID) -> Cursor -> Orchestrator MCP server\n"
        "2. Orchestrator validates user token (aud = Orchestrator)\n"
        "3. Tool needs Microsoft Graph -> Orchestrator does OBO exchange\n"
        "4. Graph receives user-scoped token (aud = Graph, sub = User)\n"
        "5. Graph enforces User's own permissions and Conditional Access"
    )

    pdf.section("Glossary - Quick Reference")
    glossary = [
        ("MCP", "Model Context Protocol - standard for AI tool integration"),
        ("Client", "App that requests and calls tools"),
        ("Server", "System that exposes and runs tools"),
        ("JSON-RPC", "Message format for remote method calls"),
        ("OAuth 2.1", "Standard for delegated authorization"),
        ("PKCE", "Security extension preventing code interception"),
        ("JWT", "Signed token carrying user identity and role"),
        ("API Key", "Long-lived secret for machine access"),
        ("RBAC", "Permissions assigned via roles"),
        ("Scope", "Permission attached to an API key or OAuth token"),
        ("Allowlist", "Explicit list of permitted tools"),
        ("Tenant", "One organization's isolated data space"),
        ("AS", "Authorization Server - issues tokens"),
        ("RS", "Resource Server - accepts tokens (MCP server)"),
        ("RFC 9728", "MCP server discovery document standard"),
        ("RFC 8707", "Binds OAuth token to specific server URL"),
        ("RFC 8693", "OAuth Token Exchange - generic OBO standard"),
        ("OBO", "On-Behalf-Of - exchange user token for downstream token"),
        ("Token Exchange", "RFC 8693 mechanism; same intent as OBO"),
        ("Subject token", "User token presented in an OBO exchange"),
        ("Actor", "Middle-tier service acting on behalf of the user"),
        ("oauth2_obo", "Planned auth type for per-user delegation"),
    ]
    for term, definition in glossary:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(35, 6, term)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, definition)
        pdf.ln(1)

    pdf.output(path)
    print(f"PDF written to {path}")


if __name__ == "__main__":
    out = "/opt/cursor/artifacts/mcp_auth_rbac_concepts_guide.pdf"
    build_pdf(out)
