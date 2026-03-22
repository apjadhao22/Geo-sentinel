import { useState, useEffect } from "react";
import api from "../../api/client";
import type { SpotStats } from "../../types";

export default function StatsView() {
  const [stats, setStats] = useState<SpotStats | null>(null);

  useEffect(() => {
    api.get("/spots/stats").then((res) => setStats(res.data));
  }, []);

  if (!stats) return <div>Loading...</div>;

  const items = [
    { label: "Flagged", value: stats.flagged, color: "#ff9800" },
    { label: "Illegal", value: stats.illegal, color: "#f44336" },
    { label: "Review Pending", value: stats.review_pending, color: "#ffeb3b" },
    { label: "Legal", value: stats.legal, color: "#4caf50" },
    { label: "Resolved", value: stats.resolved, color: "#9e9e9e" },
  ];

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>Dashboard</h2>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        {items.map((item) => (
          <div key={item.label} style={{ background: "white", padding: 24, borderRadius: 8, boxShadow: "0 2px 4px rgba(0,0,0,0.1)", minWidth: 150, borderLeft: `4px solid ${item.color}` }}>
            <div style={{ fontSize: 32, fontWeight: "bold" }}>{item.value}</div>
            <div style={{ color: "#666" }}>{item.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
