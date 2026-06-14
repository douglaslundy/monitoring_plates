"use client";

import { useEffect, useState, useCallback } from "react";
import { X, AlertTriangle } from "lucide-react";
import type { RealtimeAlert } from "@/types";

type ActiveAlert = RealtimeAlert & { alertKey: string };

interface AlertBannerProps {
  lastAlert: RealtimeAlert | null;
}

export function AlertBanner({ lastAlert }: AlertBannerProps) {
  const [alerts, setAlerts] = useState<ActiveAlert[]>([]);

  const dismiss = useCallback((key: string) => {
    setAlerts((prev) => prev.filter((a) => a.alertKey !== key));
  }, []);

  useEffect(() => {
    if (!lastAlert) return;
    const alertKey =
      lastAlert.type === "plate_alert"
        ? `${lastAlert.occurrence_id}-${Date.now()}`
        : `${lastAlert.camera_id}-${Date.now()}`;
    const active: ActiveAlert = { ...lastAlert, alertKey };

    setAlerts((prev) => [active, ...prev]);

    const timer = setTimeout(() => dismiss(alertKey), 8_000);
    return () => clearTimeout(timer);
  }, [lastAlert, dismiss]);

  if (alerts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 w-80 max-h-[80vh] overflow-y-auto">
      {alerts.map((a) => (
        <div
          key={a.alertKey}
          className="flex items-start gap-3 p-4 bg-red-50 border border-red-200 rounded-xl shadow-lg animate-in slide-in-from-right-4"
        >
          <AlertTriangle className="h-5 w-5 text-red-500 shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            {a.type === "plate_alert" ? (
              <>
                <p className="font-bold text-red-800 text-sm">
                  Placa {a.plate} detectada
                </p>
                <p className="text-xs text-red-600 mt-0.5 truncate">
                  {a.camera_name}
                  {a.location ? ` - ${a.location}` : ""}
                </p>
                <p className="text-xs text-red-500 mt-0.5">
                  {new Date(a.detected_at).toLocaleTimeString("pt-BR")}
                </p>
              </>
            ) : (
              <>
                <p className="font-bold text-red-800 text-sm">
                  Camera {a.camera_name} com problema
                </p>
                <p className="text-xs text-red-600 mt-0.5 truncate">
                  {a.detail}
                  {a.location ? ` - ${a.location}` : ""}
                </p>
                <p className="text-xs text-red-500 mt-0.5">
                  {new Date(a.detected_at).toLocaleTimeString("pt-BR")}
                </p>
              </>
            )}
          </div>
          <button
            onClick={() => dismiss(a.alertKey)}
            className="p-1 rounded hover:bg-red-100 transition-colors shrink-0"
            aria-label="Fechar alerta"
          >
            <X className="h-3.5 w-3.5 text-red-400" />
          </button>
        </div>
      ))}
    </div>
  );
}
