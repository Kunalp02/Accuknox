import { useEffect, useState } from "react";
import { Plus, Send } from "lucide-react";
import { api, Agent, McpConnection, streamRunEvents, KnowledgeBase } from "../api";
import { PageHeader } from "../components/ui/page-header";
import { Card, CardHeader } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Field } from "../components/ui/label";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { cn } from "../lib/cn";

type McpToolEntry = { connection_id: string; tools: string[] };

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [mcpConnections, setMcpConnections] = useState<McpConnection[]>([]);
  const [selected, setSelected] = useState<Agent | null>(null);
  const [form, setForm] = useState({
    name: "",
    description: "",
    system_prompt: "You are a helpful assistant.",
    model: "llama3.2",
    temperature: 0.7,
    knowledge_base_ids: [] as string[],
    mcp_tools: [] as McpToolEntry[],
  });
  const [testInput, setTestInput] = useState("");
  const [output, setOutput] = useState("");
  const [events, setEvents] = useState<string[]>([]);
  const [running, setRunning] = useState(false);

  const load = async () => {
    const [a, k, m] = await Promise.all([
      api.listAgents(),
      api.listKbs(),
      api.listMcpConnections(),
    ]);
    setAgents(a);
    setKbs(k);
    setMcpConnections(m);
  };

  useEffect(() => {
    load();
  }, []);

  const resetForm = () => ({
    name: "",
    description: "",
    system_prompt: "You are a helpful assistant.",
    model: "llama3.2",
    temperature: 0.7,
    knowledge_base_ids: [],
    mcp_tools: [],
  });

  const create = async () => {
    await api.createAgent(form);
    setForm(resetForm());
    await load();
  };

  const select = (agent: Agent) => {
    setSelected(agent);
    setForm({
      name: agent.name,
      description: agent.description || "",
      system_prompt: agent.system_prompt,
      model: agent.model,
      temperature: agent.temperature,
      knowledge_base_ids: agent.knowledge_base_ids || [],
      mcp_tools: agent.mcp_tools || [],
    });
    setOutput("");
    setEvents([]);
  };

  const save = async () => {
    if (!selected) return;
    const updated = await api.updateAgent(selected.id, form);
    setSelected(updated);
    await load();
  };

  const publish = async () => {
    if (!selected) return;
    const updated = await api.publishAgent(selected.id);
    setSelected(updated);
    await load();
  };

  const toggleMcpTool = (connectionId: string, toolName: string, checked: boolean) => {
    const existing = form.mcp_tools.find((e) => e.connection_id === connectionId);
    let mcp_tools: McpToolEntry[];
    if (existing) {
      const tools = checked
        ? [...existing.tools, toolName]
        : existing.tools.filter((t) => t !== toolName);
      mcp_tools = form.mcp_tools.map((e) =>
        e.connection_id === connectionId ? { ...e, tools } : e
      );
      if (!tools.length) mcp_tools = mcp_tools.filter((e) => e.connection_id !== connectionId);
    } else if (checked) {
      mcp_tools = [...form.mcp_tools, { connection_id: connectionId, tools: [toolName] }];
    } else {
      mcp_tools = form.mcp_tools;
    }
    setForm({ ...form, mcp_tools });
  };

  const isToolChecked = (connectionId: string, toolName: string) => {
    const entry = form.mcp_tools.find((e) => e.connection_id === connectionId);
    return entry?.tools.includes(toolName) ?? false;
  };

  const invoke = async () => {
    if (!selected || !testInput.trim()) return;
    setRunning(true);
    setOutput("");
    setEvents([]);
    try {
      const { run_id } = await api.invokeAgent(selected.id, testInput);
      setEvents((e) => [...e, `run started: ${run_id}`]);
      const stop = streamRunEvents(run_id, (type, data) => {
        setEvents((e) => [...e, `${type}: ${JSON.stringify(data)}`]);
        if (type === "message.delta" && data && typeof data === "object" && "content" in data) {
          setOutput(String((data as { content: string }).content));
        }
        if (type === "run.completed" && data && typeof data === "object" && "message" in data) {
          setOutput(String((data as { message: string }).message));
        }
        if (type === "run.failed") {
          setOutput(`Error: ${JSON.stringify(data)}`);
        }
      });
      const poll = setInterval(async () => {
        const run = await api.getRun(run_id);
        if (run.status === "completed" || run.status === "failed") {
          clearInterval(poll);
          stop();
          if (run.output?.message) setOutput(run.output.message);
          if (run.error) setOutput(`Error: ${run.error}`);
          setRunning(false);
        }
      }, 1500);
    } catch (err) {
      setOutput(err instanceof Error ? err.message : "Invoke failed");
      setRunning(false);
    }
  };

  const apiEndpoint = selected ? `${window.location.origin}/v1/agents/${selected.id}/invoke` : "";

  return (
    <div>
      <PageHeader
        title="Agents"
        description="Build a single agent, publish it, and expose it as an async API product."
      />

      <div className="grid gap-5 lg:grid-cols-[280px_1fr_320px]">
        <Card>
          <CardHeader title="Your agents" />
          <div className="space-y-1">
            {agents.map((a) => (
              <button
                key={a.id}
                type="button"
                onClick={() => select(a)}
                className={cn(
                  "flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left text-sm transition-colors",
                  selected?.id === a.id
                    ? "bg-primary-subtle text-primary"
                    : "text-gray-700 hover:bg-gray-50"
                )}
              >
                <span className="font-medium">{a.name}</span>
                <Badge variant={a.is_published ? "success" : "default"}>
                  {a.is_published ? `v${a.version}` : "draft"}
                </Badge>
              </button>
            ))}
          </div>

          <div className="mt-6 border-t border-border pt-5 space-y-3">
            <h4 className="text-sm font-semibold text-gray-900">New agent</h4>
            <Field label="Name">
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </Field>
            <Button type="button" onClick={create} disabled={!form.name} size="sm">
              <Plus className="h-4 w-4" />
              Create
            </Button>
          </div>
        </Card>

        <Card>
          {selected ? (
            <div className="space-y-4">
              <CardHeader title={`Edit: ${selected.name}`} />
              <Field label="Description">
                <Input
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="What this agent does"
                />
              </Field>
              <Field label="System prompt">
                <Textarea
                  rows={4}
                  value={form.system_prompt}
                  onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
                />
              </Field>
              <Field label="Model">
                <Input value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} />
              </Field>
              <Field label={`Temperature (${form.temperature})`}>
                <input
                  type="range"
                  min={0}
                  max={2}
                  step={0.1}
                  value={form.temperature}
                  onChange={(e) => setForm({ ...form, temperature: Number(e.target.value) })}
                  className="w-full accent-primary"
                />
              </Field>
              {kbs.length > 0 && (
                <Field label="Knowledge bases">
                  <div className="space-y-2">
                    {kbs.map((kb) => (
                      <label key={kb.id} className="flex items-center gap-2 text-sm text-gray-700">
                        <input
                          type="checkbox"
                          checked={form.knowledge_base_ids.includes(kb.id)}
                          onChange={(e) => {
                            const ids = e.target.checked
                              ? [...form.knowledge_base_ids, kb.id]
                              : form.knowledge_base_ids.filter((id) => id !== kb.id);
                            setForm({ ...form, knowledge_base_ids: ids });
                          }}
                          className="rounded border-gray-300 text-primary focus:ring-primary"
                        />
                        {kb.name}
                      </label>
                    ))}
                  </div>
                </Field>
              )}
              {mcpConnections.some((c) => c.discovered_tools?.length) && (
                <Field label="MCP tools">
                  {mcpConnections.map((conn) =>
                    conn.discovered_tools?.length ? (
                      <div key={conn.id} className="mb-2">
                        <p className="text-xs font-semibold text-gray-500">{conn.name}</p>
                        {conn.discovered_tools.map((tool) => (
                          <label
                            key={tool.name}
                            className="flex items-center gap-2 mt-1 text-sm text-gray-700"
                          >
                            <input
                              type="checkbox"
                              checked={isToolChecked(conn.id, tool.name)}
                              onChange={(e) => toggleMcpTool(conn.id, tool.name, e.target.checked)}
                              className="rounded border-gray-300 text-primary focus:ring-primary"
                            />
                            <span className="font-mono text-xs">{tool.name}</span>
                          </label>
                        ))}
                      </div>
                    ) : null
                  )}
                </Field>
              )}
              <div className="flex gap-2">
                <Button type="button" onClick={save}>Save</Button>
                <Button type="button" variant="secondary" onClick={publish}>Publish</Button>
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-500">Select an agent to edit</p>
          )}
        </Card>

        <Card>
          {selected ? (
            <div className="space-y-4">
              {selected.is_published && (
                <div className="rounded-lg bg-gray-50 p-4 space-y-2">
                  <h4 className="text-sm font-semibold text-gray-900">API endpoint</h4>
                  <p className="font-mono text-xs text-gray-600">POST {apiEndpoint}</p>
                  <p className="text-xs text-gray-500">
                    Returns 202 with run_id. Use X-API-Key or Bearer auth.
                  </p>
                  <pre className="font-mono text-[11px] text-gray-500 overflow-x-auto">
{`curl -X POST ${apiEndpoint} \\
  -H "X-API-Key: oak_..." \\
  -H "Content-Type: application/json" \\
  -d '{"input":"Hello"}'`}
                  </pre>
                </div>
              )}

              <CardHeader title="Test invoke" description="Async — response streams via SSE" />
              <Textarea
                rows={3}
                placeholder="Message..."
                value={testInput}
                onChange={(e) => setTestInput(e.target.value)}
              />
              <Button type="button" onClick={invoke} disabled={running}>
                <Send className="h-4 w-4" />
                {running ? "Running..." : "Invoke"}
              </Button>
              <div className="min-h-[120px] rounded-lg border border-border bg-gray-50 p-3 text-sm whitespace-pre-wrap">
                {output || "Response will appear here..."}
              </div>
              {events.length > 0 && (
                <pre className="font-mono text-[11px] text-gray-400 max-h-32 overflow-y-auto">
                  {events.join("\n")}
                </pre>
              )}
            </div>
          ) : (
            <p className="text-sm text-gray-500">Select an agent to test</p>
          )}
        </Card>
      </div>
    </div>
  );
}
