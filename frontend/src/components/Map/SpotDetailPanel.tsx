import { useState } from "react";
import { reviewSpot } from "../../hooks/useSpots";
import type { SpotDetail } from "../../types";

interface Props {
  spot: SpotDetail;
  onClose: () => void;
  onReviewed: () => void;
}

export default function SpotDetailPanel({ spot, onClose, onReviewed }: Props) {
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");

  const handleReview = async (action: string) => {
    try {
      if ((action === "marked_legal" || action === "re_approved") && !notes.trim()) {
        setError("Notes are required when marking as legal");
        return;
      }
      await reviewSpot(spot.id, action, spot.version, notes || undefined);
      onReviewed();
    } catch (err: any) {
      if (err.response?.status === 409) {
        setError("Conflict: this spot was modified by another user. Please refresh.");
      } else {
        setError("Failed to update spot");
      }
    }
  };

  return (
    <div style={{ width: 380, background: "white", borderLeft: "1px solid #ddd", padding: 16, overflowY: "auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <h3>Spot Detail</h3>
        <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 18, cursor: "pointer" }}>x</button>
      </div>

      <p><strong>Status:</strong> {spot.status}</p>
      <p><strong>Type:</strong> {spot.change_type || "Unknown"}</p>
      <p><strong>Confidence:</strong> {(spot.confidence_score * 100).toFixed(0)}%</p>
      <p><strong>First detected:</strong> {new Date(spot.first_detected_at).toLocaleDateString()}</p>
      <p><strong>Last detected:</strong> {new Date(spot.last_detected_at).toLocaleDateString()}</p>
      {spot.grace_period_until && <p><strong>Grace until:</strong> {new Date(spot.grace_period_until).toLocaleDateString()}</p>}
      {spot.notes && <p><strong>Notes:</strong> {spot.notes}</p>}

      <hr style={{ margin: "16px 0" }} />

      <textarea
        placeholder="Add notes (required for marking legal)..."
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        style={{ width: "100%", height: 80, marginBottom: 8, boxSizing: "border-box" }}
      />

      {error && <p style={{ color: "red", fontSize: 14 }}>{error}</p>}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {spot.status === "flagged" && (
          <>
            <button onClick={() => handleReview("marked_legal")} style={{ background: "#4caf50", color: "white", border: "none", padding: "8px 16px", borderRadius: 4, cursor: "pointer" }}>Mark Legal</button>
            <button onClick={() => handleReview("marked_illegal")} style={{ background: "#f44336", color: "white", border: "none", padding: "8px 16px", borderRadius: 4, cursor: "pointer" }}>Mark Illegal</button>
          </>
        )}
        {spot.status === "illegal" && (
          <button onClick={() => handleReview("marked_resolved")} style={{ background: "#2196f3", color: "white", border: "none", padding: "8px 16px", borderRadius: 4, cursor: "pointer" }}>Mark Resolved</button>
        )}
        {spot.status === "review_pending" && (
          <>
            <button onClick={() => handleReview("re_approved")} style={{ background: "#4caf50", color: "white", border: "none", padding: "8px 16px", borderRadius: 4, cursor: "pointer" }}>Re-approve</button>
            <button onClick={() => handleReview("re_flagged")} style={{ background: "#ff9800", color: "white", border: "none", padding: "8px 16px", borderRadius: 4, cursor: "pointer" }}>Re-flag</button>
          </>
        )}
      </div>
    </div>
  );
}
