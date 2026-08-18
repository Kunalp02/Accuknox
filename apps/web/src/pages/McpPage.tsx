import { useEffect, useState } from "react";
import { api, McpConnection } from "../api";
import { PageHeader } from "../components/ui/page-header";
import { Card, CardHeader } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Field } from "../components/ui/label";
import { Input } from "../components/ui/input";
import { Select } from "../components/ui/select";

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
    <div>
      <PageHeader
        title="MCP connections"
        description="Hosted HTTP only — connect remote MCP servers for agent and workflow tools."
      />

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="Add connection" />
          <div className="space-y-4">
            <Field label="Name">
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </Field>
            <Field label="Base URL (HTTP JSON-RPC endpoint)">
              <Input
                value={form.base_url}
                onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                placeholder="https://mcp.example.com/mcp"
              />
            </Field>
            <Field label="Auth type">
              <Select value={form.auth_type} onChange={(e) => setForm({ ...form, auth_type: e.target.value })}>
                <option value="bearer">Bearer token</option>
                <option value="api_key_header">API key header (name:value)</option>
              </Select>
            </Field>
            <Field label="Credentials">
              <Input
                type="password"
                value={form.auth_credentials}
                onChange={(e) => setForm({ ...form, auth_credentials: e.target.value })}
                placeholder="token or HeaderName: value"
              />
            </Field>
            <Field label="Tool allowlist (comma-separated, optional)">
              <Input value={form.tool_allowlist} onChange={(e) => setForm({ ...form, tool_allowlist: e.target.value })} />
            </Field>
            <Button type="button" onClick={create} disabled={!form.name || !form.base_url}>
              Create
            </Button>
          </div>
        </Card>

        <Card>
          <CardHeader title="Connections" />
          {connections.length === 0 && <p className="text-sm text-gray-500">No connections yet</p>}
          <div className="space-y-3">
            {connections.map((c) => (
              <div key={c.id} className="rounded-lg border border-border p-4">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-900">{c.name}</span>
                  <Badge variant={c.health_status === "healthy" ? "success" : "danger"}>
                    {c.health_status}
                  </Badge>
                </div>
                <p className="mt-1 font-mono text-xs text-gray-500">{c.base_url}</p>
                {c.discovered_tools?.length > 0 && (
                  <p className="mt-2 text-sm text-gray-600">
                    Tools: {c.discovered_tools.map((t) => t.name).join(", ")}
                  </p>
                )}
                {c.last_error && <p className="mt-1 text-sm text-red-600">{c.last_error}</p>}
                <div className="mt-3 flex gap-2">
                  <Button type="button" variant="secondary" size="sm" onClick={() => api.testMcpConnection(c.id).then(load)}>
                    Test & discover
                  </Button>
                  <Button type="button" variant="secondary" size="sm" onClick={() => api.deleteMcpConnection(c.id).then(load)}>
                    Delete
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
