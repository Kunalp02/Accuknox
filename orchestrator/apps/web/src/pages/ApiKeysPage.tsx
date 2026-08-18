import { useEffect, useState } from "react";
import { api, Agent, ApiKey, Workflow, UsageDay } from "../api";

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [usage, setUsage] = useState<UsageDay[]>([]);
  const [name, setName] = useState("");
  const [rateLimit, setRateLimit] = useState(60);
  const [resourceIds, setResourceIds] = useState<string[]>([]);
  const [newKey, setNewKey] = useState<string | null>(null);

  const load = async () => {
    const [k, a, w, u] = await Promise.all([
      api.listApiKeys(),
      api.listAgents(),
      api.listWorkflows(),
      api.getUsage(14),
    ]);
    setKeys(k);
    setAgents(a);
    setWorkflows(w);
    setUsage(u);
  };

  useEffect(() => {
    load();
  }, []);

  const create = async () => {
    const key = await api.createApiKey({
      name: name || "Default",
      resource_ids: resourceIds,
      rate_limit_per_minute: rateLimit,
    });
    setNewKey(key.key || null);
    setName("");
    setResourceIds([]);
    await load();
  };

  const toggleResource = (id: string) => {
    setResourceIds((ids) =>
      ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]
    );
  };

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>API keys & usage</h2>
      <div className="grid-2">
        <div className="card stack">
          <h3 style={{ margin: 0 }}>Create API key</h3>
          <p style={{ color: "var(--muted)", margin: 0, fontSize: "0.85rem" }}>
            Scope to specific agents/workflows, or leave empty for all published resources.
          </p>
          <div className="field">
            <label>Name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Production" />
          </div>
          <div className="field">
            <label>Rate limit (req/min)</label>
            <input type="number" min={1} value={rateLimit} onChange={(e) => setRateLimit(Number(e.target.value))} />
          </div>
          <div className="field">
            <label>Resource scope (optional)</label>
            {agents.filter((a) => a.is_published).map((a) => (
              <label key={a.id} style={{ display: "flex", gap: "0.5rem" }}>
                <input type="checkbox" checked={resourceIds.includes(a.id)} onChange={() => toggleResource(a.id)} />
                Agent: {a.name}
              </label>
            ))}
            {workflows.filter((w) => w.is_published).map((w) => (
              <label key={w.id} style={{ display: "flex", gap: "0.5rem" }}>
                <input type="checkbox" checked={resourceIds.includes(w.id)} onChange={() => toggleResource(w.id)} />
                Workflow: {w.name}
              </label>
            ))}
          </div>
          <button type="button" onClick={create}>Create API key</button>
          {newKey && (
            <div style={{ padding: "1rem", background: "var(--bg)", borderRadius: "var(--radius)" }}>
              <p style={{ margin: 0, color: "var(--success)" }}>Copy now — won&apos;t be shown again:</p>
              <p className="mono" style={{ margin: "0.5rem 0 0" }}>{newKey}</p>
            </div>
          )}
          <hr style={{ border: "none", borderTop: "1px solid var(--border)" }} />
          {keys.map((k) => (
            <div key={k.id} className="mono" style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
              {k.name} — {k.key_prefix}... · {k.scopes.join(", ")}
              {k.resource_ids?.length ? ` · scoped: ${k.resource_ids.length}` : " · all resources"}
            </div>
          ))}
        </div>
        <div className="card stack">
          <h3 style={{ margin: 0 }}>Usage (14 days)</h3>
          {usage.length === 0 && <p style={{ color: "var(--muted)" }}>No usage yet</p>}
          {usage.map((u) => (
            <div key={u.date} style={{ borderBottom: "1px solid var(--border)", padding: "0.5rem 0" }}>
              <strong>{u.date}</strong>
              <p style={{ margin: "0.25rem 0", color: "var(--muted)", fontSize: "0.85rem" }}>
                runs: {u.runs_total} ({u.runs_completed} ok, {u.runs_failed} failed) ·
                tokens in: {u.tokens_in} · out: {u.tokens_out}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
