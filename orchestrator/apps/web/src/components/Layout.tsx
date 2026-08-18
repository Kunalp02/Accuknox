import { NavLink } from "react-router-dom";
import { clearToken } from "../api";

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>Orchestrator</h1>
        <nav>
          <NavLink className="nav-link" to="/agents">Agents</NavLink>
          <NavLink className="nav-link" to="/workflows">Workflows</NavLink>
          <NavLink className="nav-link" to="/mcp">MCP</NavLink>
          <NavLink className="nav-link" to="/runs">Runs</NavLink>
          <NavLink className="nav-link" to="/knowledge">Knowledge</NavLink>
          <NavLink className="nav-link" to="/api-keys">API Keys</NavLink>
        </nav>
        <button
          type="button"
          className="secondary"
          style={{ marginTop: "2rem", width: "100%" }}
          onClick={() => {
            clearToken();
            window.location.href = "/login";
          }}
        >
          Sign out
        </button>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}
