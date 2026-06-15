"use client";

import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { getToken } from "@/lib/auth";
import { PlateAlertWebSocket, type RealtimeConnectionState, type RealtimeConnectionStatus } from "@/lib/websocket";
import type { RealtimeAlert } from "@/types";

interface RealtimeAlertsContextValue {
  lastAlert: RealtimeAlert | null;
  connection: RealtimeConnectionState;
}

const initialConnectionState: RealtimeConnectionState = {
  connected: false,
  status: "idle",
  message: "Aguardando autenticacao do cliente...",
  retryAfterMs: null,
  attempts: 0,
};

const RealtimeAlertsContext = createContext<RealtimeAlertsContextValue>({
  lastAlert: null,
  connection: initialConnectionState,
});

function statusMessage(status: RealtimeConnectionStatus): string {
  if (status === "auth_pending") return "Aguardando autenticacao do cliente...";
  if (status === "connecting") return "Conectando ao tempo real...";
  if (status === "connected") return "Tempo real conectado.";
  if (status === "retrying") return "Reconectando ao tempo real...";
  if (status === "error") return "Falha de autenticacao no tempo real.";
  if (status === "disconnected") return "Tempo real desconectado.";
  return "Tempo real indisponivel.";
}

export function RealtimeAlertsProvider({
  clientId,
  children,
}: {
  clientId: string | null | undefined;
  children: ReactNode;
}) {
  const [lastAlert, setLastAlert] = useState<RealtimeAlert | null>(null);
  const [connection, setConnection] = useState<RealtimeConnectionState>(initialConnectionState);
  const wsRef = useRef<PlateAlertWebSocket | null>(null);

  useEffect(() => {
    if (!clientId) {
      setConnection({
        connected: false,
        status: "auth_pending",
        message: statusMessage("auth_pending"),
        retryAfterMs: null,
        attempts: 0,
      });
      wsRef.current?.disconnect();
      wsRef.current = null;
      return;
    }

    const token = getToken();
    if (!token) {
      setConnection({
        connected: false,
        status: "auth_pending",
        message: statusMessage("auth_pending"),
        retryAfterMs: null,
        attempts: 0,
      });
      wsRef.current?.disconnect();
      wsRef.current = null;
      return;
    }

    wsRef.current?.disconnect();
    const ws = new PlateAlertWebSocket(clientId, token);
    wsRef.current = ws;

    ws.connect(
      setLastAlert,
      (state) => setConnection({
        ...state,
        message: state.message || statusMessage(state.status),
      }),
    );

    return () => {
      ws.disconnect();
      if (wsRef.current === ws) {
        wsRef.current = null;
      }
    };
  }, [clientId]);

  const value = useMemo(
    () => ({ lastAlert, connection }),
    [connection, lastAlert],
  );

  return <RealtimeAlertsContext.Provider value={value}>{children}</RealtimeAlertsContext.Provider>;
}

export function useRealtimeAlerts(): RealtimeAlertsContextValue {
  return useContext(RealtimeAlertsContext);
}
