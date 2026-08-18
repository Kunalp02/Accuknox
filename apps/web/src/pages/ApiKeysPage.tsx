import { useEffect, useState } from "react";
import { api, Agent, ApiKey, Workflow, UsageDay } from "../api";
import { PageHeader } from "../components/ui/page-header";
import { Card, CardHeader } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Field } from "../components/ui/label";
import { Input } from "../components/ui/input";

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
    <div>
      <PageHeader title="API keys & usage" description="Manage API access and monitor consumption." />

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="Create API key"
            description="Scope to specific agents/workflows, or leave empty for all published resources."
          />
          <div className="space-y-4">
            <Field label="Name">
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Production" />
            </Field>
            <Field label="Rate limit (req/min)">
              <Input type="number" min={1} value={rateLimit} onChange={(e) => setRateLimit(Number(e.target.value))} />
            </Field>
            <Field label="Resource scope (optional)">
              <div className="space-y-2">
                {agents.filter((a) => a.is_published).map((a) => (
                  <label key={a.id} className="flex items-center gap-2 text-sm text-gray-700">
                    <input
                      type="checkbox"
                      checked={resourceIds.includes(a.id)}
                      onChange={() => toggleResource(a.id)}
                      className="rounded border-gray-300 text-primary focus:ring-primary"
                    />
                    Agent: {a.name}
                  </label>
                ))}
                {workflows.filter((w) => w.is_published).map((w) => (
                  <label key={w.id} className="flex items-center gap-2 text-sm text-gray-700">
                    <input
                      type="checkbox"
                      checked={resourceIds.includes(w.id)}
                      onChange={() => toggleResource(w.id)}
                      className="rounded border-gray-300 text-primary focus:ring-primary"
                    />
                    Workflow: {w.name}
                  </label>
                ))}
              </div>
            </Field>
            <Button type="button" onClick={create}>Create API key</Button>

            {newKey && (
              <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-4">
                <p className="text-sm font-medium text-emerald-700">Copy now — won&apos;t be shown again:</p>
                <p className="mt-2 font-mono text-sm text-emerald-900">{newKey}</p>
              </div>
            )}

            <div className="border-t border-border pt-4 space-y-2">
              {keys.map((k) => (
                <div key={k.id} className="font-mono text-xs text-gray-500">
                  {k.name} — {k.key_prefix}... · {k.scopes.join(", ")}
                  {k.resource_ids?.length ? ` · scoped: ${k.resource_ids.length}` : " · all resources"}
                </div>
              ))}
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader title="Usage (14 days)" />
          {usage.length === 0 && <p className="text-sm text-gray-500">No usage yet</p>}
          <div className="space-y-3">
            {usage.map((u) => (
              <div key={u.date} className="border-b border-border pb-3 last:border-0">
                <p className="font-medium text-gray-900">{u.date}</p>
                <p className="text-sm text-gray-500">
                  runs: {u.runs_total} ({u.runs_completed} ok, {u.runs_failed} failed) ·
                  tokens in: {u.tokens_in} · out: {u.tokens_out}
                </p>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
