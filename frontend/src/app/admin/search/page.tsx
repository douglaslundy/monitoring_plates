"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import api from "@/lib/api";
import { PageHeader } from "@/components/ui/PageHeader";
import { Modal } from "@/components/ui/Modal";
import type { OccurrenceWithCamera, OccurrencePage, Camera } from "@/types";
import {
  Search,
  Download,
  Camera as CameraIcon,
  Calendar,
  X,
  ZoomIn,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 90 ? "bg-green-500" : pct >= 70 ? "bg-yellow-500" : "bg-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-100 rounded-full h-1.5">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-muted-foreground w-9 text-right">{pct}%</span>
    </div>
  );
}

function HighlightPlate({ plate, query }: { plate: string; query: string }) {
  if (!query) {
    return (
      <span className="font-mono font-bold text-base tracking-wider">{plate}</span>
    );
  }
  const q = query.toUpperCase();
  const idx = plate.toUpperCase().indexOf(q);
  if (idx === -1) {
    return (
      <span className="font-mono font-bold text-base tracking-wider">{plate}</span>
    );
  }
  return (
    <span className="font-mono font-bold text-base tracking-wider">
      {plate.slice(0, idx)}
      <mark className="bg-yellow-300 text-gray-900 rounded px-0.5">
        {plate.slice(idx, idx + q.length)}
      </mark>
      {plate.slice(idx + q.length)}
    </span>
  );
}

