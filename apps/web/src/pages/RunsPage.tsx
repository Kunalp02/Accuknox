import { useEffect, useState } from "react";
import { api, Run } from "../api";
import { PageHeader } from "../components/ui/page-header";
import { Card, CardHeader } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { cn } from "../lib/cn";

function statusVariant(status: string): "success" | "danger" | "warning" | "default" {
  if (status === "completed") return "success";
  if (status === "failed") return "danger";
  if (status === "running" || status === "awaiting_input") return "warning";
  return "default";
}

function TraceTimeline({ trace }: { trace: Run["trace"] }) {
  if (!trace?.length) return <p className="text-sm text-gray-500">No trace events</p>;

  return (
    <div className="max-h-[420px] space-y-2 overflow-y-auto">
      {trace.map((entry, i) => (
        <div key={i} className="rounded-lg border border-border p-3">
          <div className="mb-2 flex items-center gap-2">
            <Badge
              variant={
                entry.type.includes("failed")
                  ? "danger"
                  : entry.type.includes("completed")
                    ? "success"
                    : "primary"
              }
            >
              {entry.type}
            </Badge>
            <span className="font-mono text-xs text-gray-400">
              {entry.ts ? new Date(entry.ts).toLocaleTimeString() : ""}
            </span>
          </div>
          <pre className="font-mono text-[11px] text-gray-500 whitespace-pre-wrap max-h-28 overflow-y-auto">
            {JSON.stringify(entry.data, null, 2)}
          </pre>
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
    <div>
      <PageHeader title="Runs" description="Inspect execution traces, metrics, and outputs." />

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="Recent runs" />
          {runs.length === 0 && <p className="text-sm text-gray-500">No runs yet</p>}
          <div className="space-y-1">
            {runs.map((run) => (
              <button
                key={run.id}
                type="button"
                onClick={() => open(run)}
                className={cn(
                  "w-full rounded-lg px-3 py-3 text-left transition-colors",
                  selected?.id === run.id ? "bg-primary-subtle" : "hover:bg-gray-50"
                )}
              >
                <div className="flex items-center gap-2">
                  <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
                  <span className="font-mono text-xs text-gray-500">{run.id.slice(0, 8)}...</span>
                </div>
                <p className="mt-1 text-sm text-gray-500 truncate">
                  {run.input?.message?.slice(0, 80) || "—"}
                </p>
              </button>
            ))}
          </div>
        </Card>

        <Card>
          {selected ? (
            <div className="space-y-4">
              <CardHeader title="Run trace" />
              <p className="font-mono text-xs text-gray-500">{selected.id}</p>
              <div className="flex gap-2">
                <Badge variant={statusVariant(selected.status)}>{selected.status}</Badge>
                {selected.agent_id && <Badge>agent</Badge>}
                {selected.workflow_id && <Badge>workflow</Badge>}
              </div>
              <div className="text-sm space-y-1">
                <p><span className="font-medium">Input:</span> {selected.input?.message || "—"}</p>
                {selected.output?.message && (
                  <p><span className="font-medium">Output:</span> {selected.output.message.slice(0, 500)}</p>
                )}
              </div>
              {selected.error && <p className="text-sm text-red-600">{selected.error}</p>}
              {selected.metrics && (
                <p className="font-mono text-xs text-gray-500">
                  tokens in: {selected.metrics.tokens_in || 0} · out: {selected.metrics.tokens_out || 0}
                  {selected.metrics.steps ? ` · steps: ${selected.metrics.steps}` : ""}
                </p>
              )}
              <div className="border-t border-border pt-4">
                <h4 className="mb-3 text-sm font-semibold text-gray-900">Timeline</h4>
                <TraceTimeline trace={selected.trace} />
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-500">Select a run to view trace</p>
          )}
        </Card>
      </div>
    </div>
  );
}
