import { useState, useEffect } from "react";
import { reviewSpot } from "../../hooks/useSpots";
import type { SpotDetail } from "../../types";
import api from "../../api/client";

interface Detection {
  id: string;
  detected_at: string;
  comparison_interval: string;
  confidence: number;
  area_sq_meters: number;
}

interface ImageCompare {
  before_url: string;
  after_url: string;
  before_captured_at: string;
  after_captured_at: string;
}

interface Props {
  spot: SpotDetail;
  onClose: () => void;
  onReviewed: () => void;
}

const STATUS_BG: Record<string, string> = {
  flagged: "#ff9800",
  illegal: "#f44336",
  review_pending: "#ffeb3b",
  legal: "#4caf50",
  resolved: "#9e9e9e",
};

export default function SpotDetailPanel({ spot, onClose, onReviewed }: Props) {
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [detections, setDetections] = useState<Detection[]>([]);
  const [images, setImages] = useState<ImageCompare | null>(null);
  const [loadingImages, setLoadingImages] = useState(false);

  useEffect(() => {
    setDetections([]);
    setImages(null);
    setNotes("");
    setError("");
    api.get(`/spots/${spot.id}/detections`).then((res) => {
      setDetections(res.data);
      if (res.data.length > 0) {
        setLoadingImages(true);
        api.get(`/images/compare?detection_id=${res.data[0].id}`)
          .then((r) => setImages(r.data))
          .finally(() => setLoadingImages(false));
      }
    });
  }, [spot.id]);

  const handleReview = async (action: string) => {
    setError("");
    try {
      if ((action === "marked_legal" || action === "re_approved") && !notes.trim()) {
        setError("Notes are required for this action");
        return;
      }
      await reviewSpot(spot.id, action, spot.version, notes || undefined);
      onReviewed();
    } catch (err: unknown) {
      const status = (err as any)?.response?.status;
      if (status === 409) {
        setError("Conflict: this spot was modified by another user. Please refresh.");
      } else {
        setError("Failed to update spot");
      }
    }
  };

  const latestDetection = detections[0];

  return (
    <div style={{ width: 420, background: "white", borderLeft: "1px solid #ddd", padding: 16, overflowY: "auto", flexShrink: 0 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h3 style={{ margin: 0 }}>Construction Spot</h3>
        <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 20, cursor: "pointer", lineHeight: 1 }}>✕</button>
      </div>

      <span style={{
        display: "inline-block",
        padding: "3px 12px",
        borderRadius: 12,
        fontSize: 12,
        fontWeight: 700,
        textTransform: "uppercase",
        background: STATUS_BG[spot.status] || "#999",
        color: spot.status === "review_pending" ? "#333" : "white",
        marginBottom: 12,
      }}>
        {spot.status.replace(/_/g, " ")}
      </span>

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, marginBottom: 4 }}>
        <tbody>
          <tr><td style={{ padding: "3px 0", color: "#666", width: 130 }}>Change type</td><td><strong>{spot.change_type?.replace(/_/g, " ") || "—"}</strong></td></tr>
          <tr><td style={{ padding: "3px 0", color: "#666" }}>Confidence</td><td><strong>{(spot.confidence_score * 100).toFixed(0)}%</strong></td></tr>
          {latestDetection && <tr><td style={{ padding: "3px 0", color: "#666" }}>Area</td><td><strong>{latestDetection.area_sq_meters.toLocaleString()} m²</strong></td></tr>}
          <tr><td style={{ padding: "3px 0", color: "#666" }}>First detected</td><td>{new Date(spot.first_detected_at).toLocaleDateString()}</td></tr>
          <tr><td style={{ padding: "3px 0", color: "#666" }}>Last detected</td><td>{new Date(spot.last_detected_at).toLocaleDateString()}</td></tr>
          {spot.grace_period_until && <tr><td style={{ padding: "3px 0", color: "#666" }}>Grace period ends</td><td>{new Date(spot.grace_period_until).toLocaleDateString()}</td></tr>}
        </tbody>
      </table>

      {spot.notes && <p style={{ margin: "8px 0", fontSize: 13, color: "#555" }}><em>{spot.notes}</em></p>}

      {/* Before / After satellite comparison */}
      <hr style={{ margin: "14px 0" }} />
      <h4 style={{ margin: "0 0 10px", fontSize: 14 }}>Satellite Image Comparison</h4>

      {loadingImages && <p style={{ color: "#888", fontSize: 13 }}>Loading imagery…</p>}

      {images && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 8 }}>
          <div>
            <p style={{ margin: "0 0 4px", fontSize: 11, color: "#666", textAlign: "center", textTransform: "uppercase", letterSpacing: 1 }}>
              Before · {new Date(images.before_captured_at).toLocaleDateString()}
            </p>
            <img
              src={images.before_url}
              alt="Before"
              style={{ width: "100%", borderRadius: 4, border: "2px solid #4caf50", display: "block", objectFit: "cover", aspectRatio: "1" }}
              onError={(e) => {
                const el = e.target as HTMLImageElement;
                el.style.display = "none";
                el.insertAdjacentHTML("afterend", '<div style="height:150px;background:#f5f5f5;display:flex;align-items:center;justify-content:center;font-size:12px;color:#aaa;border-radius:4px">No image</div>');
              }}
            />
          </div>
          <div>
            <p style={{ margin: "0 0 4px", fontSize: 11, color: "#666", textAlign: "center", textTransform: "uppercase", letterSpacing: 1 }}>
              After · {new Date(images.after_captured_at).toLocaleDateString()}
            </p>
            <img
              src={images.after_url}
              alt="After"
              style={{ width: "100%", borderRadius: 4, border: "2px solid #f44336", display: "block", objectFit: "cover", aspectRatio: "1" }}
              onError={(e) => {
                const el = e.target as HTMLImageElement;
                el.style.display = "none";
                el.insertAdjacentHTML("afterend", '<div style="height:150px;background:#f5f5f5;display:flex;align-items:center;justify-content:center;font-size:12px;color:#aaa;border-radius:4px">No image</div>');
              }}
            />
          </div>
        </div>
      )}

      {!loadingImages && !images && (
        <p style={{ color: "#aaa", fontSize: 13 }}>No detection imagery available.</p>
      )}

      {/* Review */}
      <hr style={{ margin: "14px 0" }} />
      <h4 style={{ margin: "0 0 8px", fontSize: 14 }}>Review Action</h4>

      <textarea
        placeholder="Add notes (required for marking legal / re-approving)…"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        style={{ width: "100%", height: 68, marginBottom: 8, boxSizing: "border-box", fontSize: 13, padding: 8, borderRadius: 4, border: "1px solid #ddd", resize: "vertical" }}
      />

      {error && <p style={{ color: "red", fontSize: 13, margin: "0 0 8px" }}>{error}</p>}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {spot.status === "flagged" && (
          <>
            <button onClick={() => handleReview("marked_legal")} style={{ background: "#4caf50", color: "white", border: "none", padding: "8px 14px", borderRadius: 4, cursor: "pointer", fontSize: 13 }}>Mark Legal</button>
            <button onClick={() => handleReview("marked_illegal")} style={{ background: "#f44336", color: "white", border: "none", padding: "8px 14px", borderRadius: 4, cursor: "pointer", fontSize: 13 }}>Mark Illegal</button>
          </>
        )}
        {spot.status === "illegal" && (
          <button onClick={() => handleReview("marked_resolved")} style={{ background: "#2196f3", color: "white", border: "none", padding: "8px 14px", borderRadius: 4, cursor: "pointer", fontSize: 13 }}>Mark Resolved</button>
        )}
        {spot.status === "review_pending" && (
          <>
            <button onClick={() => handleReview("re_approved")} style={{ background: "#4caf50", color: "white", border: "none", padding: "8px 14px", borderRadius: 4, cursor: "pointer", fontSize: 13 }}>Re-approve</button>
            <button onClick={() => handleReview("re_flagged")} style={{ background: "#ff9800", color: "white", border: "none", padding: "8px 14px", borderRadius: 4, cursor: "pointer", fontSize: 13 }}>Re-flag</button>
          </>
        )}
      </div>
    </div>
  );
}
