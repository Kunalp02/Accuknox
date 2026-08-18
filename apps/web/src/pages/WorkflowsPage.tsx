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
import { api, Agent, McpConnection, Workflow, streamRunEvents } from "../api";
import { NodeConfigPanel, nodeLabel, WorkflowNodeData } from "../components/WorkflowNodePanel";

const NODE_TYPES = ["agent", "supervisor", "tool", "branch", "parallel", "human"];

function graphToFlow(graph: Workflow["graph"]): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = graph.nodes.map((n, i) => {
    const wn = n as WorkflowNodeData;
    const pos = wn.position || { x: 80 + (i % 3) * 220, y: 60 + Math.floor(i / 3) * 120 };
    return {
      id: wn.id,
      position: pos,
      data: { label: nodeLabel(wn), node: { ...wn, position: pos } },
      style: {
        background: "#1c2430",
        border: "1px solid #2a3544",
        color: "#e8edf4",
        borderRadius: 8,
        padding: 8,
        fontSize: 12,
        minWidth: 120,
      },
    };
  });
  const edges: Edge[] = graph.edges.map((e, i) => ({
    id: `e${i}`,
    source: e.from,
    target: e.to,
    label: e.condition || undefined,
    style: { stroke: "#3d8bfd" },
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
  const [output, setOutput] = useState("");
  const [events, setEvents] = useState<string[]>([]);
  const [resumeInput, setResumeInput] = useState("");
  const [pendingRunId, setPendingRunId] = useState<string | null>(null);

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
      setEdges((eds) => addEdge({ ...params, style: { stroke: "#3d8bfd" } }, eds)),
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
                borderColor: "var(--accent)",
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
        style: {
          background: "#1c2430",
          border: "1px solid #2a3544",
          color: "#e8edf4",
          borderRadius: 8,
          padding: 8,
          fontSize: 12,
        },
      },
    ]);
    if (!entry) setEntry(id);
    setNewNodeId("");
    setSelectedNodeId(id);
  };

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);
  const selectedEdge = edges.find((e) => e.id === selectedEdgeId);
  const nodeIds = nodes.map((n) => n.id);

  const invoke = async () => {
    if (!selected || !testInput.trim()) return;
    setOutput("");
    setEvents([]);
    const { run_id } = await api.invokeWorkflow(selected.id, testInput);
    setEvents((e) => [...e, `started ${run_id}`]);
    streamRunEvents(run_id, (type, data) => {
      setEvents((e) => [...e, `${type}: ${JSON.stringify(data)}`]);
      if (type === "run.completed" && data && typeof data === "object" && "message" in data) {
        setOutput(String((data as { message: string }).message));
      }
      if (type === "run.awaiting_input") setPendingRunId(run_id);
    });
    const poll = setInterval(async () => {
      const run = await api.getRun(run_id);
      if (run.status === "completed") {
        clearInterval(poll);
        if (run.output?.message) setOutput(run.output.message);
      } else if (run.status === "failed") {
        clearInterval(poll);
        setOutput(run.error || "failed");
      } else if (run.status === "awaiting_input") {
        clearInterval(poll);
        setPendingRunId(run_id);
        setOutput("Awaiting human input...");
      }
    }, 1500);
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
    <div className="stack">
      <h2 style={{ margin: 0 }}>Workflows</h2>
      <p style={{ color: "var(--muted)", margin: 0 }}>
        Click a node to configure it. Connect edges and set conditions for supervisor routes.
      </p>
      <div className="workflow-layout" style={{ display: "grid", gridTemplateColumns: "220px 1fr 280px", gap: "1rem" }}>
        <div className="card stack">
          <h3 style={{ margin: 0 }}>Workflows</h3>
          {workflows.map((w) => (
            <button key={w.id} type="button" className="secondary" onClick={() => selectWorkflow(w)}>
              {w.name}{" "}
              <span className={`badge ${w.is_published ? "success" : ""}`}>
                {w.is_published ? `v${w.version}` : "draft"}
              </span>
            </button>
          ))}
          <button
            type="button"
            onClick={async () => {
              const wf = await api.createWorkflow({ name: `Workflow ${workflows.length + 1}` });
              await load();
              selectWorkflow(wf);
            }}
          >
            New workflow
          </button>
        </div>

        <div className="card stack">
          {selected ? (
            <>
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
                <strong>{selected.name}</strong>
                <select value={newNodeType} onChange={(e) => setNewNodeType(e.target.value)}>
                  {NODE_TYPES.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
                <input
                  placeholder="node id"
                  value={newNodeId}
                  onChange={(e) => setNewNodeId(e.target.value)}
                  style={{ width: 100 }}
                />
                <button type="button" className="secondary" onClick={addNode}>Add</button>
                <button type="button" onClick={save}>Save</button>
                <button type="button" className="secondary" onClick={validate}>Validate</button>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => api.publishWorkflow(selected.id).then(load)}
                >
                  Publish
                </button>
              </div>
              <div className="field">
                <label>Entry node</label>
                <select value={entry} onChange={(e) => setEntry(e.target.value)}>
                  {nodeIds.map((id) => (
                    <option key={id} value={id}>{id}</option>
                  ))}
                </select>
              </div>
              {validation && (
                <div style={{ fontSize: "0.85rem" }}>
                  {validation.valid ? (
                    <p style={{ color: "var(--success)", margin: 0 }}>Graph is valid</p>
                  ) : (
                    <ul style={{ color: "var(--danger)", margin: 0, paddingLeft: "1.2rem" }}>
                      {validation.errors?.map((err) => <li key={err}>{err}</li>)}
                    </ul>
                  )}
                  {validation.warnings?.map((w) => (
                    <p key={w} style={{ color: "var(--muted)", margin: "0.25rem 0" }}>{w}</p>
                  ))}
                </div>
              )}
              <div style={{ height: 380, border: "1px solid var(--border)", borderRadius: 10 }}>
                <ReactFlow
                  nodes={nodes.map((n) => ({
                    ...n,
                    style: {
                      ...n.style,
                      borderColor: n.id === selectedNodeId ? "var(--accent)" : "#2a3544",
                      borderWidth: n.id === selectedNodeId ? 2 : 1,
                    },
                  }))}
                  edges={edges.map((e) => ({
                    ...e,
                    style: {
                      stroke: e.id === selectedEdgeId ? "var(--success)" : "#3d8bfd",
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
                  <Background color="#2a3544" />
                  <Controls />
                </ReactFlow>
              </div>
              <textarea rows={2} placeholder="Test input…" value={testInput} onChange={(e) => setTestInput(e.target.value)} />
              <button type="button" onClick={invoke}>Invoke</button>
              {pendingRunId && (
                <div className="stack">
                  <input placeholder="Human response…" value={resumeInput} onChange={(e) => setResumeInput(e.target.value)} />
                  <button type="button" onClick={resume}>Resume</button>
                </div>
              )}
              <div className="chat-output">{output || "…"}</div>
            </>
          ) : (
            <p style={{ color: "var(--muted)" }}>Select or create a workflow</p>
          )}
        </div>

        <div className="card stack">
          <h3 style={{ margin: 0 }}>Inspector</h3>
          {selectedNode && selectedNodeId ? (
            <NodeConfigPanel
              node={(selectedNode.data as { node: WorkflowNodeData }).node}
              nodeIds={nodeIds}
              agents={agents}
              mcpConnections={mcpConnections}
              onChange={(updated) => updateNodeData(selectedNodeId, updated)}
            />
          ) : selectedEdge && selectedEdgeId ? (
            <div className="stack">
              <p className="mono" style={{ margin: 0, fontSize: "0.85rem" }}>
                {selectedEdge.source} → {selectedEdge.target}
              </p>
              <div className="field">
                <label>Edge condition</label>
                <input
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
              </div>
              <p style={{ color: "var(--muted)", fontSize: "0.8rem", margin: 0 }}>
                Used by supervisor routing and branch nodes. Leave empty for unconditional flow.
              </p>
            </div>
          ) : (
            <p style={{ color: "var(--muted)" }}>Select a node or edge on the graph</p>
          )}
        </div>
      </div>
    </div>
  );
}
