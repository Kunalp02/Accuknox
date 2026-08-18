import { useEffect, useState } from "react";
import { api, Agent, McpConnection, streamRunEvents, KnowledgeBase } from "../api";

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

  const apiEndpoint = selected
    ? `${window.location.origin}/v1/agents/${selected.id}/invoke`
    : "";

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>Agents</h2>
      <p style={{ color: "var(--muted)", margin: 0 }}>
        Build a single agent, publish it, and expose it as an async API product.
      </p>
      <div className="grid-2">
        <div className="card stack">
          <h3 style={{ margin: 0 }}>Your agents</h3>
          {agents.map((a) => (
            <button
              key={a.id}
              type="button"
              className="secondary"
              onClick={() => select(a)}
              style={{
                textAlign: "left",
                borderColor: selected?.id === a.id ? "var(--accent)" : undefined,
              }}
            >
              {a.name}{" "}
              <span className={`badge ${a.is_published ? "success" : ""}`}>
                {a.is_published ? `v${a.version}` : "draft"}
              </span>
            </button>
          ))}
          <hr style={{ border: "none", borderTop: "1px solid var(--border)" }} />
          <h4 style={{ margin: 0 }}>New agent</h4>
          <div className="field">
            <label>Name</label>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <button type="button" onClick={create} disabled={!form.name}>Create</button>
        </div>

        <div className="card stack">
          {selected ? (
            <>
              <h3 style={{ margin: 0 }}>Edit: {selected.name}</h3>
              <div className="field">
                <label>Description</label>
                <input
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="What this agent does"
                />
              </div>
              <div className="field">
                <label>System prompt</label>
                <textarea
                  rows={4}
                  value={form.system_prompt}
                  onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
                />
              </div>
              <div className="field">
                <label>Model</label>
                <input value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} />
              </div>
              <div className="field">
                <label>Temperature ({form.temperature})</label>
                <input
                  type="range"
                  min={0}
                  max={2}
                  step={0.1}
                  value={form.temperature}
                  onChange={(e) => setForm({ ...form, temperature: Number(e.target.value) })}
                />
              </div>
              {kbs.length > 0 && (
                <div className="field">
                  <label>Knowledge bases</label>
                  {kbs.map((kb) => (
                    <label key={kb.id} style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                      <input
                        type="checkbox"
                        checked={form.knowledge_base_ids.includes(kb.id)}
                        onChange={(e) => {
                          const ids = e.target.checked
                            ? [...form.knowledge_base_ids, kb.id]
                            : form.knowledge_base_ids.filter((id) => id !== kb.id);
                          setForm({ ...form, knowledge_base_ids: ids });
                        }}
                      />
                      {kb.name}
                    </label>
                  ))}
                </div>
              )}
              {mcpConnections.some((c) => c.discovered_tools?.length) && (
                <div className="field">
                  <label>MCP tools</label>
                  {mcpConnections.map((conn) =>
                    conn.discovered_tools?.length ? (
                      <div key={conn.id} style={{ marginBottom: "0.5rem" }}>
                        <strong style={{ fontSize: "0.85rem" }}>{conn.name}</strong>
                        {conn.discovered_tools.map((tool) => (
                          <label
                            key={tool.name}
                            style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginTop: "0.25rem" }}
                          >
                            <input
                              type="checkbox"
                              checked={isToolChecked(conn.id, tool.name)}
                              onChange={(e) => toggleMcpTool(conn.id, tool.name, e.target.checked)}
                            />
                            <span className="mono">{tool.name}</span>
                          </label>
                        ))}
                      </div>
                    ) : null
                  )}
                </div>
              )}
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <button type="button" onClick={save}>Save</button>
                <button type="button" className="secondary" onClick={publish}>Publish</button>
              </div>
              {selected.is_published && (
                <div style={{ padding: "1rem", background: "var(--bg)", borderRadius: 8 }}>
                  <h4 style={{ margin: "0 0 0.5rem" }}>API endpoint</h4>
                  <p className="mono" style={{ margin: 0, fontSize: "0.85rem" }}>POST {apiEndpoint}</p>
                  <p style={{ color: "var(--muted)", margin: "0.5rem 0 0", fontSize: "0.85rem" }}>
                    Returns <span className="mono">202</span> with <span className="mono">run_id</span>.
                    Use API key header <span className="mono">X-API-Key</span> or Bearer.
                  </p>
                  <pre className="mono" style={{ fontSize: "0.75rem", marginTop: "0.5rem", color: "var(--muted)" }}>
{`curl -X POST ${apiEndpoint} \\
  -H "X-API-Key: oak_..." \\
  -H "Content-Type: application/json" \\
  -d '{"input":"Hello"}'`}
                  </pre>
                </div>
              )}
              <hr style={{ border: "none", borderTop: "1px solid var(--border)" }} />
              <h4 style={{ margin: 0 }}>Test invoke (async)</h4>
              <textarea
                rows={3}
                placeholder="Message..."
                value={testInput}
                onChange={(e) => setTestInput(e.target.value)}
              />
              <button type="button" onClick={invoke} disabled={running}>
                {running ? "Running..." : "Invoke"}
              </button>
              <div className="chat-output">{output || "Response will appear here..."}</div>
              <div className="events-log">{events.join("\n")}</div>
            </>
          ) : (
            <p style={{ color: "var(--muted)" }}>Select an agent to edit and test</p>
          )}
        </div>
      </div>
    </div>
  );
}
