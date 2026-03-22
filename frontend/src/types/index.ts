export interface User {
  id: string;
  username: string;
  full_name: string;
  role: "reviewer" | "admin" | "super_admin";
}

export interface Spot {
  id: string;
  status: "flagged" | "legal" | "illegal" | "resolved" | "review_pending";
  first_detected_at: string;
  last_detected_at: string;
  confidence_score: number;
  change_type: string | null;
  assigned_to_id: string | null;
  version: number;
  latitude: number | null;
  longitude: number | null;
}

export interface SpotDetail extends Spot {
  notes: string | null;
  grace_period_until: string | null;
  reviewed_by_id: string | null;
  reviewed_at: string | null;
  previous_spot_id: string | null;
}

export interface Detection {
  id: string;
  detected_at: string;
  comparison_interval: "1d" | "7d" | "15d" | "30d";
  confidence: number;
  area_sq_meters: number;
}

export interface AuditLogEntry {
  id: string;
  officer_id: string;
  spot_id: string;
  action: string;
  notes: string | null;
  created_at: string;
}

export interface Notification {
  id: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

export interface SpotStats {
  flagged: number;
  legal: number;
  illegal: number;
  resolved: number;
  review_pending: number;
}
