import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { api, clearToken, getToken, setToken } from "./api";
import AgentsPage from "./pages/AgentsPage";
import RunsPage from "./pages/RunsPage";
import KnowledgePage from "./pages/KnowledgePage";
import ApiKeysPage from "./pages/ApiKeysPage";
import Layout from "./components/Layout";

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
    <div className="auth-page">
      <div className="auth-card card stack">
        <div>
          <h2 style={{ margin: 0 }}>Orchestrator</h2>
          <p style={{ color: "var(--muted)", margin: "0.5rem 0 0" }}>
            Multi-agent platform — build, publish, invoke via API
          </p>
        </div>
        <form onSubmit={submit} className="stack">
          {mode === "signup" && (
            <div className="field">
              <label>Organization name</label>
              <input value={orgName} onChange={(e) => setOrgName(e.target.value)} required />
            </div>
          )}
          <div className="field">
            <label>Email</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="field">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required
            />
          </div>
          {error && <p style={{ color: "var(--danger)" }}>{error}</p>}
          <button type="submit" disabled={loading}>
            {loading ? "..." : mode === "signup" ? "Create account" : "Sign in"}
          </button>
        </form>
        <button
          type="button"
          className="secondary"
          onClick={() => setMode(mode === "login" ? "signup" : "login")}
        >
          {mode === "login" ? "Create new organization" : "Already have an account? Sign in"}
        </button>
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

  if (!ready) return null;

  return (
    <Routes>
      <Route path="/login" element={<AuthPage />} />
      <Route
        path="/*"
        element={
          <PrivateRoute>
            <Layout>
              <Routes>
                <Route path="/" element={<Navigate to="/agents" replace />} />
                <Route path="/agents" element={<AgentsPage />} />
                <Route path="/runs" element={<RunsPage />} />
                <Route path="/knowledge" element={<KnowledgePage />} />
                <Route path="/api-keys" element={<ApiKeysPage />} />
              </Routes>
            </Layout>
          </PrivateRoute>
        }
      />
    </Routes>
  );
}
