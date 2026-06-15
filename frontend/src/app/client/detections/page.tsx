"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import api from "@/lib/api";
import { PageHeader } from "@/components/ui/PageHeader";
import { MetricCard } from "@/components/ui/MetricCard";
import { Modal } from "@/components/ui/Modal";
import type { Camera, VehicleEventPage, VehicleEventStats, VehicleEventWithCamera } from "@/types";
import { Calendar, Camera as CameraIcon, ChevronLeft, ChevronRight, Download, Filter, Layers3, Search, X } from "lucide-react";

const API_BASE = typeof window !== "undefined" ? window.location.origin : "";

const VEHICLE_TYPES = [
  { value: "", label: "Todos os tipos" },
  { value: "car", label: "Carro" },
  { value: "motorcycle", label: "Moto" },
  { value: "truck", label: "Caminhão" },
] as const;

function vehicleTypeLabel(vehicleType: string): string {
  if (vehicleType === "car") return "Carro";
  if (vehicleType === "motorcycle") return "Moto";
  if (vehicleType === "truck") return "Caminhão";
  return vehicleType;
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function HourChart({ data }: { data: { hour: number; count: number }[] }) {
  const max = Math.max(...data.map((item) => item.count), 1);
  return (
    <div className="flex items-end gap-1 h-28">
      {data.map((item) => (
        <div key={item.hour} className="flex-1 flex flex-col items-center gap-1">
          <div
            className="w-full rounded-t-md bg-primary/75 hover:bg-primary transition-colors"
            style={{ height: `${Math.max((item.count / max) * 100, item.count > 0 ? 5 : 0)}%` }}
            title={`${item.hour}h: ${item.count}`}
          />
          <span className="text-[10px] text-muted-foreground">{item.hour}</span>
        </div>
      ))}
    </div>
  );
}

export default function VehicleHistoryPage() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [stats, setStats] = useState<VehicleEventStats | null>(null);
  const [result, setResult] = useState<VehicleEventPage | null>(null);
  const [cameraId, setCameraId] = useState("");
  const [vehicleType, setVehicleType] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [loadingPage, setLoadingPage] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<VehicleEventWithCamera | null>(null);

  const activeFilters = useMemo(
    () => Boolean(cameraId || vehicleType || dateFrom || dateTo),
    [cameraId, dateFrom, dateTo, vehicleType]
  );

  const loadMeta = useCallback(async () => {
    try {
      const [cameraRes, statsRes] = await Promise.all([
        api.get<Camera[]>("/api/cameras"),
        api.get<VehicleEventStats>("/api/vehicles/stats"),
      ]);
      setCameras(cameraRes.data);
      setStats(statsRes.data);
    } catch {
      setError("Nao foi possivel carregar o resumo do historico.");
    }
  }, []);

  const loadEvents = useCallback(
    async (targetPage: number) => {
      setLoadingPage(true);
      setError("");
      try {
        const response = await api.get<VehicleEventPage>("/api/vehicles", {
          params: {
            camera_id: cameraId || undefined,
            vehicle_type: vehicleType || undefined,
            date_from: dateFrom || undefined,
            date_to: dateTo || undefined,
            page: targetPage,
            limit: 24,
          },
        });
        setResult(response.data);
        setPage(targetPage);
      } catch {
        setError("Nao foi possivel carregar os eventos de veiculos.");
      } finally {
        setLoading(false);
        setLoadingPage(false);
      }
    },
    [cameraId, dateFrom, dateTo, vehicleType]
  );

  useEffect(() => {
    void loadMeta();
    void loadEvents(1);
  }, [loadEvents, loadMeta]);

  const handleSearch = useCallback(() => {
    void loadEvents(1);
  }, [loadEvents]);

  const handleClearFilters = useCallback(() => {
    setCameraId("");
    setVehicleType("");
    setDateFrom("");
    setDateTo("");
    window.requestAnimationFrame(() => {
      void loadEvents(1);
    });
  }, [loadEvents]);

  const handleExport = useCallback(() => {
    const params = new URLSearchParams();
    if (cameraId) params.set("camera_id", cameraId);
    if (vehicleType) params.set("vehicle_type", vehicleType);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    window.open(`${API_BASE}/api/vehicles/export?${params.toString()}`, "_blank", "noopener,noreferrer");
  }, [cameraId, dateFrom, dateTo, vehicleType]);

  const topType = stats?.by_type[0];
  const topCamera = stats?.top_cameras[0];
  const byHour = stats?.by_hour ?? [];

  return (
    <div className="p-6">
      <PageHeader
        title="Historico de Veiculos"
        description="Consulta os eventos com frame, camera, tipo e periodo."
      />

      <div className="mb-6 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
        Esta tela mostra eventos ja persistidos. Uma camera pode estar offline agora e ainda assim existir um caminhão
        registrado anteriormente no historico.
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard
          title="Hoje"
          value={stats?.total_today ?? "—"}
          icon={Layers3}
          description="eventos capturados"
        />
        <MetricCard
          title="Semana"
          value={stats?.total_week ?? "—"}
          icon={Calendar}
          description="ultimos 7 dias"
        />
        <MetricCard
          title="Tipo lider"
          value={topType ? vehicleTypeLabel(topType.vehicle_type) : "—"}
          icon={CameraIcon}
          description={topType ? `${topType.count} eventos` : "sem dados"}
        />
        <MetricCard
          title="Top camera"
          value={topCamera?.camera_name ?? "—"}
          icon={CameraIcon}
          description={topCamera ? `${topCamera.count} eventos` : "sem dados"}
        />
      </div>

      {stats && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
          <div className="rounded-xl border bg-white p-5 shadow-sm">
            <h2 className="font-semibold mb-1">Fluxo de veiculos por hora</h2>
            <p className="text-xs text-muted-foreground mb-4">Ultimas 24 horas</p>
            <HourChart data={byHour} />
          </div>
          <div className="rounded-xl border bg-white p-5 shadow-sm">
            <h2 className="font-semibold mb-1">Resumo rapido</h2>
            <p className="text-xs text-muted-foreground mb-4">Maiores concentracoes do periodo</p>
            <div className="space-y-3">
              {stats.by_hour
                .filter((item) => item.count > 0)
                .sort((a, b) => b.count - a.count)
                .slice(0, 4)
                .map((item) => (
                  <div key={item.hour} className="flex items-center justify-between rounded-lg border px-3 py-2 text-sm">
                    <span>{item.hour.toString().padStart(2, "0")}h</span>
                    <span className="text-muted-foreground">{item.count} eventos</span>
                  </div>
                ))}
              {stats.by_hour.every((item) => item.count === 0) && (
                <p className="text-sm text-muted-foreground">Sem eventos registrados neste periodo.</p>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border shadow-sm p-5 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" aria-hidden="true" />
            <select
              value={cameraId}
              onChange={(event) => setCameraId(event.target.value)}
              className="w-full pl-9 pr-3 py-2 border rounded-lg text-sm appearance-none focus:outline-none focus:ring-2 focus:ring-primary/50"
              aria-label="Filtrar por camera"
            >
              <option value="">Todas as cameras</option>
              {cameras.map((camera) => (
                <option key={camera.id} value={camera.id}>
                  {camera.name}
                </option>
              ))}
            </select>
          </div>

          <div className="relative">
            <Filter className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" aria-hidden="true" />
            <select
              value={vehicleType}
              onChange={(event) => setVehicleType(event.target.value)}
              className="w-full pl-9 pr-3 py-2 border rounded-lg text-sm appearance-none focus:outline-none focus:ring-2 focus:ring-primary/50"
              aria-label="Filtrar por tipo de veiculo"
            >
              {VEHICLE_TYPES.map((option) => (
                <option key={option.value || "all"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="relative">
            <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" aria-hidden="true" />
            <input
              type="datetime-local"
              value={dateFrom}
              onChange={(event) => setDateFrom(event.target.value)}
              className="w-full pl-9 pr-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              aria-label="Data inicial"
            />
          </div>

          <div className="relative">
            <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" aria-hidden="true" />
            <input
              type="datetime-local"
              value={dateTo}
              onChange={(event) => setDateTo(event.target.value)}
              className="w-full pl-9 pr-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              aria-label="Data final"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3 mt-4">
          <button
            onClick={handleSearch}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 disabled:opacity-50"
            disabled={loadingPage}
          >
            {loadingPage ? "Buscando..." : "Buscar"}
          </button>
          {activeFilters && (
            <button
              onClick={handleClearFilters}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border text-sm text-muted-foreground hover:text-foreground hover:bg-gray-50"
            >
              <X className="h-4 w-4" aria-hidden="true" />
              Limpar filtros
            </button>
          )}
          {result && result.total > 0 && (
            <button
              onClick={handleExport}
              className="ml-auto inline-flex items-center gap-2 px-3 py-2 rounded-lg border text-sm hover:bg-gray-50"
            >
              <Download className="h-4 w-4" aria-hidden="true" />
              Exportar CSV
            </button>
          )}
        </div>
      </div>

      {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="h-64 animate-pulse rounded-xl border bg-gray-100" />
          ))}
        </div>
      ) : result && result.items.length === 0 ? (
        <div className="rounded-xl border bg-white py-16 text-center text-muted-foreground">
          <CameraIcon className="mx-auto mb-3 h-12 w-12 opacity-20" />
          <p>Nenhum evento encontrado para os filtros selecionados.</p>
        </div>
      ) : result ? (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <p className="text-sm text-muted-foreground" aria-live="polite">
              {result.total} evento{result.total === 1 ? "" : "s"} encontrado{result.total === 1 ? "" : "s"}.
            </p>
            <p className="text-xs text-muted-foreground">
              {result.page} de {result.pages} pagina{result.pages === 1 ? "" : "s"}
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
            {result.items.map((event) => (
              <button
                key={event.id}
                onClick={() => setSelected(event)}
                className="overflow-hidden rounded-xl border bg-white text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-primary/50"
              >
                <div className="aspect-video bg-black">
                  {event.image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={event.image_url}
                      alt={`${vehicleTypeLabel(event.vehicle_type)} em ${event.camera.name}`}
                      className="h-full w-full object-cover"
                      loading="lazy"
                    />
                  ) : (
                    <div className="flex h-full flex-col items-center justify-center gap-2 bg-gradient-to-br from-slate-950 via-slate-900 to-zinc-950 text-white/60">
                      <CameraIcon className="h-10 w-10" aria-hidden="true" />
                      <span className="text-xs">Sem imagem capturada</span>
                    </div>
                  )}
                </div>
                <div className="space-y-2 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
                      {vehicleTypeLabel(event.vehicle_type)}
                    </span>
                    <span className="text-xs text-muted-foreground">{Math.round(event.confidence * 100)}%</span>
                  </div>
                  <p className="font-medium">{event.camera.name}</p>
                  <p className="text-sm text-muted-foreground">{event.camera.location || "Sem local"}</p>
                  <p className="text-xs text-muted-foreground">{formatDateTime(event.detected_at)}</p>
                </div>
              </button>
            ))}
          </div>

          {result.pages > 1 && (
            <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
              <button
                onClick={() => void loadEvents(page - 1)}
                disabled={page <= 1 || loadingPage}
                className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm disabled:opacity-40"
              >
                <ChevronLeft className="h-4 w-4" />
                Anterior
              </button>
              <span className="rounded-lg border bg-white px-3 py-2 text-sm text-muted-foreground">
                Pagina {page} de {result.pages}
              </span>
              <button
                onClick={() => void loadEvents(page + 1)}
                disabled={page >= result.pages || loadingPage}
                className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm disabled:opacity-40"
              >
                Proxima
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}
        </>
      ) : null}

      <Modal
        open={selected !== null}
        onOpenChange={(open) => !open && setSelected(null)}
        title={selected ? vehicleTypeLabel(selected.vehicle_type) : ""}
        description={selected ? `${selected.camera.name}${selected.camera.location ? ` • ${selected.camera.location}` : ""}` : undefined}
        className="max-w-2xl"
      >
        {selected && (
          <div className="space-y-4">
            <div className="overflow-hidden rounded-xl border bg-black">
              {selected.image_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={selected.image_url}
                  alt={`${vehicleTypeLabel(selected.vehicle_type)} em ${selected.camera.name}`}
                  className="max-h-[420px] w-full object-contain"
                />
              ) : (
                <div className="flex h-64 flex-col items-center justify-center gap-2 text-white/60">
                  <CameraIcon className="h-12 w-12" />
                  <p className="text-sm">Sem imagem capturada para este evento</p>
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-xs text-muted-foreground">Tipo</p>
                <p className="font-medium">{vehicleTypeLabel(selected.vehicle_type)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Confiança</p>
                <p className="font-medium">{Math.round(selected.confidence * 100)}%</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Camera</p>
                <p className="font-medium">{selected.camera.name}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Local</p>
                <p className="font-medium">{selected.camera.location || "—"}</p>
              </div>
              <div className="col-span-2">
                <p className="text-xs text-muted-foreground">Detectado em</p>
                <p className="font-medium">{formatDateTime(selected.detected_at)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">BBox</p>
                <p className="font-medium">
                  {selected.bbox_x}, {selected.bbox_y} • {selected.bbox_w}x{selected.bbox_h}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Criado em</p>
                <p className="font-medium">{formatDateTime(selected.created_at)}</p>
              </div>
              <div className="col-span-2">
                <p className="text-xs text-muted-foreground">Imagem</p>
                <p className="font-mono text-xs break-all text-muted-foreground">{selected.image_path || "—"}</p>
              </div>
            </div>
          </div>
        )}
      </Modal>

      {!result && !loading && (
        <div className="rounded-xl border bg-white py-16 text-center text-muted-foreground">
          <Search className="mx-auto mb-3 h-12 w-12 opacity-20" />
          <p>Use os filtros acima para consultar o historico de veiculos.</p>
        </div>
      )}
    </div>
  );
}
