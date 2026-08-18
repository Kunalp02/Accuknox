import { useEffect, useState } from "react";
import { api, McpConnection } from "../api";

export default function McpPage() {
  const [connections, setConnections] = useState<McpConnection[]>([]);
  const [form, setForm] = useState({
    name: "",
    base_url: "",
    auth_type: "bearer",
    auth_credentials: "",
    tool_allowlist: "",
  });

  const load = () => api.listMcpConnections().then(setConnections);

  useEffect(() => {
    load();
  }, []);

  const create = async () => {
    await api.createMcpConnection({
      name: form.name,
      base_url: form.base_url,
      auth_type: form.auth_type || undefined,
      auth_credentials: form.auth_credentials || undefined,
      tool_allowlist: form.tool_allowlist
        ? form.tool_allowlist.split(",").map((s) => s.trim()).filter(Boolean)
        : [],
    });
    setForm({ name: "", base_url: "", auth_type: "bearer", auth_credentials: "", tool_allowlist: "" });
    await load();
  };

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>MCP connections</h2>
      <p style={{ color: "var(--muted)", margin: 0 }}>Hosted HTTP only — connect remote MCP servers</p>
      <div className="grid-2">
        <div className="card stack">
          <h3 style={{ margin: 0 }}>Add connection</h3>
          <div className="field">
            <label>Name</label>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div className="field">
            <label>Base URL (HTTP JSON-RPC endpoint)</label>
            <input value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} placeholder="https://mcp.example.com/mcp" />
          </div>
          <div className="field">
            <label>Auth type</label>
            <select value={form.auth_type} onChange={(e) => setForm({ ...form, auth_type: e.target.value })}>
              <option value="bearer">Bearer token</option>
              <option value="api_key_header">API key header (name:value)</option>
            </select>
          </div>
          <div className="field">
            <label>Credentials</label>
            <input
              type="password"
              value={form.auth_credentials}
              onChange={(e) => setForm({ ...form, auth_credentials: e.target.value })}
              placeholder="token or HeaderName: value"
            />
          </div>
          <div className="field">
            <label>Tool allowlist (comma-separated, optional)</label>
            <input value={form.tool_allowlist} onChange={(e) => setForm({ ...form, tool_allowlist: e.target.value })} />
          </div>
          <button type="button" onClick={create} disabled={!form.name || !form.base_url}>Create</button>
        </div>
        <div className="card stack">
          <h3 style={{ margin: 0 }}>Connections</h3>
          {connections.length === 0 && <p style={{ color: "var(--muted)" }}>No connections yet</p>}
          {connections.map((c) => (
            <div key={c.id} style={{ border: "1px solid var(--border)", borderRadius: 8, padding: "0.75rem" }}>
              <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                <strong>{c.name}</strong>
                <span className={`badge ${c.health_status === "healthy" ? "success" : "failed"}`}>
                  {c.health_status}
                </span>
              </div>
              <p className="mono" style={{ color: "var(--muted)", margin: "0.25rem 0" }}>{c.base_url}</p>
              {c.discovered_tools?.length > 0 && (
                <p style={{ margin: "0.25rem 0", fontSize: "0.85rem" }}>
                  Tools: {c.discovered_tools.map((t) => t.name).join(", ")}
                </p>
              )}
              {c.last_error && <p style={{ color: "var(--danger)", fontSize: "0.85rem" }}>{c.last_error}</p>}
              <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
                <button type="button" className="secondary" onClick={() => api.testMcpConnection(c.id).then(load)}>
                  Test & discover tools
                </button>
                <button type="button" className="secondary" onClick={() => api.deleteMcpConnection(c.id).then(load)}>
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
