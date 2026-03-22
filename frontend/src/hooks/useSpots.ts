import { useState, useEffect } from "react";
import api from "../api/client";
import type { Spot, SpotDetail } from "../types";

export function useSpots(filters?: { status?: string }) {
  const [spots, setSpots] = useState<Spot[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchSpots = async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filters?.status) params.set("status", filters.status);
    const res = await api.get(`/spots?${params}`);
    setSpots(res.data);
    setLoading(false);
  };

  useEffect(() => { fetchSpots(); }, [filters?.status]);

  return { spots, loading, refetch: fetchSpots };
}

export function useSpotDetail(spotId: string | null) {
  const [spot, setSpot] = useState<SpotDetail | null>(null);

  useEffect(() => {
    if (!spotId) { setSpot(null); return; }
    api.get(`/spots/${spotId}`).then((res) => setSpot(res.data));
  }, [spotId]);

  return { spot, setSpot };
}

export async function reviewSpot(spotId: string, action: string, version: number, notes?: string) {
  const res = await api.patch(`/spots/${spotId}/review`, { action, version, notes });
  return res.data;
}
