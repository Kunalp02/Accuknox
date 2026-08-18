import { useEffect, useState } from "react";
import { api, GatewaySettings } from "../api";
import { PageHeader } from "../components/ui/page-header";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Field } from "../components/ui/label";
import { Input } from "../components/ui/input";

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
    <div>
      <PageHeader
        title="Settings"
        description="Configure your org's OpenAI-compatible gateway (Ollama Cloud, Bifrost, etc.)"
      />

      <Card className="max-w-2xl space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={settings.uses_platform_default ? "warning" : "success"}>
            {settings.uses_platform_default ? "platform default" : "custom gateway"}
          </Badge>
          <span className="font-mono text-xs text-gray-500">
            platform: {settings.platform_default_model} · embed: {settings.platform_embed_model}
          </span>
        </div>

        <Field label="Gateway base URL">
          <Input
            value={form.base_url}
            onChange={(e) => setForm({ ...form, base_url: e.target.value })}
            placeholder="https://your-bifrost-or-ollama-host/v1"
          />
        </Field>
        <Field label="Default chat model">
          <Input value={form.default_model} onChange={(e) => setForm({ ...form, default_model: e.target.value })} />
        </Field>
        <Field label="Embedding model">
          <Input value={form.embed_model} onChange={(e) => setForm({ ...form, embed_model: e.target.value })} />
        </Field>
        <Field label={`API key ${settings.has_api_key && !form.api_key ? "(configured — enter to replace)" : ""}`}>
          <Input
            type="password"
            value={form.api_key}
            onChange={(e) => setForm({ ...form, api_key: e.target.value })}
            placeholder="Optional gateway API key"
          />
        </Field>
        <Field label="Allowed models (comma-separated, optional)">
          <Input value={form.allowed_models} onChange={(e) => setForm({ ...form, allowed_models: e.target.value })} />
        </Field>

        <div className="flex flex-wrap gap-2">
          <Button type="button" onClick={save} disabled={loading || !form.base_url}>
            Save custom gateway
          </Button>
          <Button type="button" variant="secondary" onClick={test}>Test connection</Button>
          {!settings.uses_platform_default && (
            <Button type="button" variant="secondary" onClick={usePlatform}>
              Use platform default
            </Button>
          )}
        </div>

        {testResult && (
          <pre className="font-mono text-xs text-gray-500 whitespace-pre-wrap rounded-lg bg-gray-50 p-3">
            {testResult}
          </pre>
        )}
      </Card>
    </div>
  );
}
