import type { Agent, McpConnection } from "../api";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Field } from "./ui/label";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import { Select } from "./ui/select";

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
    <div className="space-y-4 text-sm">
      <div className="flex items-center gap-2">
        <Badge variant="primary">{node.type}</Badge>
        <span className="font-mono text-xs text-gray-500">{node.id}</span>
      </div>

      {node.type === "agent" && (
        <Field label="Agent">
          <Select
            value={(node.agent_id as string) || ""}
            onChange={(e) => set({ agent_id: e.target.value })}
          >
            <option value="">Select agent…</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </Select>
        </Field>
      )}

      {node.type === "supervisor" && (
        <>
          <Field label="Routing prompt (optional)">
            <Textarea
              rows={3}
              value={(node.system_prompt as string) || ""}
              onChange={(e) => set({ system_prompt: e.target.value })}
              placeholder="You are a supervisor. Route to the best child node id…"
            />
          </Field>
          <Field label="Model (optional)">
            <Input
              value={(node.model as string) || ""}
              onChange={(e) => set({ model: e.target.value })}
              placeholder="llama3.2"
            />
          </Field>
          <Field label="Child nodes (routing targets)">
            <div className="space-y-2">
              {nodeIds
                .filter((id) => id !== node.id)
                .map((id) => (
                  <label key={id} className="flex items-center gap-2 text-gray-700">
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
                      className="rounded border-gray-300 text-primary focus:ring-primary"
                    />
                    <span className="font-mono text-xs">{id}</span>
                  </label>
                ))}
            </div>
          </Field>
        </>
      )}

      {node.type === "tool" && (
        <>
          <Field label="MCP connection">
            <Select
              value={(node.connection_id as string) || ""}
              onChange={(e) => set({ connection_id: e.target.value, tool_name: "" })}
            >
              <option value="">Select connection…</option>
              {mcpConnections.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </Select>
          </Field>
          <Field label="Tool">
            <Select
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
            </Select>
          </Field>
          <Field label="Arguments (JSON, use $input or $variable)">
            <Textarea
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
          </Field>
        </>
      )}

      {node.type === "branch" && (
        <>
          <p className="text-xs text-gray-500">
            Conditions: route == value, variables.key == value, or true
          </p>
          {((node.branches as Array<{ condition?: string; to?: string }>) || []).map((b, i) => (
            <div key={i} className="flex gap-2">
              <Input
                placeholder="condition"
                value={b.condition || ""}
                onChange={(e) => {
                  const branches = [...((node.branches as Array<{ condition?: string; to?: string }>) || [])];
                  branches[i] = { ...branches[i], condition: e.target.value };
                  set({ branches });
                }}
              />
              <Select
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
              </Select>
            </div>
          ))}
          <Button
            type="button"
            variant="secondary"
            size="sm"
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
          </Button>
          <Field label="Default (if no match)">
            <Select
              value={(node.default_to as string) || ""}
              onChange={(e) => set({ default_to: e.target.value })}
            >
              <option value="">None</option>
              {nodeIds.filter((id) => id !== node.id).map((id) => (
                <option key={id} value={id}>{id}</option>
              ))}
            </Select>
          </Field>
        </>
      )}

      {node.type === "parallel" && (
        <Field label="Parallel branch entry nodes">
          <div className="space-y-2">
            {nodeIds
              .filter((id) => id !== node.id)
              .map((id) => (
                <label key={id} className="flex items-center gap-2 text-gray-700">
                  <input
                    type="checkbox"
                    checked={((node.branches as string[]) || []).includes(id)}
                    onChange={(e) => {
                      const cur = (node.branches as string[]) || [];
                      const branches = e.target.checked ? [...cur, id] : cur.filter((c) => c !== id);
                      set({ branches });
                    }}
                    className="rounded border-gray-300 text-primary focus:ring-primary"
                  />
                  <span className="font-mono text-xs">{id}</span>
                </label>
              ))}
          </div>
        </Field>
      )}

      {node.type === "human" && (
        <Field label="Prompt for human">
          <Textarea
            rows={3}
            value={(node.prompt as string) || ""}
            onChange={(e) => set({ prompt: e.target.value })}
            placeholder="Approve this output?"
          />
        </Field>
      )}
    </div>
  );
}
