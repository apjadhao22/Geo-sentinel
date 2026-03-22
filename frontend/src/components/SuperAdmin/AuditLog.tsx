import { useState, useEffect } from "react";
import api from "../../api/client";
import type { AuditLogEntry } from "../../types";

export default function AuditLog() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [filterAction, setFilterAction] = useState("");

  useEffect(() => {
    const params = new URLSearchParams();
    if (filterAction) params.set("action", filterAction);
    api.get(`/audit/logs?${params}`).then((res) => setLogs(res.data));
  }, [filterAction]);

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <select value={filterAction} onChange={(e) => setFilterAction(e.target.value)}>
          <option value="">All actions</option>
          <option value="marked_legal">Marked Legal</option>
          <option value="marked_illegal">Marked Illegal</option>
          <option value="marked_resolved">Marked Resolved</option>
          <option value="re_approved">Re-approved</option>
          <option value="re_flagged">Re-flagged</option>
        </select>
      </div>
      <table style={{ width: "100%", background: "white", borderRadius: 8 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #eee" }}>
            <th style={{ padding: 12, textAlign: "left" }}>Date</th>
            <th style={{ padding: 12, textAlign: "left" }}>Officer</th>
            <th style={{ padding: 12, textAlign: "left" }}>Action</th>
            <th style={{ padding: 12, textAlign: "left" }}>Notes</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log) => (
            <tr key={log.id} style={{ borderBottom: "1px solid #eee" }}>
              <td style={{ padding: 12 }}>{new Date(log.created_at).toLocaleString()}</td>
              <td style={{ padding: 12 }}>{log.officer_id.slice(0, 8)}</td>
              <td style={{ padding: 12 }}>{log.action}</td>
              <td style={{ padding: 12 }}>{log.notes || "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
