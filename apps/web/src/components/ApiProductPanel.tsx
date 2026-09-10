import { useEffect, useState } from "react";
import { Copy, Check, KeyRound } from "lucide-react";
import { api, IntegrationGuide } from "../api";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";

type ResourceType = "agent" | "workflow";

interface ApiProductPanelProps {
  resourceType: ResourceType;
  resourceId: string;
  isPublished: boolean;
  onCreateApiKey?: (resourceId: string) => void;
}

export function ApiProductPanel({
  resourceType,
  resourceId,
  isPublished,
  onCreateApiKey,
}: ApiProductPanelProps) {
  const [guide, setGuide] = useState<IntegrationGuide | null>(null);
  const [activeExample, setActiveExample] = useState("invoke");
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setError("");
    const load = resourceType === "agent"
      ? api.getAgentIntegration(resourceId)
      : api.getWorkflowIntegration(resourceId);
    load
      .then((g) => {
        if (!cancelled) setGuide(g);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load integration guide");
      });
    return () => {
      cancelled = true;
    };
  }, [resourceType, resourceId]);

  const copyText = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (error) {
    return <p className="text-sm text-red-600">{error}</p>;
  }

  if (!guide) {
    return <p className="text-sm text-gray-500">Loading API integration guide…</p>;
  }

  const exampleKeys = Object.keys(guide.examples);
  const exampleText = guide.examples[activeExample] || guide.examples.invoke;

  return (
    <div className="rounded-lg border border-indigo-100 bg-indigo-50/40 p-4 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h4 className="text-sm font-semibold text-gray-900">API product</h4>
          <p className="text-xs text-gray-500 mt-0.5">
            Publish and share this {resourceType} as an async HTTP API.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={isPublished ? "success" : "warning"}>
            {isPublished ? `published v${guide.version}` : "draft — publish to allow API keys"}
          </Badge>
          {onCreateApiKey && (
            <Button type="button" variant="secondary" size="sm" onClick={() => onCreateApiKey(resourceId)}>
              <KeyRound className="h-3.5 w-3.5" />
              Create API key
            </Button>
          )}
        </div>
      </div>

      {!isPublished && (
        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          API keys can only invoke <strong>published</strong> resources. Publish first, then create a scoped key.
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-2 text-xs">
        <div>
          <p className="font-medium text-gray-700">Invoke</p>
          <p className="font-mono text-gray-600">{guide.invoke.method} {guide.invoke.path}</p>
        </div>
        <div>
          <p className="font-medium text-gray-700">Poll status</p>
          <p className="font-mono text-gray-600">{guide.poll_run.method} {guide.poll_run.path}</p>
        </div>
        <div>
          <p className="font-medium text-gray-700">Stream events</p>
          <p className="font-mono text-gray-600">{guide.stream_events.method} {guide.stream_events.path}</p>
        </div>
        {guide.resume && (
          <div>
            <p className="font-medium text-gray-700">Resume (human step)</p>
            <p className="font-mono text-gray-600">{guide.resume.method} {guide.resume.path}</p>
          </div>
        )}
      </div>

      <div>
        <p className="text-xs font-medium text-gray-700 mb-1">Required API key scopes</p>
        <p className="font-mono text-xs text-gray-600">{guide.required_scopes.join(", ")}</p>
      </div>

      <div>
        <p className="text-xs font-medium text-gray-700 mb-1">Authentication</p>
        <ul className="text-xs text-gray-600 space-y-0.5">
          {guide.auth_headers.map((h) => (
            <li key={h} className="font-mono">{h}</li>
          ))}
        </ul>
      </div>

      <div>
        <div className="flex flex-wrap gap-1 mb-2">
          {exampleKeys.map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => setActiveExample(key)}
              className={`px-2 py-1 rounded text-xs font-medium ${
                activeExample === key
                  ? "bg-indigo-600 text-white"
                  : "bg-white text-gray-600 border border-gray-200 hover:bg-gray-50"
              }`}
            >
              {key}
            </button>
          ))}
        </div>
        <div className="relative">
          <pre className="font-mono text-[11px] text-gray-700 bg-white border border-gray-200 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap">
            {exampleText}
          </pre>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="absolute top-2 right-2"
            onClick={() => copyText(exampleText)}
          >
            {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? "Copied" : "Copy"}
          </Button>
        </div>
      </div>

      <div className="text-xs text-gray-500">
        <p className="font-medium text-gray-700 mb-1">Webhook events</p>
        <p>{guide.webhook_events.join(" · ")}</p>
        <p className="mt-2">
          Pass <code className="bg-white px-1 rounded">webhook_url</code> and optional{" "}
          <code className="bg-white px-1 rounded">webhook_secret</code> in the invoke body for push notifications.
        </p>
      </div>
    </div>
  );
}
