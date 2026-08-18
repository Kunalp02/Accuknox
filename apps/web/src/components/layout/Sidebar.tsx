import { NavLink } from "react-router-dom";
import {
  Bot,
  BookOpen,
  GitBranch,
  Key,
  LogOut,
  Play,
  Plug,
  Settings,
  Workflow,
} from "lucide-react";
import { cn } from "../../lib/cn";
import { clearToken } from "../../api";
import { useMe } from "../../hooks/useMe";

const navItems = [
  { to: "/agents", label: "Agents", icon: Bot },
  { to: "/workflows", label: "Workflows", icon: Workflow },
  { to: "/mcp", label: "MCP", icon: Plug },
  { to: "/runs", label: "Runs", icon: Play },
  { to: "/knowledge", label: "Knowledge", icon: BookOpen },
  { to: "/api-keys", label: "API Keys", icon: Key },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const me = useMe();

  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-white">
      <div className="flex h-14 items-center gap-2 border-b border-border px-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-white">
          <GitBranch className="h-4 w-4" />
        </div>
        <span className="text-sm font-semibold text-gray-900">Orchestrator</span>
      </div>

      <nav className="flex-1 space-y-0.5 p-3">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary-subtle text-primary"
                  : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
              )
            }
          >
            <Icon className="h-4 w-4 shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-border p-3 space-y-2">
        {me && (
          <div className="rounded-lg bg-gray-50 px-3 py-2">
            <p className="truncate text-xs font-medium text-gray-900">{me.email}</p>
            <p className="text-[11px] text-gray-500 capitalize">{me.role}</p>
          </div>
        )}
        <button
          type="button"
          onClick={() => {
            clearToken();
            window.location.href = "/login";
          }}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50 hover:text-gray-900"
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
