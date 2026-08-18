const API_BASE = "";

export function getToken(): string | null {
  return localStorage.getItem("token");
}

export function setToken(token: string) {
  localStorage.setItem("token", token);
}

export function clearToken() {
  localStorage.removeItem("token");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = err.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join("; ")
          : detail && typeof detail === "object"
            ? JSON.stringify(detail)
            : "Request failed";
    throw new Error(message);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  signup: (data: { email: string; password: string; org_name: string }) =>
    request<{ access_token: string }>("/v1/auth/signup", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  login: (data: { email: string; password: string }) =>
    request<{ access_token: string }>("/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  me: () => request<{ email: string; role: string; org_id: string }>("/v1/auth/me"),
  listAgents: () => request<Agent[]>("/v1/agents"),
  createAgent: (data: Partial<Agent>) =>
    request<Agent>("/v1/agents", { method: "POST", body: JSON.stringify(data) }),
  updateAgent: (id: string, data: Partial<Agent>) =>
    request<Agent>(`/v1/agents/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  publishAgent: (id: string) =>
    request<Agent>(`/v1/agents/${id}/publish`, { method: "POST" }),
  invokeAgent: (id: string, input: string) =>
    request<{ run_id: string; status: string }>(`/v1/agents/${id}/invoke`, {
      method: "POST",
      body: JSON.stringify({ input }),
    }),
  getRun: (id: string) => request<Run>(`/v1/runs/${id}`),
  listRuns: () => request<Run[]>("/v1/runs"),
  listKbs: () => request<KnowledgeBase[]>("/v1/knowledge-bases"),
  createKb: (name: string) =>
    request<KnowledgeBase>("/v1/knowledge-bases", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  uploadDoc: async (kbId: string, file: File) => {
    const token = getToken();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_BASE}/v1/knowledge-bases/${kbId}/documents`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!res.ok) throw new Error("Upload failed");
    return res.json();
  },
  createApiKey: (data: {
    name: string;
    scopes?: string[];
    resource_ids?: string[];
    rate_limit_per_minute?: number;
  }) =>
    request<ApiKey>("/v1/api-keys", {
      method: "POST",
      body: JSON.stringify({
        scopes: ["agent:invoke", "workflow:invoke", "run:read"],
        ...data,
      }),
    }),
  listApiKeys: () => request<ApiKey[]>("/v1/api-keys"),
  getUsage: (days?: number) => request<UsageDay[]>(`/v1/usage?days=${days || 30}`),
  listWorkflows: () => request<Workflow[]>("/v1/workflows"),
  createWorkflow: (data: { name: string; description?: string; graph?: WorkflowGraph }) =>
    request<Workflow>("/v1/workflows", { method: "POST", body: JSON.stringify(data) }),
  updateWorkflow: (id: string, data: Partial<Workflow>) =>
    request<Workflow>(`/v1/workflows/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  publishWorkflow: (id: string) =>
    request<Workflow>(`/v1/workflows/${id}/publish`, { method: "POST" }),
  validateWorkflow: (id: string) =>
    request<{ valid: boolean; errors: string[]; warnings: string[] }>(
      `/v1/workflows/${id}/validate`,
      { method: "POST" }
    ),
  invokeWorkflow: (id: string, input: string) =>
    request<{ run_id: string; status: string }>(`/v1/workflows/${id}/invoke`, {
      method: "POST",
      body: JSON.stringify({ input }),
    }),
  resumeRun: (runId: string, input: string) =>
    request<{ run_id: string; status: string }>(`/v1/runs/${runId}/resume`, {
      method: "POST",
      body: JSON.stringify({ input }),
    }),
  listMcpConnections: () => request<McpConnection[]>("/v1/mcp-connections"),
  createMcpConnection: (data: Partial<McpConnection> & { auth_credentials?: string }) =>
    request<McpConnection>("/v1/mcp-connections", { method: "POST", body: JSON.stringify(data) }),
  testMcpConnection: (id: string) =>
    request<McpConnection>(`/v1/mcp-connections/${id}/test`, { method: "POST" }),
  deleteMcpConnection: (id: string) =>
    request<void>(`/v1/mcp-connections/${id}`, { method: "DELETE" }),
  getGatewaySettings: () => request<GatewaySettings>("/v1/settings/llm-gateway"),
  updateGatewaySettings: (data: GatewayUpdate) =>
    request<GatewaySettings>("/v1/settings/llm-gateway", { method: "PUT", body: JSON.stringify(data) }),
  clearGatewaySettings: () => request<void>("/v1/settings/llm-gateway", { method: "DELETE" }),
  testGateway: () => request<Record<string, unknown>>("/v1/settings/llm-gateway/test", { method: "POST" }),
};

export interface Agent {
  id: string;
  name: string;
  description?: string;
  system_prompt: string;
  model: string;
  temperature: number;
  is_published: boolean;
  version: number;
  knowledge_base_ids: string[];
  mcp_tools: Array<{ connection_id: string; tools: string[] }>;
}

export interface WorkflowGraph {
  entry: string;
  nodes: Array<Record<string, unknown>>;
  edges: Array<{ from: string; to: string; condition?: string }>;
}

export interface Workflow {
  id: string;
  name: string;
  description?: string;
  graph: WorkflowGraph;
  is_published: boolean;
  version: number;
}

export interface McpConnection {
  id: string;
  name: string;
  base_url: string;
  auth_type?: string;
  tool_allowlist: string[];
  discovered_tools: Array<{ name: string; description?: string }>;
  health_status: string;
  last_error?: string;
  auth_credentials?: string;
}

export interface Run {
  id: string;
  status: string;
  agent_id?: string;
  workflow_id?: string;
  input: { message?: string; human_response?: string };
  output?: { message?: string };
  error?: string;
  metrics: Record<string, number>;
  trace?: Array<{ ts?: string; type: string; data: Record<string, unknown> }>;
}

export interface GatewaySettings {
  uses_platform_default: boolean;
  base_url?: string;
  default_model?: string;
  embed_model?: string;
  allowed_models?: string[];
  has_api_key?: boolean;
  platform_default_model: string;
  platform_embed_model: string;
}

export interface GatewayUpdate {
  base_url: string;
  default_model: string;
  embed_model: string;
  api_key?: string;
  allowed_models?: string[];
}

export interface KnowledgeBase {
  id: string;
  name: string;
  description?: string;
  embed_model: string;
}

export interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  key?: string;
  scopes: string[];
  resource_ids?: string[];
}

export interface UsageDay {
  date: string;
  runs_total: number;
  runs_completed: number;
  runs_failed: number;
  tokens_in: number;
  tokens_out: number;
}

export function streamRunEvents(
  runId: string,
  onEvent: (type: string, data: unknown) => void
): () => void {
  const token = getToken();
  const controller = new AbortController();
  fetch(`/v1/runs/${runId}/events`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    signal: controller.signal,
  }).then(async (res) => {
    const reader = res.body?.getReader();
    const decoder = new TextDecoder();
    if (!reader) return;
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const parsed = JSON.parse(line.slice(6));
            onEvent(parsed.type, parsed.data);
          } catch {
            /* ignore */
          }
        }
      }
    }
  });
  return () => controller.abort();
}
