import { useState } from "react";
import MapView from "../components/Map/MapView";
import SpotDetailPanel from "../components/Map/SpotDetailPanel";
import { useSpots, useSpotDetail } from "../hooks/useSpots";

export default function MapPage() {
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const { spots, refetch } = useSpots({ status: statusFilter });
  const [selectedSpotId, setSelectedSpotId] = useState<string | null>(null);
  const { spot: selectedSpot } = useSpotDetail(selectedSpotId);

  return (
    <div style={{ display: "flex", height: "100%" }}>
      <div style={{ flex: 1, position: "relative" }}>
        <div style={{ position: "absolute", top: 10, left: 60, zIndex: 1000, background: "white", padding: 8, borderRadius: 4, boxShadow: "0 2px 4px rgba(0,0,0,0.2)" }}>
          <select value={statusFilter || ""} onChange={(e) => setStatusFilter(e.target.value || undefined)}>
            <option value="">All statuses</option>
            <option value="flagged">Flagged</option>
            <option value="illegal">Illegal</option>
            <option value="review_pending">Review Pending</option>
            <option value="legal">Legal</option>
            <option value="resolved">Resolved</option>
          </select>
        </div>
        <MapView spots={spots} onSpotClick={setSelectedSpotId} />
      </div>
      {selectedSpot && (
        <SpotDetailPanel
          spot={selectedSpot}
          onClose={() => setSelectedSpotId(null)}
          onReviewed={() => { setSelectedSpotId(null); refetch(); }}
        />
      )}
    </div>
  );
}
