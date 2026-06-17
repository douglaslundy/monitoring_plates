"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import api from "@/lib/api";
import { PageHeader } from "@/components/ui/PageHeader";
import { MetricCard } from "@/components/ui/MetricCard";
import { Modal } from "@/components/ui/Modal";
import type { Camera, VehicleEventPage, VehicleEventStats, VehicleEventWithCamera } from "@/types";
import {
  Calendar,
  Camera as CameraIcon,
  Car,
  ChevronLeft,
  ChevronRight,
  Download,
  Filter,
  Layers3,
  PawPrint,
  Search,
  Users,
  X,
} from "lucide-react";
import { ViewToggle } from "@/components/ui/ViewToggle";
import { useViewMode } from "@/hooks/useViewMode";

const API_BASE = typeof window !== "undefined" ? window.location.origin : "";

// Rótulos PT por label de detecção (COCO).
const LABELS: Record<string, string> = {
  car: "Carro",
  motorcycle: "Moto",
  bus: "Ônibus",
  truck: "Caminhão",
  person: "Pessoa",
  bird: "Pássaro",
  cat: "Gato",
  dog: "Cachorro",
  horse: "Cavalo",
  sheep: "Ovelha",
  cow: "Vaca",
  elephant: "Elefante",
  bear: "Urso",
  zebra: "Zebra",
  giraffe: "Girafa",
  unknown: "Indefinido",
};

function labelFor(type: string): string {
  return LABELS[type] ?? type;
}

// Rótulo de exibição: agrupa piloto+moto em "Moto + Pessoa" (T5).
function displayLabel(event: { vehicle_type: string; companion_type?: string | null }): string {
  const main = labelFor(event.vehicle_type);
  if (event.companion_type) {
    return `${main} + ${labelFor(event.companion_type)}`;
  }
  return main;
}

const CATEGORIES = [
  { value: "", label: "Todos", icon: Layers3 },
  { value: "vehicle", label: "Veículos", icon: Car },
  { value: "person", label: "Pessoas", icon: Users },
  { value: "animal", label: "Animais", icon: PawPrint },
] as const;

