import AuditLog from "../components/SuperAdmin/AuditLog";
import OfficerSummary from "../components/SuperAdmin/OfficerSummary";

export default function AuditPage() {
  return (
    <div style={{ padding: 24 }}>
      <h2>Audit Trail</h2>
      <OfficerSummary />
      <div style={{ marginTop: 24 }}>
        <AuditLog />
      </div>
    </div>
  );
}
