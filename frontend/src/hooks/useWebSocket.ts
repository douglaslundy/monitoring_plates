"use client";

import { useState, useEffect, useRef } from "react";
import { PlateAlertWebSocket } from "@/lib/websocket";
import { getToken } from "@/lib/auth";
import type { RealtimeAlert } from "@/types";

export function useWebSocket(clientId: string | null | undefined) {
  const [lastAlert, setLastAlert] = useState<RealtimeAlert | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<PlateAlertWebSocket | null>(null);

  useEffect(() => {
    if (!clientId) return;
    const token = getToken();
    if (!token) return;

    const ws = new PlateAlertWebSocket(clientId, token);
    wsRef.current = ws;
    ws.connect(setLastAlert, setIsConnected);

    return () => {
      ws.disconnect();
      wsRef.current = null;
    };
  }, [clientId]);

  return { lastAlert, isConnected };
}
