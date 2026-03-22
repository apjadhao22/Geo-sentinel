import { useState, useEffect } from "react";
import api from "../api/client";

export function useNotifications(pollIntervalMs: number = 30000) {
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    const fetchCount = () => {
      api.get("/notifications/count").then((res) => setUnreadCount(res.data.unread)).catch(() => {});
    };
    fetchCount();
    const interval = setInterval(fetchCount, pollIntervalMs);
    return () => clearInterval(interval);
  }, [pollIntervalMs]);

  return { unreadCount };
}
