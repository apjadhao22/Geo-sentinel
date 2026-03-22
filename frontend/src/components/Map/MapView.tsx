import { MapContainer, TileLayer } from "react-leaflet";
import SpotMarker from "./SpotMarker";
import type { Spot } from "../../types";
import "leaflet/dist/leaflet.css";

const PCMC_CENTER: [number, number] = [18.6298, 73.7997];

interface Props {
  spots: Spot[];
  onSpotClick: (spotId: string) => void;
}

export default function MapView({ spots, onSpotClick }: Props) {
  return (
    <MapContainer center={PCMC_CENTER} zoom={13} style={{ height: "100%", width: "100%" }}>
      <TileLayer
        attribution='&copy; OpenStreetMap'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {spots.map((spot) => (
        <SpotMarker key={spot.id} spot={spot} onClick={() => onSpotClick(spot.id)} />
      ))}
    </MapContainer>
  );
}
