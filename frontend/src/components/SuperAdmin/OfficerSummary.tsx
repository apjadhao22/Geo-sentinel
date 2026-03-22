import { useState, useEffect } from "react";
import api from "../../api/client";

interface Summary {
  officer_id: string;
  action: string;
  count: number;
}

export default function OfficerSummary() {
  const [data, setData] = useState<Summary[]>([]);

  useEffect(() => {
    api.get("/audit/officer-summary").then((res) => setData(res.data));
  }, []);

  // Group by officer
  const grouped = data.reduce((acc, item) => {
    if (!acc[item.officer_id]) acc[item.officer_id] = {};
    acc[item.officer_id][item.action] = item.count;
    return acc;
  }, {} as Record<string, Record<string, number>>);

  return (
    <div>
      <h3>Officer Review Summary</h3>
      <table style={{ width: "100%", background: "white", borderRadius: 8 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #eee" }}>
            <th style={{ padding: 12, textAlign: "left" }}>Officer</th>
            <th style={{ padding: 12, textAlign: "left" }}>Legal</th>
            <th style={{ padding: 12, textAlign: "left" }}>Illegal</th>
            <th style={{ padding: 12, textAlign: "left" }}>Resolved</th>
            <th style={{ padding: 12, textAlign: "left" }}>Total</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(grouped).map(([officerId, actions]) => {
            const legal = (actions.marked_legal || 0) + (actions.re_approved || 0);
            const illegal = actions.marked_illegal || 0;
            const resolved = actions.marked_resolved || 0;
            return (
              <tr key={officerId} style={{ borderBottom: "1px solid #eee" }}>
                <td style={{ padding: 12 }}>{officerId.slice(0, 8)}</td>
                <td style={{ padding: 12 }}>{legal}</td>
                <td style={{ padding: 12 }}>{illegal}</td>
                <td style={{ padding: 12 }}>{resolved}</td>
                <td style={{ padding: 12 }}>{legal + illegal + resolved}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
