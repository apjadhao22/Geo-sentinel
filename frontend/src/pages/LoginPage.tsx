import { useState } from "react";
import { useAuth } from "../hooks/useAuth";
import { useNavigate } from "react-router-dom";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login(username, password);
      navigate("/");
    } catch {
      setError("Invalid credentials");
    }
  };

  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh", background: "#f5f5f5" }}>
      <form onSubmit={handleSubmit} style={{ background: "white", padding: 32, borderRadius: 8, boxShadow: "0 2px 8px rgba(0,0,0,0.1)", width: 360 }}>
        <h2 style={{ marginBottom: 24 }}>Geo Sentinel</h2>
        {error && <p style={{ color: "red" }}>{error}</p>}
        <input type="text" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} style={{ width: "100%", padding: 8, marginBottom: 12, boxSizing: "border-box" }} />
        <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} style={{ width: "100%", padding: 8, marginBottom: 16, boxSizing: "border-box" }} />
        <button type="submit" style={{ width: "100%", padding: 10, background: "#1976d2", color: "white", border: "none", borderRadius: 4, cursor: "pointer" }}>Login</button>
      </form>
    </div>
  );
}
