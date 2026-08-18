import type { Agent, McpConnection } from "../api";

export type WorkflowNodeData = Record<string, unknown> & {
  id: string;
  type: string;
  position?: { x: number; y: number };
};

export function nodeLabel(node: WorkflowNodeData): string {
  const type = node.type;
  if (type === "agent") {
    const aid = node.agent_id as string | undefined;
    return `agent: ${aid ? aid.slice(0, 8) : "?"}…`;
  }
  if (type === "supervisor") {
    const n = (node.children as string[] | undefined)?.length || 0;
    return `supervisor (${n} children)`;
  }
  if (type === "tool") return `tool: ${node.tool_name || "?"}`;
  if (type === "branch") return `branch`;
  if (type === "parallel") {
    const n = (node.branches as string[] | undefined)?.length || 0;
    return `parallel (${n})`;
  }
  if (type === "human") return `human`;
  return `${type}: ${node.id}`;
}

interface NodeConfigPanelProps {
  node: WorkflowNodeData;
  nodeIds: string[];
  agents: Agent[];
  mcpConnections: McpConnection[];
  onChange: (updated: WorkflowNodeData) => void;
}

export function NodeConfigPanel({
  node,
  nodeIds,
  agents,
  mcpConnections,
  onChange,
}: NodeConfigPanelProps) {
  const set = (patch: Partial<WorkflowNodeData>) => onChange({ ...node, ...patch });

  return (
    <div className="stack" style={{ fontSize: "0.9rem" }}>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
        <span className="badge">{node.type}</span>
        <span className="mono">{node.id}</span>
      </div>

      {node.type === "agent" && (
        <div className="field">
          <label>Agent</label>
          <select
            value={(node.agent_id as string) || ""}
            onChange={(e) => set({ agent_id: e.target.value })}
          >
            <option value="">Select agent…</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        </div>
      )}

      {node.type === "supervisor" && (
        <>
          <div className="field">
            <label>Routing prompt (optional)</label>
            <textarea
              rows={3}
              value={(node.system_prompt as string) || ""}
              onChange={(e) => set({ system_prompt: e.target.value })}
              placeholder="You are a supervisor. Route to the best child node id…"
            />
          </div>
          <div className="field">
            <label>Model (optional)</label>
            <input
              value={(node.model as string) || ""}
              onChange={(e) => set({ model: e.target.value })}
              placeholder="llama3.2"
            />
          </div>
          <div className="field">
            <label>Child nodes (routing targets)</label>
            {nodeIds
              .filter((id) => id !== node.id)
              .map((id) => (
                <label key={id} style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <input
                    type="checkbox"
                    checked={((node.children as string[]) || []).includes(id)}
                    onChange={(e) => {
                      const cur = (node.children as string[]) || [];
                      const children = e.target.checked
                        ? [...cur, id]
                        : cur.filter((c) => c !== id);
                      set({ children });
                    }}
                  />
                  <span className="mono">{id}</span>
                </label>
              ))}
          </div>
        </>
      )}

      {node.type === "tool" && (
        <>
          <div className="field">
            <label>MCP connection</label>
            <select
              value={(node.connection_id as string) || ""}
              onChange={(e) => set({ connection_id: e.target.value, tool_name: "" })}
            >
              <option value="">Select connection…</option>
              {mcpConnections.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Tool</label>
            <select
              value={(node.tool_name as string) || ""}
              onChange={(e) => set({ tool_name: e.target.value })}
            >
              <option value="">Select tool…</option>
              {mcpConnections
                .filter((c) => c.id === node.connection_id)
                .flatMap((c) => c.discovered_tools || [])
                .map((t) => (
                  <option key={t.name} value={t.name}>{t.name}</option>
                ))}
            </select>
          </div>
          <div className="field">
            <label>Arguments (JSON, use $input or $variable)</label>
            <textarea
              rows={3}
              value={JSON.stringify(node.arguments || {}, null, 2)}
              onChange={(e) => {
                try {
                  set({ arguments: JSON.parse(e.target.value) });
                } catch {
                  /* ignore invalid json while typing */
                }
              }}
            />
          </div>
        </>
      )}

      {node.type === "branch" && (
        <>
          <p style={{ color: "var(--muted)", margin: 0, fontSize: "0.8rem" }}>
            Conditions: route == value, variables.key == value, or true
          </p>
          {((node.branches as Array<{ condition?: string; to?: string }>) || []).map((b, i) => (
            <div key={i} style={{ display: "flex", gap: "0.5rem" }}>
              <input
                placeholder="condition"
                value={b.condition || ""}
                onChange={(e) => {
                  const branches = [...((node.branches as Array<{ condition?: string; to?: string }>) || [])];
                  branches[i] = { ...branches[i], condition: e.target.value };
                  set({ branches });
                }}
              />
              <select
                value={b.to || ""}
                onChange={(e) => {
                  const branches = [...((node.branches as Array<{ condition?: string; to?: string }>) || [])];
                  branches[i] = { ...branches[i], to: e.target.value };
                  set({ branches });
                }}
              >
                <option value="">to…</option>
                {nodeIds.filter((id) => id !== node.id).map((id) => (
                  <option key={id} value={id}>{id}</option>
                ))}
              </select>
            </div>
          ))}
          <button
            type="button"
            className="secondary"
            onClick={() =>
              set({
                branches: [
                  ...((node.branches as Array<{ condition?: string; to?: string }>) || []),
                  { condition: "true", to: "" },
                ],
              })
            }
          >
            Add branch
          </button>
          <div className="field">
            <label>Default (if no match)</label>
            <select
              value={(node.default_to as string) || ""}
              onChange={(e) => set({ default_to: e.target.value })}
            >
              <option value="">None</option>
              {nodeIds.filter((id) => id !== node.id).map((id) => (
                <option key={id} value={id}>{id}</option>
              ))}
            </select>
          </div>
        </>
      )}

      {node.type === "parallel" && (
        <div className="field">
          <label>Parallel branch entry nodes</label>
          {nodeIds
            .filter((id) => id !== node.id)
            .map((id) => (
              <label key={id} style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={((node.branches as string[]) || []).includes(id)}
                  onChange={(e) => {
                    const cur = (node.branches as string[]) || [];
                    const branches = e.target.checked ? [...cur, id] : cur.filter((c) => c !== id);
                    set({ branches });
                  }}
                />
                <span className="mono">{id}</span>
              </label>
            ))}
        </div>
      )}

      {node.type === "human" && (
        <div className="field">
          <label>Prompt for human</label>
          <textarea
            rows={3}
            value={(node.prompt as string) || ""}
            onChange={(e) => set({ prompt: e.target.value })}
            placeholder="Approve this output?"
          />
        </div>
      )}
    </div>
  );
}
