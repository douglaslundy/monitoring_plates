"use client";

import { useEffect, useMemo, useState } from "react";
import api from "@/lib/api";
import { extractErrorMessage } from "@/lib/errors";
import { PageHeader } from "@/components/ui/PageHeader";
import type { FaceDetection } from "@/types";
import { ScanFace, Trash2, UserRound, X } from "lucide-react";

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(date);
}

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

export function FaceDetectionsHistory({ title, description }: { title: string; description: string }) {
  const [items, setItems] = useState<FaceDetection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lightbox, setLightbox] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    api.get<{ role: string }>("/api/auth/me").then((r) => {
      setIsAdmin(r.data.role === "super_admin" || r.data.role === "client_admin");
    }).catch(() => {});
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      setLoading(true);
      setError("");
      try {
        const res = await api.get<FaceDetection[]>("/api/face-detections?limit=200");
        if (active) setItems(res.data);
      } catch (e: unknown) {
        if (active) setError(extractErrorMessage(e, "Não foi possível carregar as detecções de faces."));
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const allSelected = useMemo(
    () => items.length > 0 && items.every((i) => selectedIds.has(i.id)),
    [items, selectedIds]
  );

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(items.map((i) => i.id)));
    }
  }

  async function handleBulkDelete() {
    setDeleting(true);
    try {
      await api.delete("/api/face-detections/bulk", { data: { ids: [...selectedIds] } });
      setItems((prev) => prev.filter((i) => !selectedIds.has(i.id)));
      setSelectedIds(new Set());
      setConfirmDelete(false);
    } catch (e: unknown) {
      setError(extractErrorMessage(e, "Erro ao apagar detecções."));
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <PageHeader title={title} description={description} />

      {error && (
        <div className="p-3 rounded-lg border border-red-200 bg-red-50 text-sm text-red-700">{error}</div>
      )}

      {isAdmin && items.length > 0 && (
        <div className="flex items-center gap-3 flex-wrap">
          <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
            <input
              type="checkbox"
              className="h-4 w-4 rounded"
              checked={allSelected}
              onChange={toggleSelectAll}
            />
            Selecionar todas
          </label>
          {selectedIds.size > 0 && (
            <button
              onClick={() => setConfirmDelete(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm font-medium"
            >
              <Trash2 className="h-4 w-4" />
              Apagar selecionadas ({selectedIds.size})
            </button>
          )}
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-40 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="bg-white rounded-xl border shadow-sm p-10 text-center text-muted-foreground">
          <ScanFace className="h-14 w-14 mx-auto mb-4 opacity-15" />
          <p className="text-base font-medium">Nenhuma detecção de face</p>
          <p className="text-sm mt-1">As detecções aparecerão aqui quando câmeras com faces ativas reconhecerem pessoas.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((d) => (
            <div
              key={d.id}
              className={`bg-white rounded-xl border shadow-sm overflow-hidden relative ${
                selectedIds.has(d.id) ? "ring-2 ring-red-500" : ""
              }`}
            >
              {isAdmin && (
                <label className="absolute top-2 left-2 z-10 cursor-pointer" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded"
                    checked={selectedIds.has(d.id)}
                    onChange={() => toggleSelect(d.id)}
                  />
                </label>
              )}
              <button
                type="button"
                onClick={() => d.image_url && setLightbox(d.image_url)}
                className="block w-full aspect-video bg-gray-100 relative"
                aria-label="Ampliar imagem"
              >
                {d.image_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={d.image_url} alt={d.person_name ?? "Desconhecido"} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-gray-300">
                    <UserRound className="h-10 w-10" />
                  </div>
                )}
              </button>
              <div className="p-3 space-y-1">
                <div className="flex items-center gap-2">
                  <UserRound className="h-4 w-4 text-primary shrink-0" />
                  <span className={`font-semibold text-sm ${d.person_name ? "" : "text-muted-foreground italic"}`}>
                    {d.person_name ?? "Desconhecido"}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">{d.camera_name ?? "—"}</p>
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>{formatDateTime(d.detected_at)}</span>
                  <span title="Duração rastreada">⏱ {formatDuration(d.tracked_seconds)}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {lightbox && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
          onClick={() => setLightbox(null)}
        >
          <button
            onClick={() => setLightbox(null)}
            className="absolute top-4 right-4 p-2 rounded-lg bg-white/10 hover:bg-white/20 text-white"
            aria-label="Fechar"
          >
            <X className="h-5 w-5" />
          </button>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={lightbox} alt="Detecção" className="max-h-[90vh] max-w-[90vw] object-contain rounded-lg" />
        </div>
      )}

      {confirmDelete && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-md w-full space-y-4">
            <h2 className="text-lg font-semibold">Confirmar exclusão</h2>
            <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
              Você está prestes a apagar <strong>{selectedIds.size}</strong> detecção(ões) de face permanentemente.
              Os arquivos de imagem também serão removidos. Esta ação não pode ser desfeita.
            </div>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setConfirmDelete(false)}
                disabled={deleting}
                className="px-4 py-2 rounded-lg border text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
              >
                Cancelar
              </button>
              <button
                onClick={handleBulkDelete}
                disabled={deleting}
                className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm font-medium disabled:opacity-50"
              >
                {deleting ? "Apagando..." : "Apagar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
