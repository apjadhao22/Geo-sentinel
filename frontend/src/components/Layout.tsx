import { Link, Outlet } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useNotifications } from "../hooks/useNotifications";

export default function Layout() {
  const { user, logout } = useAuth();
  const { unreadCount } = useNotifications();

  return (
    <div style={{ display: "flex", height: "100vh" }}>
      <nav style={{ width: 220, background: "#1a237e", color: "white", padding: 16, display: "flex", flexDirection: "column" }}>
        <h3 style={{ marginBottom: 24 }}>Geo Sentinel</h3>
        <Link to="/" style={{ color: "white", marginBottom: 12, textDecoration: "none" }}>Map</Link>
        <Link to="/dashboard" style={{ color: "white", marginBottom: 12, textDecoration: "none" }}>Dashboard</Link>
        {(user?.role === "admin" || user?.role === "super_admin") && (
          <Link to="/admin" style={{ color: "white", marginBottom: 12, textDecoration: "none" }}>Admin</Link>
        )}
        {user?.role === "super_admin" && (
          <Link to="/audit" style={{ color: "white", marginBottom: 12, textDecoration: "none" }}>Audit</Link>
        )}
        <div style={{ marginTop: "auto" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <span style={{ position: "relative", cursor: "pointer", fontSize: 20 }}>
              &#128276;
              {unreadCount > 0 && (
                <span style={{ position: "absolute", top: -6, right: -8, background: "#f44336", borderRadius: "50%", width: 18, height: 18, fontSize: 11, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  {unreadCount}
                </span>
              )}
            </span>
          </div>
          <p style={{ fontSize: 14 }}>{user?.full_name}</p>
          <button onClick={logout} style={{ background: "transparent", color: "white", border: "1px solid white", padding: "4px 8px", cursor: "pointer" }}>Logout</button>
        </div>
      </nav>
      <main style={{ flex: 1, overflow: "auto" }}>
        <Outlet />
      </main>
    </div>
  );
}
