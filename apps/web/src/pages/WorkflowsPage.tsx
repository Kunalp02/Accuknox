import { useCallback, useEffect, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  Edge,
  Node,
  addEdge,
  Connection,
  useEdgesState,
  useNodesState,
} from "reactflow";
import "reactflow/dist/style.css";
import { Plus, Trash2 } from "lucide-react";
import { api, Agent, McpConnection, Workflow, streamRunEvents } from "../api";
import { NodeConfigPanel, nodeLabel, WorkflowNodeData } from "../components/WorkflowNodePanel";
import { PageHeader } from "../components/ui/page-header";
import { Card, CardHeader } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Field } from "../components/ui/label";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Select } from "../components/ui/select";
import { cn } from "../lib/cn";

const NODE_TYPES = ["agent", "supervisor", "tool", "branch", "parallel", "human"];

const nodeStyle = {
  background: "#ffffff",
  border: "1px solid #E5E7EB",
  color: "#111827",
  borderRadius: 8,
  padding: 8,
  fontSize: 12,
  minWidth: 120,
  boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
};

function graphToFlow(graph: Workflow["graph"]): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = graph.nodes.map((n, i) => {
    const wn = n as WorkflowNodeData;
    const pos = wn.position || { x: 80 + (i % 3) * 220, y: 60 + Math.floor(i / 3) * 120 };
    return {
      id: wn.id,
      position: pos,
      data: { label: nodeLabel(wn), node: { ...wn, position: pos } },
      style: nodeStyle,
    };
  });
  const edges: Edge[] = graph.edges.map((e, i) => ({
    id: `e${i}`,
    source: e.from,
    target: e.to,
    label: e.condition || undefined,
    style: { stroke: "#4F46E5" },
  }));
  return { nodes, edges };
}

