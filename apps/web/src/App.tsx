import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { GitBranch } from "lucide-react";
import { api, clearToken, getToken, setToken } from "./api";
import AgentsPage from "./pages/AgentsPage";
import RunsPage from "./pages/RunsPage";
import KnowledgePage from "./pages/KnowledgePage";
import ApiKeysPage from "./pages/ApiKeysPage";
import WorkflowsPage from "./pages/WorkflowsPage";
import McpPage from "./pages/McpPage";
import SettingsPage from "./pages/SettingsPage";
import { AppShell } from "./components/layout/AppShell";
import { PageLoader } from "./components/ui/spinner";
import { Button } from "./components/ui/button";
import { Card } from "./components/ui/card";
import { Field } from "./components/ui/label";
import { Input } from "./components/ui/input";

function AuthPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "signup">("signup");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [orgName, setOrgName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res =
        mode === "signup"
          ? await api.signup({ email, password, org_name: orgName })
          : await api.login({ email, password });
      setToken(res.access_token);
      navigate("/agents");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen bg-canvas">
      <div className="hidden w-1/2 flex-col justify-between bg-primary p-12 text-white lg:flex">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/20">
            <GitBranch className="h-5 w-5" />
          </div>
          <span className="text-lg font-semibold">Orchestrator</span>
        </div>
        <div>
          <h1 className="text-3xl font-semibold leading-tight">
            Build, publish, and invoke multi-agent workflows
          </h1>
          <p className="mt-4 text-indigo-200">
            Single agents and orchestrated workflows exposed as async APIs with knowledge bases,
            MCP tools, and full run tracing.
          </p>
        </div>
        <p className="text-sm text-indigo-200">OpenAI-compatible gateway · Qdrant RAG · HTTP MCP</p>
      </div>

      <div className="flex flex-1 items-center justify-center p-6">
        <Card className="w-full max-w-md" padding="lg">
          <div className="mb-6">
            <h2 className="text-xl font-semibold text-gray-900">
              {mode === "signup" ? "Create your organization" : "Welcome back"}
            </h2>
            <p className="mt-1 text-sm text-gray-500">
              {mode === "signup"
                ? "Start building agents and workflows in minutes"
                : "Sign in to your orchestrator workspace"}
            </p>
          </div>

          <form onSubmit={submit} className="space-y-4">
            {mode === "signup" && (
              <Field label="Organization name">
                <Input value={orgName} onChange={(e) => setOrgName(e.target.value)} required />
              </Field>
            )}
            <Field label="Email">
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </Field>
            <Field label="Password">
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={8}
                required
              />
            </Field>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <Button type="submit" disabled={loading} className="w-full" size="lg">
              {loading ? "..." : mode === "signup" ? "Create account" : "Sign in"}
            </Button>
          </form>

          <Button
            type="button"
            variant="ghost"
            className="mt-4 w-full"
            onClick={() => setMode(mode === "login" ? "signup" : "login")}
          >
            {mode === "login" ? "Create new organization" : "Already have an account? Sign in"}
          </Button>
        </Card>
      </div>
    </div>
  );
}

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = getToken();
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      setReady(true);
      return;
    }
    api.me()
      .then(() => setReady(true))
      .catch(() => {
        clearToken();
        setReady(true);
      });
  }, []);

  if (!ready) return <PageLoader />;

  return (
    <Routes>
      <Route path="/login" element={<AuthPage />} />
      <Route
        path="/*"
        element={
          <PrivateRoute>
            <AppShell>
              <Routes>
                <Route path="/" element={<Navigate to="/agents" replace />} />
                <Route path="/agents" element={<AgentsPage />} />
                <Route path="/workflows" element={<WorkflowsPage />} />
                <Route path="/mcp" element={<McpPage />} />
                <Route path="/runs" element={<RunsPage />} />
                <Route path="/knowledge" element={<KnowledgePage />} />
                <Route path="/api-keys" element={<ApiKeysPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Routes>
            </AppShell>
          </PrivateRoute>
        }
      />
    </Routes>
  );
}
