import { useState, useEffect } from "react";
import api from "../api/client";
import type { User } from "../types";

export default function AdminPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [newUser, setNewUser] = useState({ username: "", password: "", full_name: "", role: "reviewer" });

  useEffect(() => {
    api.get("/users").then((res) => setUsers(res.data));
  }, []);

  const createUser = async () => {
    await api.post("/users", newUser);
    const res = await api.get("/users");
    setUsers(res.data);
    setNewUser({ username: "", password: "", full_name: "", role: "reviewer" });
  };

  return (
    <div style={{ padding: 24 }}>
      <h2>User Management</h2>

      <div style={{ background: "white", padding: 16, borderRadius: 8, marginBottom: 24, boxShadow: "0 2px 4px rgba(0,0,0,0.1)" }}>
        <h3>Add Officer</h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input placeholder="Username" value={newUser.username} onChange={(e) => setNewUser({ ...newUser, username: e.target.value })} style={{ padding: 8 }} />
          <input placeholder="Full Name" value={newUser.full_name} onChange={(e) => setNewUser({ ...newUser, full_name: e.target.value })} style={{ padding: 8 }} />
          <input type="password" placeholder="Password" value={newUser.password} onChange={(e) => setNewUser({ ...newUser, password: e.target.value })} style={{ padding: 8 }} />
          <select value={newUser.role} onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}>
            <option value="reviewer">Reviewer</option>
            <option value="admin">Admin</option>
          </select>
          <button onClick={createUser} style={{ background: "#1976d2", color: "white", border: "none", padding: "8px 16px", borderRadius: 4, cursor: "pointer" }}>Add</button>
        </div>
      </div>

      <table style={{ width: "100%", background: "white", borderRadius: 8, boxShadow: "0 2px 4px rgba(0,0,0,0.1)" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #eee" }}>
            <th style={{ padding: 12, textAlign: "left" }}>Username</th>
            <th style={{ padding: 12, textAlign: "left" }}>Full Name</th>
            <th style={{ padding: 12, textAlign: "left" }}>Role</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id} style={{ borderBottom: "1px solid #eee" }}>
              <td style={{ padding: 12 }}>{u.username}</td>
              <td style={{ padding: 12 }}>{u.full_name}</td>
              <td style={{ padding: 12 }}>{u.role}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
