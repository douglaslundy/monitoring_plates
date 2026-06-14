"use client";

import { useEffect, useState, useCallback } from "react";
import api from "@/lib/api";
import { MetricCard } from "@/components/ui/MetricCard";
import { PageHeader } from "@/components/ui/PageHeader";
import { useWebSocket } from "@/hooks/useWebSocket";
import { getMe } from "@/lib/auth";
import type { UserMe } from "@/lib/auth";
import type {
  Camera as CameraType,
  OccurrenceStats,
  OccurrenceWithCamera,
  VehicleEventStats,
} from "@/types";
import { Camera as CameraIcon, Shield, Activity, BarChart2, CarFront, Truck, Bike, Gauge } from "lucide-react";

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

function vehicleTypeLabel(vehicleType: string) {
  if (vehicleType === "car") return "Carro";
  if (vehicleType === "motorcycle") return "Moto";
  if (vehicleType === "truck") return "Caminhão";
  return vehicleType;
}

function vehicleTypeIcon(vehicleType: string) {
  if (vehicleType === "motorcycle") return Bike;
  if (vehicleType === "truck") return Truck;
  return CarFront;
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
  const [vehicleStats, setVehicleStats] = useState<VehicleEventStats | null>(null);
  const [feed, setFeed] = useState<OccurrenceWithCamera[]>([]);
  const [cameras, setCameras] = useState<CameraType[]>([]);
  const [loading, setLoading] = useState(true);

  const { lastAlert, isConnected } = useWebSocket(user?.client_id ?? null);

  const load = useCallback(async () => {
    try {
      const [statsRes, feedRes, camerasRes, vehicleRes] = await Promise.all([
        api.get<OccurrenceStats>("/api/occurrences/stats"),
        api.get<{ items: OccurrenceWithCamera[] }>("/api/occurrences?limit=10"),
        api.get<CameraType[]>("/api/cameras"),
        api.get<VehicleEventStats>("/api/vehicles/stats"),
      ]);
      setStats(statsRes.data);
      setFeed(feedRes.data.items);
      setCameras(camerasRes.data);
      setVehicleStats(vehicleRes.data);
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

  useEffect(() => {
    if (!lastAlert || lastAlert.type !== "plate_alert") return;
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
      vehicle_type: null,
      vehicle_color: null,
      vehicle_make_model: null,
      region_code: null,
      ocr_engine_used: null,
    };
    setFeed((prev) => [synthetic, ...prev].slice(0, 10));
  }, [lastAlert]);

  const onlineCount = cameras.filter((camera) => camera.is_online).length;
  const totalCameras = cameras.length;
  const latestVehicle = vehicleStats?.latest_event;
  const topVehicleType = vehicleStats?.by_type[0];

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
            {isConnected ? "Tempo real conectado" : "Sem conexão em tempo real"}
          </span>
        </div>
      </div>

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
          title="Câmeras online"
          value={loading ? "—" : onlineCount}
          icon={CameraIcon}
          description={loading ? "carregando" : `${totalCameras} cadastradas`}
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

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 mb-8">
        <MetricCard
          title="Veículos hoje"
          value={loading ? "—" : (vehicleStats?.total_today ?? 0)}
          icon={CarFront}
          description="eventos de passagem"
        />
        <MetricCard
          title="Veículos na semana"
          value={loading ? "—" : (vehicleStats?.total_week ?? 0)}
          icon={Gauge}
          description="últimos 7 dias"
        />
        <MetricCard
          title="Tipo líder"
          value={loading ? "—" : (topVehicleType ? vehicleTypeLabel(topVehicleType.vehicle_type) : "—")}
          icon={topVehicleType ? vehicleTypeIcon(topVehicleType.vehicle_type) : CarFront}
          description={topVehicleType ? `${topVehicleType.count} ocorrências` : "sem dados"}
        />
        <MetricCard
          title="Último veículo"
          value={loading ? "—" : (latestVehicle ? vehicleTypeLabel(latestVehicle.vehicle_type) : "—")}
          icon={latestVehicle ? vehicleTypeIcon(latestVehicle.vehicle_type) : Truck}
          description={
            latestVehicle
              ? `${latestVehicle.camera_name} • ${Math.round(latestVehicle.confidence * 100)}%`
              : "sem leitura recente"
          }
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
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
                <li key={occ.id} className="py-3 flex items-center gap-3">
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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        <div className="bg-white rounded-xl border shadow-sm p-5">
          <h2 className="font-semibold mb-4">Fluxo de veículos</h2>
          {loading || !vehicleStats ? (
            <div className="space-y-3">
              <div className="h-20 animate-pulse bg-gray-100 rounded" />
              <div className="h-20 animate-pulse bg-gray-100 rounded" />
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">Por tipo</p>
                <div className="space-y-2">
                  {vehicleStats.by_type.length > 0 ? (
                    vehicleStats.by_type.map((item) => {
                      const Icon = vehicleTypeIcon(item.vehicle_type);
                      return (
                        <div key={item.vehicle_type} className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2">
                          <div className="flex items-center gap-2">
                            <Icon className="h-4 w-4 text-primary" />
                            <span className="text-sm font-medium">{vehicleTypeLabel(item.vehicle_type)}</span>
                          </div>
                          <span className="text-sm text-muted-foreground">{item.count}</span>
                        </div>
                      );
                    })
                  ) : (
                    <p className="text-xs text-muted-foreground">Sem veículos registrados.</p>
                  )}
                </div>
              </div>

              <div>
                <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">Top câmeras</p>
                <div className="space-y-2">
                  {vehicleStats.top_cameras.slice(0, 3).length > 0 ? (
                    vehicleStats.top_cameras.slice(0, 3).map((item) => (
                      <div key={item.camera_id} className="flex items-center justify-between text-sm">
                        <span className="truncate pr-3">{item.camera_name}</span>
                        <span className="text-muted-foreground">{item.count}x</span>
                      </div>
                    ))
                  ) : (
                    <p className="text-xs text-muted-foreground">Sem dados.</p>
                  )}
                </div>
              </div>

              {latestVehicle && (
                <div className="rounded-lg bg-primary/5 border border-primary/10 p-3">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1">
                    Última leitura
                  </p>
                  <p className="font-medium">
                    {vehicleTypeLabel(latestVehicle.vehicle_type)} em {latestVehicle.camera_name}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {latestVehicle.camera_location ? `${latestVehicle.camera_location} • ` : ""}
                    confiança {Math.round(latestVehicle.confidence * 100)}%
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {formatDt(latestVehicle.detected_at)}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="bg-white rounded-xl border shadow-sm p-5">
          <h2 className="font-semibold mb-1">Fluxo de veículos por hora</h2>
          <p className="text-xs text-muted-foreground mb-4">Últimas 24 horas</p>
          {loading || !vehicleStats ? (
            <div className="h-20 animate-pulse bg-gray-100 rounded" />
          ) : (
            <>
              <BarChart data={vehicleStats.by_hour} />
              <div className="flex justify-between text-xs text-muted-foreground mt-1">
                <span>0h</span>
                <span>12h</span>
                <span>23h</span>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
