import { NavLink, Outlet, Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const NAV_ITEMS = [
  { to: "/cases", label: "Cases & Evidence" },
  { to: "/search", label: "Search" },
  { to: "/sharing", label: "Sharing" },
  { to: "/audit", label: "Chain of Custody" },
  { to: "/retention", label: "Retention & Archive" },
  { to: "/reports", label: "Reports" },
];

export default function Layout() {
  const { user, loading, logout } = useAuth();

  if (loading) return <div className="main">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;

  return (
    <div className="app-shell">
      <nav className="sidebar">
        <h1>TTC DEMS</h1>
        {NAV_ITEMS.map((item) => (
          <NavLink key={item.to} to={item.to} className={({ isActive }) => (isActive ? "active" : "")}>
            {item.label}
          </NavLink>
        ))}
        <div className="user-info">
          <div>{user.name}</div>
          <div>{user.role}</div>
          <button className="secondary" style={{ marginTop: 8, width: "100%" }} onClick={logout}>
            Log out
          </button>
        </div>
      </nav>
      <div className="main">
        <Outlet />
      </div>
    </div>
  );
}
