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
    throw new Error(err.detail || "Request failed");
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
  createApiKey: (name: string) =>
    request<ApiKey>("/v1/api-keys", {
      method: "POST",
      body: JSON.stringify({ name, scopes: ["agent:invoke", "run:read"] }),
    }),
  listApiKeys: () => request<ApiKey[]>("/v1/api-keys"),
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
}

export interface Run {
  id: string;
  status: string;
  agent_id?: string;
  input: { message?: string };
  output?: { message?: string };
  error?: string;
  metrics: Record<string, number>;
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
