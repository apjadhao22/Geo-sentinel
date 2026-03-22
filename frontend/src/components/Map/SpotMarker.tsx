import { CircleMarker, Popup } from "react-leaflet";
import type { Spot } from "../../types";

const STATUS_COLORS: Record<string, string> = {
  flagged: "#ff9800",
  illegal: "#f44336",
  review_pending: "#ffeb3b",
  legal: "#4caf50",
  resolved: "#9e9e9e",
};

interface Props {
  spot: Spot;
  onClick: () => void;
}

export default function SpotMarker({ spot, onClick }: Props) {
  if (spot.latitude == null || spot.longitude == null) return null;

  return (
    <CircleMarker
      center={[spot.latitude, spot.longitude]}
      radius={8}
      pathOptions={{ color: STATUS_COLORS[spot.status] || "#999", fillColor: STATUS_COLORS[spot.status] || "#999", fillOpacity: 0.7 }}
      eventHandlers={{ click: onClick }}
    >
      <Popup>
        <strong>{spot.status.toUpperCase()}</strong><br />
        {spot.change_type && <span>Type: {spot.change_type}<br /></span>}
        Confidence: {(spot.confidence_score * 100).toFixed(0)}%
      </Popup>
    </CircleMarker>
  );
}
