"use client";

import { useEffect, useState } from "react";
import api from "@/lib/api";
import { extractErrorMessage } from "@/lib/errors";
import { PageHeader } from "@/components/ui/PageHeader";
import type { FaceDetection } from "@/types";
import { ScanFace, UserRound, X } from "lucide-react";

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

  return (
    <div className="p-6 space-y-6">
      <PageHeader title={title} description={description} />

      {error && (
        <div className="p-3 rounded-lg border border-red-200 bg-red-50 text-sm text-red-700">{error}</div>
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
            <div key={d.id} className="bg-white rounded-xl border shadow-sm overflow-hidden">
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
    </div>
  );
}