function formatDt(s: string) {
  return new Date(s).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function AdminSearchPage() {
  const [plate, setPlate] = useState("");
  const [cameraId, setCameraId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [result, setResult] = useState<OccurrencePage | null>(null);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<OccurrenceWithCamera | null>(null);
  const [zoomedImage, setZoomedImage] = useState<string | null>(null);
  const plateRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api
      .get<Camera[]>("/api/cameras")
      .then((r) => setCameras(r.data))
      .catch(() => {});
    plateRef.current?.focus();
  }, []);

  const search = useCallback(
    async (p = 1) => {
      setLoading(true);
      try {
        const res = await api.post<OccurrencePage>("/api/occurrences/search", {
          plate: plate.trim() || undefined,
          camera_ids: cameraId ? [cameraId] : undefined,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
          page: p,
          limit: 20,
        });
        setResult(res.data);
        setPage(p);
      } catch {
        /* ignore */
      } finally {
        setLoading(false);
      }
    },
    [plate, cameraId, dateFrom, dateTo]
  );

  function exportCsv() {
    const params = new URLSearchParams();
    if (plate.trim()) params.set("plate", plate.trim());
    if (cameraId) params.set("camera_id", cameraId);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    window.open(`${API_BASE}/api/occurrences/export?${params}`, "_blank");
  }

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === "Enter") search(1);
  }

  function clearFilters() {
    setPlate("");
    setCameraId("");
    setDateFrom("");
    setDateTo("");
    setResult(null);
    plateRef.current?.focus();
  }

  const hasFilters = plate || cameraId || dateFrom || dateTo;

  return (
    <div className="p-6">
      <PageHeader
        title="Pesquisa Global de Placas"
        description="Busque ocorrências em todos os clientes"
      />

      {/* Filters */}
      <div className="bg-white rounded-xl border shadow-sm p-5 mb-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="relative">
            <Search
              className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground"
              aria-hidden="true"
            />
            <input
              ref={plateRef}
              value={plate}
              onChange={(e) => setPlate(e.target.value.toUpperCase())}
              onKeyDown={handleKey}
              placeholder="Placa (ex: ABC1234)"
              aria-label="Filtrar por placa"
              className="w-full pl-9 pr-3 py-2 border rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>

          <div className="relative">
            <CameraIcon
              className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground"
              aria-hidden="true"
            />
            <select
              value={cameraId}
              onChange={(e) => setCameraId(e.target.value)}
              aria-label="Filtrar por câmera"
              className="w-full pl-9 pr-3 py-2 border rounded-lg text-sm appearance-none focus:outline-none focus:ring-2 focus:ring-primary/50"
            >
              <option value="">Todas as câmeras</option>
              {cameras.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          <div className="relative">
            <Calendar
              className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground"
              aria-hidden="true"
            />
            <input
              type="datetime-local"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              aria-label="Data de início"
              className="w-full pl-9 pr-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>

          <div className="relative">
            <Calendar
              className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground"
              aria-hidden="true"
            />
            <input
              type="datetime-local"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              aria-label="Data de fim"
              className="w-full pl-9 pr-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>
        </div>

        <div className="flex items-center gap-3 mt-4 flex-wrap">
          <button
            onClick={() => search(1)}
            disabled={loading}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
          >
            {loading ? "Buscando…" : "Buscar"}
          </button>
          {hasFilters && (
            <button
              onClick={clearFilters}
              className="flex items-center gap-1 px-3 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              <X className="h-3.5 w-3.5" aria-hidden="true" /> Limpar
            </button>
          )}
          {result && result.total > 0 && (
            <button
              onClick={exportCsv}
              aria-label="Exportar resultados em CSV"
              className="ml-auto flex items-center gap-2 px-3 py-2 border rounded-lg text-sm hover:bg-gray-50 transition-colors"
            >
              <Download className="h-4 w-4" aria-hidden="true" />
              Exportar CSV
            </button>
          )}
        </div>
      </div>

      {/* Results */}
      {result && (
        <>
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm text-muted-foreground" aria-live="polite">
              {result.total === 0
                ? "Nenhuma ocorrência encontrada"
                : `${result.total} ocorrência${result.total !== 1 ? "s" : ""} encontrada${result.total !== 1 ? "s" : ""}`}
            </p>
            {result.pages > 1 && (
              <p className="text-xs text-muted-foreground">
                Página {result.page} de {result.pages}
              </p>
            )}
          </div>

          {result.items.length === 0 ? (
            <div className="text-center py-16 text-muted-foreground">
              <Search className="h-12 w-12 mx-auto mb-3 opacity-20" aria-hidden="true" />
              <p>Nenhum resultado para os filtros selecionados.</p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {result.items.map((occ) => (
                  <button
                    key={occ.id}
                    onClick={() => setSelected(occ)}
                    aria-label={`Ver detalhes da placa ${occ.plate}`}
                    className="bg-white rounded-xl border shadow-sm overflow-hidden text-left hover:shadow-md hover:border-primary/40 transition-all group focus:outline-none focus:ring-2 focus:ring-primary/50"
                  >
                    <div className="aspect-video bg-gray-100 relative overflow-hidden">
                      {occ.image_url ? (
                        <img
                          src={occ.image_url}
                          alt={`Captura da placa ${occ.plate}`}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                          loading="lazy"
                          onError={(e) => {
                            (e.target as HTMLImageElement).style.display = "none";
                          }}
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <CameraIcon className="h-8 w-8 text-gray-300" aria-hidden="true" />
                        </div>
                      )}
                    </div>
                    <div className="p-3">
                      <div className="inline-block bg-gray-900 text-white px-2 py-0.5 rounded mb-2">
                        <HighlightPlate plate={occ.plate} query={plate} />
                      </div>
                      <ConfidenceBar value={occ.confidence} />
                      <p className="text-xs text-muted-foreground mt-2 truncate">
                        {occ.camera.name}
                        {occ.camera.location ? ` · ${occ.camera.location}` : ""}
                      </p>
                      <p className="text-xs text-gray-400 mt-0.5">
                        {formatDt(occ.detected_at)}
                      </p>
                    </div>
                  </button>
                ))}
              </div>

              {result.pages > 1 && (
                <div className="flex justify-center gap-2 mt-6 flex-wrap">
                  <button
                    onClick={() => search(page - 1)}
                    disabled={page <= 1}
                    className="px-3 py-1.5 border rounded text-sm disabled:opacity-40 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary/50"
                  >
                    Anterior
                  </button>
                  {Array.from({ length: result.pages }, (_, i) => i + 1)
                    .filter((p) => Math.abs(p - page) <= 2)
                    .map((p) => (
                      <button
                        key={p}
                        onClick={() => search(p)}
                        aria-current={p === page ? "page" : undefined}
                        className={`px-3 py-1.5 border rounded text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50 ${
                          p === page
                            ? "bg-primary text-primary-foreground border-primary"
                            : "hover:bg-gray-50"
                        }`}
                      >
                        {p}
                      </button>
                    ))}
                  <button
                    onClick={() => search(page + 1)}
                    disabled={page >= result.pages}
                    className="px-3 py-1.5 border rounded text-sm disabled:opacity-40 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary/50"
                  >
                    Próxima
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}

      {!result && !loading && (
        <div className="text-center py-20 text-muted-foreground">
          <Search className="h-14 w-14 mx-auto mb-4 opacity-15" aria-hidden="true" />
          <p className="text-base">Use os filtros acima para buscar ocorrências.</p>
          <p className="text-sm mt-1">
            Pesquise por placa completa ou parcial em todos os clientes.
          </p>
        </div>
      )}

      {/* ── Detail modal ── */}
      <Modal
        open={!!selected}
        onOpenChange={(open) => !open && setSelected(null)}
        title={selected?.plate ?? ""}
        description={
          selected
            ? `${selected.camera.name}${selected.camera.location ? ` · ${selected.camera.location}` : ""}`
            : undefined
        }
        className="max-w-xl"
      >
        {selected && (
          <div className="space-y-4">
            <div className="relative group">
              {selected.image_url ? (
                <>
                  <img
                    src={selected.image_url}
                    alt={`Captura da placa ${selected.plate}`}
                    className="w-full rounded-lg object-contain max-h-64 bg-gray-50 cursor-zoom-in"
                    onClick={() => setZoomedImage(selected.image_url)}
                  />
                  <button
                    onClick={() => setZoomedImage(selected.image_url)}
                    aria-label="Ampliar imagem"
                    className="absolute top-2 right-2 p-1.5 bg-black/50 text-white rounded-lg opacity-0 group-hover:opacity-100 transition-opacity focus:opacity-100"
                  >
                    <ZoomIn className="h-4 w-4" />
                  </button>
                </>
              ) : (
                <div className="w-full h-40 bg-gray-100 rounded-lg flex items-center justify-center">
                  <CameraIcon className="h-10 w-10 text-gray-300" aria-hidden="true" />
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-xs text-muted-foreground mb-1">Placa</p>
                <p className="font-mono font-bold text-lg">{selected.plate}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Confiança</p>
                <ConfidenceBar value={selected.confidence} />
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Câmera</p>
                <p className="font-medium">{selected.camera.name}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Local</p>
                <p className="font-medium">{selected.camera.location ?? "—"}</p>
              </div>
              <div className="col-span-2">
                <p className="text-xs text-muted-foreground mb-1">Detectado em</p>
                <p className="font-medium">{formatDt(selected.detected_at)}</p>
              </div>
              {selected.expires_at && (
                <div className="col-span-2">
                  <p className="text-xs text-muted-foreground mb-1">Expira em</p>
                  <p className="font-medium">{formatDt(selected.expires_at)}</p>
                </div>
              )}
              {selected.vehicle_type && (
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Tipo de veículo</p>
                  <p className="font-medium capitalize">{selected.vehicle_type}</p>
                </div>
              )}
              {selected.vehicle_color && (
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Cor</p>
                  <p className="font-medium capitalize">{selected.vehicle_color}</p>
                </div>
              )}
              {selected.vehicle_make_model && (
                <div className="col-span-2">
                  <p className="text-xs text-muted-foreground mb-1">Marca / Modelo</p>
                  <p className="font-medium">{selected.vehicle_make_model}</p>
                </div>
              )}
              {selected.region_code && (
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Região</p>
                  <p className="font-medium uppercase">{selected.region_code}</p>
                </div>
              )}
              {selected.ocr_engine_used && (
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Motor OCR</p>
                  <p className="font-medium">
                    {selected.ocr_engine_used === "plate_recognizer" ? "Plate Recognizer" : "EasyOCR"}
                  </p>
                </div>
              )}
            </div>

            <div className="flex gap-3">
              {selected.image_url && (
                <a
                  href={selected.image_url}
                  download={`placa-${selected.plate}-${selected.id}.jpg`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 px-3 py-2 border rounded-lg text-sm hover:bg-gray-50 transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50"
                >
                  <Download className="h-4 w-4" aria-hidden="true" />
                  Baixar imagem
                </a>
              )}
              <button
                onClick={() => {
                  const currentPlate = selected.plate;
                  setSelected(null);
                  setPlate(currentPlate);
                  search(1);
                }}
                className="flex-1 py-2 border rounded-lg text-sm hover:bg-gray-50 transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50"
              >
                Ver todas as ocorrências desta placa
              </button>
            </div>
          </div>
        )}
      </Modal>

      {/* ── Lightbox ── */}
      {zoomedImage && (
        <div
          className="fixed inset-0 z-[70] bg-black/90 flex items-center justify-center p-4"
          onClick={() => setZoomedImage(null)}
          role="dialog"
          aria-label="Visualização ampliada"
          aria-modal="true"
        >
          <button
            onClick={() => setZoomedImage(null)}
            aria-label="Fechar visualização"
            className="absolute top-4 right-4 p-2 text-white/80 hover:text-white bg-white/10 rounded-lg"
          >
            <X className="h-5 w-5" />
          </button>
          <img
            src={zoomedImage}
            alt="Imagem ampliada"
            className="max-w-full max-h-full object-contain rounded-lg"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  );
}