function flowToGraph(nodes: Node[], edges: Edge[], entry: string): Workflow["graph"] {
  return {
    entry,
    nodes: nodes.map((n) => {
      const node = { ...(n.data as { node: WorkflowNodeData }).node };
      node.position = n.position;
      return node;
    }),
    edges: edges.map((e) => ({
      from: e.source,
      to: e.target,
      condition: typeof e.label === "string" && e.label ? e.label : undefined,
    })),
  };
}

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [mcpConnections, setMcpConnections] = useState<McpConnection[]>([]);
  const [selected, setSelected] = useState<Workflow | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [entry, setEntry] = useState("");
  const [newNodeType, setNewNodeType] = useState("agent");
  const [newNodeId, setNewNodeId] = useState("");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [validation, setValidation] = useState<{ valid?: boolean; errors?: string[]; warnings?: string[] } | null>(
    null
  );
  const [testInput, setTestInput] = useState("");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [output, setOutput] = useState("");
  const [events, setEvents] = useState<string[]>([]);
  const [resumeInput, setResumeInput] = useState("");
  const [pendingRunId, setPendingRunId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [invokeLoading, setInvokeLoading] = useState(false);

  const load = async () => {
    const [w, a, m] = await Promise.all([
      api.listWorkflows(),
      api.listAgents(),
      api.listMcpConnections(),
    ]);
    setWorkflows(w);
    setAgents(a);
    setMcpConnections(m);
  };

  useEffect(() => {
    load();
  }, []);

  const selectWorkflow = (wf: Workflow) => {
    setSelected(wf);
    const { nodes: n, edges: e } = graphToFlow(wf.graph);
    setNodes(n);
    setEdges(e);
    setEntry(wf.graph.entry);
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
    setValidation(null);
    setOutput("");
    setEvents([]);
    setPendingRunId(null);
  };

  const onConnect = useCallback(
    (params: Connection) =>
      setEdges((eds) => addEdge({ ...params, style: { stroke: "#4F46E5" } }, eds)),
    [setEdges]
  );

  const updateNodeData = (nodeId: string, updated: WorkflowNodeData) => {
    setNodes((nds) =>
      nds.map((n) =>
        n.id === nodeId
          ? {
              ...n,
              data: { label: nodeLabel(updated), node: updated },
              style: {
                ...n.style,
                borderColor: "#4F46E5",
              },
            }
          : n
      )
    );
  };

  const save = async () => {
    if (!selected) return;
    const graph = flowToGraph(nodes, edges, entry || nodes[0]?.id || "");
    const updated = await api.updateWorkflow(selected.id, { graph });
    setSelected(updated);
    await load();
    setValidation(null);
  };

  const validate = async () => {
    if (!selected) return;
    await save();
    const result = await api.validateWorkflow(selected.id);
    setValidation(result);
  };

  const deleteSelected = async () => {
    if (!selected || !confirm(`Delete workflow "${selected.name}"?`)) return;
    await api.deleteWorkflow(selected.id);
    setSelected(null);
    setNodes([]);
    setEdges([]);
    await load();
  };

  const addNode = () => {
    const id = newNodeId || `${newNodeType}_${nodes.length + 1}`;
    const base: WorkflowNodeData = { id, type: newNodeType };
    if (newNodeType === "agent" && agents[0]) base.agent_id = agents[0].id;
    if (newNodeType === "supervisor") base.children = [];
    if (newNodeType === "parallel") base.branches = [];
    if (newNodeType === "branch") base.branches = [{ condition: "true", to: "" }];
    if (newNodeType === "human") base.prompt = "Approve?";
    const position = { x: 100 + nodes.length * 40, y: 100 + nodes.length * 30 };
    base.position = position;
    setNodes((nds) => [
      ...nds,
      {
        id,
        position,
        data: { label: nodeLabel(base), node: base },
        style: nodeStyle,
      },
    ]);
    if (!entry) setEntry(id);
    setNewNodeId("");
    setSelectedNodeId(id);
  };

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);
  const selectedEdge = edges.find((e) => e.id === selectedEdgeId);
  const nodeIds = nodes.map((n) => n.id);

  const deleteNode = (nodeId: string) => {
    setNodes((nds) => nds.filter((n) => n.id !== nodeId));
    setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
    if (entry === nodeId) setEntry("");
    if (selectedNodeId === nodeId) setSelectedNodeId(null);
  };

  const invoke = async () => {
    if (!selected || !testInput.trim()) return;
    setOutput("");
    setEvents([]);
    setInvokeLoading(true);
    try {
      await save();
      const { run_id } = await api.invokeWorkflow(selected.id, {
        input: testInput,
        webhook_url: webhookUrl.trim() || undefined,
        webhook_secret: webhookSecret.trim() || undefined,
      });
      setEvents((e) => [...e, `started ${run_id}`]);
      streamRunEvents(run_id, (type, data) => {
        setEvents((e) => [...e, `${type}: ${JSON.stringify(data)}`]);
        if (type === "run.completed" && data && typeof data === "object" && "message" in data) {
          setOutput(String((data as { message: string }).message));
        }
        if (type === "run.failed" && data && typeof data === "object" && "error" in data) {
          setOutput(String((data as { error: string }).error));
        }
        if (type === "run.awaiting_input") setPendingRunId(run_id);
      });
      const poll = setInterval(async () => {
        const run = await api.getRun(run_id);
        if (run.status === "completed") {
          clearInterval(poll);
          if (run.output?.message) setOutput(run.output.message);
          setInvokeLoading(false);
        } else if (run.status === "failed") {
          clearInterval(poll);
          setOutput(run.error || "failed");
          setInvokeLoading(false);
        } else if (run.status === "awaiting_input") {
          clearInterval(poll);
          setPendingRunId(run_id);
          setOutput("Awaiting human input...");
          setInvokeLoading(false);
        }
      }, 1500);
    } catch (err) {
      setOutput(err instanceof Error ? err.message : "Invoke failed");
      setInvokeLoading(false);
    }
  };

  const resume = async () => {
    if (!pendingRunId || !resumeInput.trim()) return;
    const { run_id } = await api.resumeRun(pendingRunId, resumeInput);
    setPendingRunId(null);
    const poll = setInterval(async () => {
      const run = await api.getRun(run_id);
      if (run.status === "completed") {
        clearInterval(poll);
        if (run.output?.message) setOutput(run.output.message);
      }
    }, 1500);
  };

  return (
    <div>
      <PageHeader
        title="Workflows"
        description="Click a node to configure it. Connect edges and set conditions for supervisor routes."
      />

      <div className="grid gap-5 lg:grid-cols-[220px_1fr_280px]">
        <Card>
          <CardHeader title="Workflows" />
          <div className="space-y-1">
            {workflows.map((w) => (
              <button
                key={w.id}
                type="button"
                onClick={() => selectWorkflow(w)}
                className={cn(
                  "flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left text-sm transition-colors",
                  selected?.id === w.id ? "bg-primary-subtle text-primary" : "hover:bg-gray-50 text-gray-700"
                )}
              >
                <span className="font-medium">{w.name}</span>
                <Badge variant={w.is_published ? "success" : "default"}>
                  {w.is_published ? `v${w.version}` : "draft"}
                </Badge>
              </button>
            ))}
          </div>
          <Button
            type="button"
            size="sm"
            className="mt-4"
            onClick={async () => {
              const wf = await api.createWorkflow({ name: `Workflow ${workflows.length + 1}` });
              await load();
              selectWorkflow(wf);
            }}
          >
            <Plus className="h-4 w-4" />
            New workflow
          </Button>
        </Card>

        <Card padding="sm">
          {selected ? (
            <div className="space-y-3 p-2">
              <div className="flex flex-wrap items-center gap-2">
                <strong className="text-sm text-gray-900">{selected.name}</strong>
                <Select value={newNodeType} onChange={(e) => setNewNodeType(e.target.value)} className="w-auto min-w-[100px]">
                  {NODE_TYPES.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </Select>
                <Input
                  placeholder="node id"
                  value={newNodeId}
                  onChange={(e) => setNewNodeId(e.target.value)}
                  className="w-24"
                />
                <Button type="button" variant="secondary" size="sm" onClick={addNode}>Add</Button>
                <Button type="button" size="sm" onClick={save}>Save</Button>
                <Button type="button" variant="secondary" size="sm" onClick={validate}>Validate</Button>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => api.publishWorkflow(selected.id).then(load)}
                >
                  Publish
                </Button>
                <Button type="button" variant="danger" size="sm" onClick={deleteSelected}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>

              <Field label="Entry node">
                <Select value={entry} onChange={(e) => setEntry(e.target.value)}>
                  {nodeIds.map((id) => (
                    <option key={id} value={id}>{id}</option>
                  ))}
                </Select>
              </Field>

              {validation && (
                <div className="text-sm">
                  {validation.valid ? (
                    <p className="text-emerald-600">Graph is valid</p>
                  ) : (
                    <ul className="text-red-600 list-disc pl-4">
                      {validation.errors?.map((err) => <li key={err}>{err}</li>)}
                    </ul>
                  )}
                  {validation.warnings?.map((w) => (
                    <p key={w} className="text-gray-500">{w}</p>
                  ))}
                </div>
              )}

              <div className="h-[380px] rounded-lg border border-border overflow-hidden">
                <ReactFlow
                  nodes={nodes.map((n) => ({
                    ...n,
                    style: {
                      ...n.style,
                      borderColor: n.id === selectedNodeId ? "#4F46E5" : "#E5E7EB",
                      borderWidth: n.id === selectedNodeId ? 2 : 1,
                    },
                  }))}
                  edges={edges.map((e) => ({
                    ...e,
                    style: {
                      stroke: e.id === selectedEdgeId ? "#10B981" : "#4F46E5",
                      strokeWidth: e.id === selectedEdgeId ? 2 : 1,
                    },
                  }))}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  onConnect={onConnect}
                  onNodeClick={(_, n) => {
                    setSelectedNodeId(n.id);
                    setSelectedEdgeId(null);
                  }}
                  onEdgeClick={(_, e) => {
                    setSelectedEdgeId(e.id);
                    setSelectedNodeId(null);
                  }}
                  fitView
                >
                  <Background color="#E5E7EB" gap={16} />
                  <Controls />
                </ReactFlow>
              </div>

              <Textarea rows={2} placeholder="Test input…" value={testInput} onChange={(e) => setTestInput(e.target.value)} />
              <div className="grid gap-2 sm:grid-cols-2">
                <Field label="Webhook URL (optional)">
                  <Input value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} placeholder="https://..." />
                </Field>
                <Field label="Webhook secret">
                  <Input type="password" value={webhookSecret} onChange={(e) => setWebhookSecret(e.target.value)} />
                </Field>
              </div>
              <Button type="button" size="sm" onClick={invoke} disabled={invokeLoading || !testInput.trim()}>
                {invokeLoading ? "Running…" : "Invoke"}
              </Button>
              {pendingRunId && (
                <div className="space-y-2">
                  <Input placeholder="Human response…" value={resumeInput} onChange={(e) => setResumeInput(e.target.value)} />
                  <Button type="button" size="sm" onClick={resume}>Resume</Button>
                </div>
              )}
              <div className="min-h-[60px] rounded-lg border border-border bg-gray-50 p-3 text-sm">
                {output || "…"}
              </div>
              {events.length > 0 && (
                <pre className="max-h-32 overflow-y-auto rounded-lg border border-border bg-gray-50 p-2 font-mono text-[11px] text-gray-500 whitespace-pre-wrap">
                  {events.join("\n")}
                </pre>
              )}
            </div>
          ) : (
            <p className="p-4 text-sm text-gray-500">Select or create a workflow</p>
          )}
        </Card>

        <Card>
          <CardHeader title="Inspector" />
          {selectedNode && selectedNodeId ? (
            <div className="space-y-4">
              <NodeConfigPanel
                node={(selectedNode.data as { node: WorkflowNodeData }).node}
                nodeIds={nodeIds}
                agents={agents}
                mcpConnections={mcpConnections}
                onChange={(updated) => updateNodeData(selectedNodeId, updated)}
              />
              <Button type="button" variant="danger" size="sm" onClick={() => deleteNode(selectedNodeId)}>
                Delete node
              </Button>
            </div>
          ) : selectedEdge && selectedEdgeId ? (
            <div className="space-y-3">
              <p className="font-mono text-sm text-gray-600">
                {selectedEdge.source} → {selectedEdge.target}
              </p>
              <Field label="Edge condition">
                <Input
                  value={typeof selectedEdge.label === "string" ? selectedEdge.label : ""}
                  onChange={(e) => {
                    const label = e.target.value;
                    setEdges((eds) =>
                      eds.map((edge) =>
                        edge.id === selectedEdgeId ? { ...edge, label } : edge
                      )
                    );
                  }}
                  placeholder="route == researcher"
                />
              </Field>
              <p className="text-xs text-gray-500">
                Used by supervisor routing and branch nodes. Leave empty for unconditional flow.
              </p>
            </div>
          ) : (
            <p className="text-sm text-gray-500">Select a node or edge on the graph</p>
          )}
        </Card>
      </div>
    </div>
  );
}
