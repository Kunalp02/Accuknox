import { useEffect, useState } from "react";
import { api, ApiKey } from "../api";

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [name, setName] = useState("");
  const [newKey, setNewKey] = useState<string | null>(null);

  const load = () => api.listApiKeys().then(setKeys);

  useEffect(() => {
    load();
  }, []);

  const create = async () => {
    const key = await api.createApiKey(name || "Default");
    setNewKey(key.key || null);
    setName("");
    await load();
  };

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>API keys</h2>
      <p style={{ color: "var(--muted)", margin: 0 }}>
        Use keys with <span className="mono">X-API-Key</span> or Bearer header to invoke published agents
      </p>
      <div className="card stack">
        <div className="field">
          <label>Key name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Production" />
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
          <div key={k.id} className="mono" style={{ color: "var(--muted)" }}>
            {k.name} — {k.key_prefix}... ({k.scopes.join(", ")})
          </div>
        ))}
      </div>
    </div>
  );
}
