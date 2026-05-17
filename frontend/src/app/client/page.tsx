"use client";

import { useEffect, useState, useCallback } from "react";
import api from "@/lib/api";
import { MetricCard } from "@/components/ui/MetricCard";
import { PageHeader } from "@/components/ui/PageHeader";
import { useWebSocket } from "@/hooks/useWebSocket";
import { getMe } from "@/lib/auth";
import type { OccurrenceStats, OccurrenceWithCamera, UserMe } from "@/types";
import { Camera, Shield, Activity, BarChart2 } from "lucide-react";

function BarChart({ data }: { data: { hour: number; count: number }[] }) {
  const max = Math.max(...data.map((d) => d.count), 1);
  return (
    <div className="flex items-end gap-px h-20">
      {data.map(({ hour, count }) => (
        <div
          key={hour}
          className="flex-1 bg-primary/70 hover:bg-primary rounded-t-sm transition-colors cursor-default min-h-[2px]"
          style={{ height: `${Math.max((count / max) * 100, count > 0 ? 4 : 0)}%` }}
          title={`${hour}h: ${count}`}
        />
      ))}
    </div>
  );
}

function formatDt(s: string) {
  return new Date(s).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ClientDashboard() {
  const [user, setUser] = useState<UserMe | null>(null);
  const [stats, setStats] = useState<OccurrenceStats | null>(null);
  const [feed, setFeed] = useState<OccurrenceWithCamera[]>([]);
  const [loading, setLoading] = useState(true);

  const { lastAlert, isConnected } = useWebSocket(user?.client_id ?? null);

  const load = useCallback(async () => {
    try {
      const [statsRes, feedRes] = await Promise.all([
        api.get<OccurrenceStats>("/api/occurrences/stats"),
        api.get<{ items: OccurrenceWithCamera[] }>("/api/occurrences?limit=10"),
      ]);
      setStats(statsRes.data);
      setFeed(feedRes.data.items);
    } catch {
      /* silently ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    getMe()
      .then(setUser)
      .catch(() => {});
    load();
  }, [load]);

  // Prepend new alerts from WebSocket to feed
  useEffect(() => {
    if (!lastAlert) return;
    const synthetic: OccurrenceWithCamera = {
      id: lastAlert.occurrence_id,
      plate: lastAlert.plate,
      confidence: lastAlert.confidence,
      image_path: "",
      image_url: lastAlert.image_url,
      detected_at: lastAlert.detected_at,
      expires_at: null,
      camera: {
        id: "",
        name: lastAlert.camera_name,
        location: lastAlert.location,
      },
    };
    setFeed((prev) => [synthetic, ...prev].slice(0, 10));
  }, [lastAlert]);

  const camCount = stats
    ? stats.top_cameras.length
    : 0;

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <PageHeader
          title="Painel do Cliente"
          description="Monitoramento em tempo real"
        />
        <div className="flex items-center gap-2 text-xs">
          <span
            className={`h-2 w-2 rounded-full ${isConnected ? "bg-green-500 animate-pulse" : "bg-gray-300"}`}
          />
          <span className="text-muted-foreground">
            {isConnected ? "WebSocket conectado" : "Offline"}
          </span>
        </div>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <MetricCard
          title="Hoje"
          value={loading ? "—" : (stats?.total_today ?? 0)}
          icon={Activity}
          description="detecções hoje"
        />
        <MetricCard
          title="Semana"
          value={loading ? "—" : (stats?.total_week ?? 0)}
          icon={BarChart2}
          description="últimos 7 dias"
        />
        <MetricCard
          title="Câmeras ativas"
          value={loading ? "—" : camCount}
          icon={Camera}
          description="com ocorrências recentes"
        />
        <MetricCard
          title="Top placa"
          value={loading ? "—" : (stats?.top_plates[0]?.plate ?? "—")}
          icon={Shield}
          description={
            stats?.top_plates[0]
              ? `${stats.top_plates[0].count} detecções`
              : "sem dados"
          }
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent feed */}
        <div className="lg:col-span-2 bg-white rounded-xl border shadow-sm p-5">
          <h2 className="font-semibold mb-4">Últimas Ocorrências</h2>
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-12 animate-pulse bg-gray-100 rounded" />
              ))}
            </div>
          ) : feed.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhuma ocorrência registrada.</p>
          ) : (
            <ul className="divide-y">
              {feed.map((occ) => (
                <li
                  key={occ.id}
                  className="py-3 flex items-center gap-3"
                >
                  <span className="font-mono text-sm font-bold bg-gray-100 px-2 py-0.5 rounded">
                    {occ.plate}
                  </span>
                  <span className="text-sm text-muted-foreground flex-1 truncate">
                    {occ.camera.name}
                    {occ.camera.location ? ` · ${occ.camera.location}` : ""}
                  </span>
                  <span className="text-xs text-gray-400 shrink-0">
                    {formatDt(occ.detected_at)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* 24h bar chart */}
        <div className="bg-white rounded-xl border shadow-sm p-5">
          <h2 className="font-semibold mb-1">Detecções por hora</h2>
          <p className="text-xs text-muted-foreground mb-4">Últimas 24 horas</p>
          {loading || !stats ? (
            <div className="h-20 animate-pulse bg-gray-100 rounded" />
          ) : (
            <>
              <BarChart data={stats.by_hour} />
              <div className="flex justify-between text-xs text-muted-foreground mt-1">
                <span>0h</span>
                <span>12h</span>
                <span>23h</span>
              </div>
            </>
          )}
          {stats && (
            <div className="mt-4 space-y-2">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Top placas
              </p>
              {stats.top_plates.slice(0, 3).map((p) => (
                <div key={p.plate} className="flex justify-between text-sm">
                  <span className="font-mono font-medium">{p.plate}</span>
                  <span className="text-muted-foreground">{p.count}x</span>
                </div>
              ))}
              {stats.top_plates.length === 0 && (
                <p className="text-xs text-muted-foreground">Sem dados</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
