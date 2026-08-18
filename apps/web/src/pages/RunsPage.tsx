import { useEffect, useState } from "react";
import { api, Run } from "../api";

function TraceTimeline({ trace }: { trace: Run["trace"] }) {
  if (!trace?.length) return <p style={{ color: "var(--muted)", fontSize: "0.85rem" }}>No trace events</p>;

  return (
    <div className="trace-timeline">
      {trace.map((entry, i) => (
        <div key={i} className="trace-entry">
          <div className="trace-meta">
            <span className={`badge ${entry.type.includes("failed") ? "failed" : entry.type.includes("completed") ? "success" : "pending"}`}>
              {entry.type}
            </span>
            <span className="mono" style={{ color: "var(--muted)", fontSize: "0.75rem" }}>
              {entry.ts ? new Date(entry.ts).toLocaleTimeString() : ""}
            </span>
          </div>
          <pre className="trace-data">{JSON.stringify(entry.data, null, 2)}</pre>
        </div>
      ))}
    </div>
  );
}

export default function RunsPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [selected, setSelected] = useState<Run | null>(null);

  useEffect(() => {
    api.listRuns().then(setRuns);
  }, []);

  const open = async (run: Run) => {
    const full = await api.getRun(run.id);
    setSelected(full);
  };

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>Runs</h2>
      <div className="grid-2">
        <div className="card stack">
          {runs.length === 0 && <p style={{ color: "var(--muted)" }}>No runs yet</p>}
          {runs.map((run) => (
            <button
              key={run.id}
              type="button"
              className="secondary"
              onClick={() => open(run)}
              style={{
                textAlign: "left",
                borderColor: selected?.id === run.id ? "var(--accent)" : undefined,
              }}
            >
              <span className={`badge ${run.status === "completed" ? "success" : run.status === "failed" ? "failed" : "pending"}`}>
                {run.status}
              </span>
              <span className="mono" style={{ marginLeft: "0.5rem" }}>{run.id.slice(0, 8)}...</span>
              <div style={{ color: "var(--muted)", fontSize: "0.85rem", marginTop: "0.25rem" }}>
                {run.input?.message?.slice(0, 80) || "—"}
              </div>
            </button>
          ))}
        </div>
        <div className="card stack">
          {selected ? (
            <>
              <h3 style={{ margin: 0 }}>Run trace</h3>
              <p className="mono" style={{ color: "var(--muted)", margin: 0, fontSize: "0.85rem" }}>{selected.id}</p>
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <span className={`badge ${selected.status === "completed" ? "success" : selected.status === "failed" ? "failed" : "pending"}`}>
                  {selected.status}
                </span>
                {selected.agent_id && <span className="badge">agent</span>}
                {selected.workflow_id && <span className="badge">workflow</span>}
              </div>
              <p style={{ margin: "0.5rem 0 0" }}>
                <strong>Input:</strong> {selected.input?.message || "—"}
              </p>
              {selected.output?.message && (
                <p style={{ margin: "0.25rem 0 0" }}>
                  <strong>Output:</strong> {selected.output.message.slice(0, 500)}
                </p>
              )}
              {selected.error && <p style={{ color: "var(--danger)" }}>{selected.error}</p>}
              {selected.metrics && (
                <p className="mono" style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
                  tokens in: {selected.metrics.tokens_in || 0} · out: {selected.metrics.tokens_out || 0}
                  {selected.metrics.steps ? ` · steps: ${selected.metrics.steps}` : ""}
                </p>
              )}
              <hr style={{ border: "none", borderTop: "1px solid var(--border)" }} />
              <h4 style={{ margin: 0 }}>Timeline</h4>
              <TraceTimeline trace={selected.trace} />
            </>
          ) : (
            <p style={{ color: "var(--muted)" }}>Select a run to view trace</p>
          )}
        </div>
      </div>
    </div>
  );
}