function categoryLabel(category: string): string {
  return CATEGORIES.find((c) => c.value === category)?.label ?? category;
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

// O input datetime-local dá a hora LOCAL escolhida (sem fuso). Converte para o
// instante UTC (ISO com 'Z') que o backend compara contra detected_at. Sem isso
// o filtro de data/hora ficava deslocado pelo fuso (parecia não funcionar).
function localToIso(local: string): string | undefined {
  if (!local) return undefined;
  const d = new Date(local);
  return Number.isNaN(d.getTime()) ? undefined : d.toISOString();
}

function HourChart({ data }: { data: { hour: number; count: number }[] }) {
  const max = Math.max(...data.map((item) => item.count), 1);
  return (
    <div>
      {/* As barras são filhas DIRETAS do container de altura fixa (h-28) para
          que `height: %` resolva contra uma altura definida. */}
      <div className="flex items-end gap-1 h-28">
        {data.map((item) => (
          <div
            key={item.hour}
            className="flex-1 flex flex-col items-stretch h-full"
            title={`${item.hour}h: ${item.count}`}
          >
            {/* Rótulo com a quantidade de cada coluna (oculto quando zero). */}
            <span className="h-3 text-center text-[10px] leading-3 text-muted-foreground tabular-nums">
              {item.count > 0 ? item.count : ""}
            </span>
            {/* Área da barra: % resolve contra esta região (altura - rótulo). */}
            <div className="flex-1 flex items-end">
              <div
                className="w-full rounded-t-md bg-primary/75 hover:bg-primary transition-colors"
                style={{ height: `${Math.max((item.count / max) * 100, item.count > 0 ? 5 : 0)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
      <div className="mt-1 flex gap-1">
        {data.map((item) => (
          <span key={item.hour} className="flex-1 text-center text-[10px] text-muted-foreground">
            {item.hour}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function DetectionHistory({ title, description }: { title: string; description: string }) {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [stats, setStats] = useState<VehicleEventStats | null>(null);
  const [result, setResult] = useState<VehicleEventPage | null>(null);
  const [viewMode, setViewMode] = useViewMode("deteccoes-view");
  const [category, setCategory] = useState("");
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

  useEffect(() => {
    api.get<Camera[]>("/api/cameras").then((r) => setCameras(r.data)).catch(() => {});
  }, []);

  const loadStats = useCallback(async (cat: string) => {
    try {
      const res = await api.get<VehicleEventStats>("/api/vehicles/stats", {
        params: { category: cat || undefined },
      });
      setStats(res.data);
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
            category: category || undefined,
            camera_id: cameraId || undefined,
            vehicle_type: vehicleType || undefined,
            date_from: localToIso(dateFrom),
            date_to: localToIso(dateTo),
            page: targetPage,
            limit: 24,
          },
        });
        setResult(response.data);
        setPage(targetPage);
      } catch {
        setError("Nao foi possivel carregar os eventos de deteccao.");
      } finally {
        setLoading(false);
        setLoadingPage(false);
      }
    },
    [category, cameraId, dateFrom, dateTo, vehicleType]
  );

  useEffect(() => {
    void loadStats(category);
    void loadEvents(1);
  }, [category, loadEvents, loadStats]);

  const handleSearch = useCallback(() => {
    void loadEvents(1);
  }, [loadEvents]);

  const handleSelectCategory = useCallback((value: string) => {
    setCategory(value);
    setVehicleType(""); // os tipos disponíveis dependem da categoria
  }, []);

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
    if (category) params.set("category", category);
    if (cameraId) params.set("camera_id", cameraId);
    if (vehicleType) params.set("vehicle_type", vehicleType);
    const isoFrom = localToIso(dateFrom);
    const isoTo = localToIso(dateTo);
    if (isoFrom) params.set("date_from", isoFrom);
    if (isoTo) params.set("date_to", isoTo);
    window.open(`${API_BASE}/api/vehicles/export?${params.toString()}`, "_blank", "noopener,noreferrer");
  }, [category, cameraId, dateFrom, dateTo, vehicleType]);

  const categoryCount = useCallback(
    (cat: string) => {
      if (!stats) return null;
      if (!cat) return stats.by_category.reduce((sum, c) => sum + c.count, 0);
      return stats.by_category.find((c) => c.category === cat)?.count ?? 0;
    },
    [stats]
  );

  const topType = stats?.by_type[0];
  const topCamera = stats?.top_cameras[0];
  const byHour = stats?.by_hour ?? [];
  // O dropdown de "tipo" é dinâmico: reflete os tipos da categoria selecionada.
  const typeOptions = stats?.by_type ?? [];

  return (
    <div className="p-6">
      <PageHeader title={title} description={description} />

      {/* Abas de categoria */}
      <div className="mb-6 flex flex-wrap gap-2">
        {CATEGORIES.map((cat) => {
          const Icon = cat.icon;
          const active = category === cat.value;
          const count = categoryCount(cat.value);
          return (
            <button
              key={cat.value || "all"}
              onClick={() => handleSelectCategory(cat.value)}
              className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition ${
                active ? "border-primary bg-primary text-primary-foreground" : "bg-white hover:bg-gray-50"
              }`}
              aria-pressed={active}
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
              {cat.label}
              {count !== null && (
                <span
                  className={`rounded-full px-1.5 text-xs ${
                    active ? "bg-white/20" : "bg-gray-100 text-muted-foreground"
                  }`}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard title="Hoje" value={stats?.total_today ?? "—"} icon={Layers3} description="detecções capturadas" />
        <MetricCard title="Semana" value={stats?.total_week ?? "—"} icon={Calendar} description="últimos 7 dias" />
        <MetricCard
          title="Tipo líder"
          value={topType ? labelFor(topType.vehicle_type) : "—"}
          icon={CameraIcon}
          description={topType ? `${topType.count} detecções` : "sem dados"}
        />
        <MetricCard
          title="Top câmera"
          value={topCamera?.camera_name ?? "—"}
          icon={CameraIcon}
          description={topCamera ? `${topCamera.count} detecções` : "sem dados"}
        />
      </div>

      {stats && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
          <div className="rounded-xl border bg-white p-5 shadow-sm">
            <h2 className="font-semibold mb-1">Fluxo por hora</h2>
            <p className="text-xs text-muted-foreground mb-4">
              Últimas 24 horas{category ? ` · ${categoryLabel(category)}` : ""}
            </p>
            <HourChart data={byHour} />
          </div>
          <div className="rounded-xl border bg-white p-5 shadow-sm">
            <h2 className="font-semibold mb-1">Por tipo</h2>
            <p className="text-xs text-muted-foreground mb-4">
              Distribuição{category ? ` em ${categoryLabel(category)}` : " geral"}
            </p>
            <div className="space-y-2">
              {typeOptions.slice(0, 6).map((item) => (
                <div key={item.vehicle_type} className="flex items-center justify-between rounded-lg border px-3 py-2 text-sm">
                  <span className="capitalize">{labelFor(item.vehicle_type)}</span>
                  <span className="text-muted-foreground">{item.count}</span>
                </div>
              ))}
              {typeOptions.length === 0 && (
                <p className="text-sm text-muted-foreground">Sem detecções neste período.</p>
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
              aria-label="Filtrar por câmera"
            >
              <option value="">Todas as câmeras</option>
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
              aria-label="Filtrar por tipo"
            >
              <option value="">Todos os tipos</option>
              {typeOptions.map((option) => (
                <option key={option.vehicle_type} value={option.vehicle_type}>
                  {labelFor(option.vehicle_type)}
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
          <p>Nenhuma detecção encontrada para os filtros selecionados.</p>
        </div>
      ) : result ? (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <p className="text-sm text-muted-foreground" aria-live="polite">
              {result.total} detecç{result.total === 1 ? "ão" : "ões"} encontrada{result.total === 1 ? "" : "s"}.
            </p>
            <div className="flex items-center gap-3">
              <p className="text-xs text-muted-foreground">
                {result.page} de {result.pages} página{result.pages === 1 ? "" : "s"}
              </p>
              {result.items.length > 0 && <ViewToggle mode={viewMode} onChange={setViewMode} />}
            </div>
          </div>

          {viewMode === "blocks" ? (
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
                        alt={`${displayLabel(event)} em ${event.camera.name}`}
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
                        {displayLabel(event)}
                      </span>
                      <span className="text-xs text-muted-foreground">{Math.round(event.confidence * 100)}%</span>
                    </div>
                    {event.plate && <p className="font-mono text-sm font-semibold tracking-wider">{event.plate}</p>}
                    <p className="font-medium">{event.camera.name}</p>
                    <p className="text-sm text-muted-foreground">{event.camera.location || "Sem local"}</p>
                    <p className="text-xs text-muted-foreground">{formatDateTime(event.detected_at)}</p>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {result.items.map((event) => (
                <button
                  key={event.id}
                  onClick={() => setSelected(event)}
                  className="flex items-center gap-3 rounded-lg border bg-white p-2 text-left shadow-sm transition hover:border-primary/40 hover:shadow focus:outline-none focus:ring-2 focus:ring-primary/50"
                >
                  <div className="h-14 w-20 flex-shrink-0 overflow-hidden rounded bg-black">
                    {event.image_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={event.image_url}
                        alt={`${displayLabel(event)} em ${event.camera.name}`}
                        className="h-full w-full object-cover"
                        loading="lazy"
                      />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-white/50">
                        <CameraIcon className="h-6 w-6" aria-hidden="true" />
                      </div>
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
                        {displayLabel(event)}
                      </span>
                      {event.plate && (
                        <span className="font-mono text-sm font-semibold tracking-wider">{event.plate}</span>
                      )}
                    </div>
                    <p className="mt-1 truncate text-sm font-medium">
                      {event.camera.name}
                      {event.camera.location ? ` · ${event.camera.location}` : ""}
                    </p>
                    <p className="text-xs text-muted-foreground">{formatDateTime(event.detected_at)}</p>
                  </div>
                  <span className="hidden flex-shrink-0 text-xs text-muted-foreground sm:block">
                    {Math.round(event.confidence * 100)}%
                  </span>
                </button>
              ))}
            </div>
          )}

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
                Página {page} de {result.pages}
              </span>
              <button
                onClick={() => void loadEvents(page + 1)}
                disabled={page >= result.pages || loadingPage}
                className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm disabled:opacity-40"
              >
                Próxima
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}
        </>
      ) : null}

      <Modal
        open={selected !== null}
        onOpenChange={(open) => !open && setSelected(null)}
        title={selected ? displayLabel(selected) : ""}
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
                  alt={`${labelFor(selected.vehicle_type)} em ${selected.camera.name}`}
                  className="max-h-[420px] w-full object-contain"
                />
              ) : (
                <div className="flex h-64 flex-col items-center justify-center gap-2 text-white/60">
                  <CameraIcon className="h-12 w-12" />
                  <p className="text-sm">Sem imagem capturada para esta detecção</p>
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-xs text-muted-foreground">Categoria</p>
                <p className="font-medium">{categoryLabel(selected.category)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Tipo</p>
                <p className="font-medium">{displayLabel(selected)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Placa</p>
                <p className="font-mono font-medium">{selected.plate || "—"}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Confiança</p>
                <p className="font-medium">{Math.round(selected.confidence * 100)}%</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Câmera</p>
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
            </div>
          </div>
        )}
      </Modal>

      {!result && !loading && (
        <div className="rounded-xl border bg-white py-16 text-center text-muted-foreground">
          <Search className="mx-auto mb-3 h-12 w-12 opacity-20" />
          <p>Use os filtros acima para consultar o histórico de detecções.</p>
        </div>
      )}
    </div>
  );
}
