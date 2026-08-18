import { useEffect, useState } from "react";
import { api, Run } from "../api";

export default function RunsPage() {
  const [runs, setRuns] = useState<Run[]>([]);

  useEffect(() => {
    api.listRuns().then(setRuns);
  }, []);

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>Runs</h2>
      <div className="card stack">
        {runs.length === 0 && <p style={{ color: "var(--muted)" }}>No runs yet</p>}
        {runs.map((run) => (
          <div
            key={run.id}
            style={{
              padding: "0.75rem",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
            }}
          >
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <span className={`badge ${run.status === "completed" ? "success" : run.status === "failed" ? "failed" : "pending"}`}>
                {run.status}
              </span>
              <span className="mono">{run.id.slice(0, 8)}...</span>
            </div>
            <p style={{ margin: "0.5rem 0 0", color: "var(--muted)" }}>
              Input: {run.input?.message || "—"}
            </p>
            {run.output?.message && (
              <p style={{ margin: "0.25rem 0 0" }}>Output: {run.output.message.slice(0, 200)}</p>
            )}
            {run.error && <p style={{ color: "var(--danger)" }}>{run.error}</p>}
            {run.metrics?.tokens_in && (
              <p className="mono" style={{ color: "var(--muted)", margin: "0.25rem 0 0" }}>
                tokens in: {run.metrics.tokens_in} · out: {run.metrics.tokens_out}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
