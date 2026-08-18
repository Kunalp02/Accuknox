import { useEffect, useState } from "react";
import { api, GatewaySettings } from "../api";

export default function SettingsPage() {
  const [settings, setSettings] = useState<GatewaySettings | null>(null);
  const [form, setForm] = useState({
    base_url: "",
    default_model: "llama3.2",
    embed_model: "nomic-embed-text",
    api_key: "",
    allowed_models: "",
  });
  const [testResult, setTestResult] = useState<string>("");
  const [loading, setLoading] = useState(false);

  const load = async () => {
    const s = await api.getGatewaySettings();
    setSettings(s);
    if (!s.uses_platform_default && s.base_url) {
      setForm({
        base_url: s.base_url,
        default_model: s.default_model || s.platform_default_model,
        embed_model: s.embed_model || s.platform_embed_model,
        api_key: "",
        allowed_models: (s.allowed_models || []).join(", "),
      });
    }
  };

  useEffect(() => {
    load();
  }, []);

  const save = async () => {
    setLoading(true);
    try {
      const updated = await api.updateGatewaySettings({
        base_url: form.base_url,
        default_model: form.default_model,
        embed_model: form.embed_model,
        api_key: form.api_key || undefined,
        allowed_models: form.allowed_models
          ? form.allowed_models.split(",").map((s) => s.trim()).filter(Boolean)
          : [],
      });
      setSettings(updated);
      setForm((f) => ({ ...f, api_key: "" }));
    } finally {
      setLoading(false);
    }
  };

  const test = async () => {
    setTestResult("Testing...");
    const res = await api.testGateway();
    setTestResult(JSON.stringify(res, null, 2));
  };

  const usePlatform = async () => {
    await api.clearGatewaySettings();
    await load();
    setForm({
      base_url: "",
      default_model: settings?.platform_default_model || "llama3.2",
      embed_model: settings?.platform_embed_model || "nomic-embed-text",
      api_key: "",
      allowed_models: "",
    });
  };

  if (!settings) return null;

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>Settings</h2>
      <p style={{ color: "var(--muted)", margin: 0 }}>
        Configure your org&apos;s OpenAI-compatible gateway (Ollama Cloud, Bifrost, etc.)
      </p>
      <div className="card stack">
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <span className={`badge ${settings.uses_platform_default ? "pending" : "success"}`}>
            {settings.uses_platform_default ? "platform default" : "custom gateway"}
          </span>
          <span className="mono" style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
            platform: {settings.platform_default_model} · embed: {settings.platform_embed_model}
          </span>
        </div>
        <div className="field">
          <label>Gateway base URL</label>
          <input
            value={form.base_url}
            onChange={(e) => setForm({ ...form, base_url: e.target.value })}
            placeholder="https://your-bifrost-or-ollama-host/v1"
          />
        </div>
        <div className="field">
          <label>Default chat model</label>
          <input value={form.default_model} onChange={(e) => setForm({ ...form, default_model: e.target.value })} />
        </div>
        <div className="field">
          <label>Embedding model</label>
          <input value={form.embed_model} onChange={(e) => setForm({ ...form, embed_model: e.target.value })} />
        </div>
        <div className="field">
          <label>API key {settings.has_api_key && !form.api_key ? "(configured — enter to replace)" : ""}</label>
          <input
            type="password"
            value={form.api_key}
            onChange={(e) => setForm({ ...form, api_key: e.target.value })}
            placeholder="Optional gateway API key"
          />
        </div>
        <div className="field">
          <label>Allowed models (comma-separated, optional)</label>
          <input value={form.allowed_models} onChange={(e) => setForm({ ...form, allowed_models: e.target.value })} />
        </div>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          <button type="button" onClick={save} disabled={loading || !form.base_url}>Save custom gateway</button>
          <button type="button" className="secondary" onClick={test}>Test connection</button>
          {!settings.uses_platform_default && (
            <button type="button" className="secondary" onClick={usePlatform}>Use platform default</button>
          )}
        </div>
        {testResult && (
          <pre className="mono" style={{ fontSize: "0.75rem", color: "var(--muted)", whiteSpace: "pre-wrap" }}>
            {testResult}
          </pre>
        )}
      </div>
    </div>
  );
}
