"use client";

import { useRealtimeAlerts } from "@/components/realtime/RealtimeAlertsProvider";
import type { RealtimeConnectionState } from "@/lib/websocket";
import type { RealtimeAlert } from "@/types";

export function useWebSocket(_clientId: string | null | undefined): {
  lastAlert: RealtimeAlert | null;
  isConnected: boolean;
  connection: RealtimeConnectionState;
} {
  const { lastAlert, connection } = useRealtimeAlerts();

  return {
    lastAlert,
    isConnected: connection.connected,
    connection,
  };
}
