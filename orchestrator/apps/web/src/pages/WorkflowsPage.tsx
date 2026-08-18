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
import { api, Agent, Workflow, streamRunEvents } from "../api";

const NODE_TYPES = ["agent", "supervisor", "tool", "branch", "parallel", "human"];

function graphToFlow(graph: Workflow["graph"]): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = graph.nodes.map((n, i) => ({
    id: n.id as string,
    position: { x: 80 + (i % 3) * 220, y: 60 + Math.floor(i / 3) * 120 },
    data: { label: `${n.type}: ${n.id}`, node: n },
    type: "default",
    style: {
      background: "#1c2430",
      border: "1px solid #2a3544",
      color: "#e8edf4",
      borderRadius: 8,
      padding: 8,
      fontSize: 12,
    },
  }));
  const edges: Edge[] = graph.edges.map((e, i) => ({
    id: `e${i}`,
    source: e.from,
    target: e.to,
    label: e.condition || undefined,
    style: { stroke: "#3d8bfd" },
  }));
  return { nodes, edges };
}

function flowToGraph(
  nodes: Node[],
  edges: Edge[],
  entry: string
): Workflow["graph"] {
  return {
    entry,
    nodes: nodes.map((n) => (n.data as { node: Record<string, unknown> }).node),
    edges: edges.map((e) => ({
      from: e.source,
      to: e.target,
      condition: typeof e.label === "string" ? e.label : undefined,
    })),
  };
}

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selected, setSelected] = useState<Workflow | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [entry, setEntry] = useState("");
  const [newNodeType, setNewNodeType] = useState("agent");
  const [newNodeId, setNewNodeId] = useState("");
  const [testInput, setTestInput] = useState("");
  const [output, setOutput] = useState("");
  const [events, setEvents] = useState<string[]>([]);
  const [resumeInput, setResumeInput] = useState("");
  const [pendingRunId, setPendingRunId] = useState<string | null>(null);

  const load = async () => {
    const [w, a] = await Promise.all([api.listWorkflows(), api.listAgents()]);
    setWorkflows(w);
    setAgents(a);
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
    setOutput("");
    setEvents([]);
    setPendingRunId(null);
  };

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge({ ...params, style: { stroke: "#3d8bfd" } }, eds)),
    [setEdges]
  );

  const save = async () => {
    if (!selected) return;
    const graph = flowToGraph(nodes, edges, entry || nodes[0]?.id || "");
    const updated = await api.updateWorkflow(selected.id, { graph });
    setSelected(updated);
    await load();
  };

  const addNode = () => {
    const id = newNodeId || `${newNodeType}_${nodes.length + 1}`;
    const base: Record<string, unknown> = { id, type: newNodeType };
    if (newNodeType === "agent" && agents[0]) base.agent_id = agents[0].id;
    if (newNodeType === "supervisor") base.children = [];
    if (newNodeType === "parallel") base.branches = [];
    if (newNodeType === "human") base.prompt = "Approve?";
    setNodes((nds) => [
      ...nds,
      {
        id,
        position: { x: 100 + nds.length * 40, y: 100 + nds.length * 30 },
        data: { label: `${newNodeType}: ${id}`, node: base },
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
  };

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
      if (type === "run.awaiting_input") {
        setPendingRunId(run_id);
      }
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
    setEvents((e) => [...e, `resumed ${run_id}`]);
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
      <div className="grid-2">
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
              <h3 style={{ margin: 0 }}>{selected.name}</h3>
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                <select value={newNodeType} onChange={(e) => setNewNodeType(e.target.value)}>
                  {NODE_TYPES.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
                <input placeholder="node id" value={newNodeId} onChange={(e) => setNewNodeId(e.target.value)} style={{ width: 120 }} />
                <button type="button" className="secondary" onClick={addNode}>Add node</button>
                <button type="button" onClick={save}>Save graph</button>
                <button type="button" className="secondary" onClick={() => api.publishWorkflow(selected.id).then(load)}>
                  Publish
                </button>
              </div>
              <div className="field">
                <label>Entry node</label>
                <input value={entry} onChange={(e) => setEntry(e.target.value)} />
              </div>
              <div style={{ height: 360, border: "1px solid var(--border)", borderRadius: 10 }}>
                <ReactFlow
                  nodes={nodes}
                  edges={edges}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  onConnect={onConnect}
                  fitView
                >
                  <Background color="#2a3544" />
                  <Controls />
                </ReactFlow>
              </div>
              <textarea rows={2} placeholder="Test input..." value={testInput} onChange={(e) => setTestInput(e.target.value)} />
              <button type="button" onClick={invoke}>Invoke workflow</button>
              {pendingRunId && (
                <div className="stack">
                  <input placeholder="Human response..." value={resumeInput} onChange={(e) => setResumeInput(e.target.value)} />
                  <button type="button" onClick={resume}>Resume run</button>
                </div>
              )}
              <div className="chat-output">{output || "..."}</div>
              <div className="events-log">{events.join("\n")}</div>
            </>
          ) : (
            <p style={{ color: "var(--muted)" }}>Select or create a workflow</p>
          )}
        </div>
      </div>
    </div>
  );
}
