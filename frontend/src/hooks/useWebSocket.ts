"use client";

import { useState, useEffect, useRef } from "react";
import { PlateAlertWebSocket } from "@/lib/websocket";
import { getToken } from "@/lib/auth";
import type { PlateAlert } from "@/types";

export function useWebSocket(clientId: string | null | undefined) {
  const [lastAlert, setLastAlert] = useState<PlateAlert | null>(null);
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
