"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import api from "@/lib/api";
import type { Camera } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Camera as CameraIcon, RefreshCw, Video, AlertTriangle } from "lucide-react";

export default function LiveMonitor({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [previewUrls, setPreviewUrls] = useState<Record<string, string>>({});
  const [previewStatus, setPreviewStatus] = useState<Record<string, "loading" | "ready" | "error">>({});

  const activeCameras = useMemo(
    () => cameras.filter((camera) => camera.is_active),
    [cameras]
  );

  const fetchCameras = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.get<Camera[]>("/api/cameras");
      setCameras(res.data);
      setPreviewStatus((current) => {
        const next: Record<string, "loading" | "ready" | "error"> = { ...current };
        for (const camera of res.data) {
          next[camera.id] = current[camera.id] ?? "loading";
        }
        return next;
      });
    } catch {
      setError("Erro ao carregar cameras.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCameras();
  }, [fetchCameras]);

  const refreshPreviews = useCallback(async () => {
    const items = activeCameras.filter((camera) => camera.connection_type === "rtsp" || camera.connection_type === "agent");
    if (items.length === 0) return;

    try {
      const results = await Promise.allSettled(
        items.map(async (camera) => {
          const response = await api.get<{ image_url: string | null }>(`/api/cameras/${camera.id}/last-frame`);
          const imageUrl = response.data.image_url;
          if (!imageUrl) {
            throw new Error("preview-not-available");
          }
          return { cameraId: camera.id, imageUrl };
        })
      );

      setPreviewUrls((current) => {
        const next = { ...current };
        results.forEach((result) => {
          if (result.status === "fulfilled") {
            const delimiter = result.value.imageUrl.includes("?") ? "&" : "?";
            next[result.value.cameraId] = `${result.value.imageUrl}${delimiter}t=${Date.now()}`;
          }
        });
        return next;
      });

      setPreviewStatus((current) => {
        const next = { ...current };
        results.forEach((result, index) => {
          const cameraId = items[index]?.id;
          if (!cameraId) return;
          next[cameraId] = result.status === "fulfilled" ? "ready" : "error";
        });
        return next;
      });
      setError("");
    } catch {
      setError("Erro ao atualizar previews.");
      setPreviewStatus((current) => {
        const next = { ...current };
        for (const camera of items) {
          next[camera.id] = "error";
        }
        return next;
      });
    }
  }, [activeCameras]);

  useEffect(() => {
    if (activeCameras.length === 0) return;

    void refreshPreviews();
    const interval = window.setInterval(() => {
      void refreshPreviews();
    }, 1200);

    return () => window.clearInterval(interval);
  }, [activeCameras.length, refreshPreviews]);

  const reloadAllStreams = useCallback(() => {
    void refreshPreviews();
  }, [refreshPreviews]);

  return (
    <div className="p-6">
      <PageHeader title={title} description={description} />

      <div className="mb-4 flex flex-wrap gap-2">
        <button
          onClick={fetchCameras}
          className="px-3 py-2 rounded border text-sm inline-flex items-center gap-2"
        >
          <RefreshCw className="h-4 w-4" />
          Atualizar cameras
        </button>
        <button
          onClick={reloadAllStreams}
          className="px-3 py-2 rounded bg-black text-white text-sm inline-flex items-center gap-2"
          disabled={activeCameras.length === 0}
        >
          <Video className="h-4 w-4" />
          Recarregar streams
        </button>
      </div>

      {error && <div className="mb-4 p-3 border rounded text-red-700 bg-red-50">{error}</div>}

      {loading ? (
        <p>Carregando...</p>
      ) : cameras.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <CameraIcon className="h-12 w-12 mx-auto mb-3 opacity-30" />
          <p>Nenhuma camera cadastrada.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {cameras.map((camera) => {
            const status = previewStatus[camera.id] ?? "loading";
            const streamSrc = previewUrls[camera.id];

            return (
              <div key={camera.id} className="border rounded-lg p-3 bg-white shadow-sm">
                <div className="flex items-center justify-between mb-2 gap-3">
                  <div>
                    <p className="font-medium">{camera.name}</p>
                    <p className="text-xs text-muted-foreground">{camera.location || "Sem local"}</p>
                  </div>
                  <Badge variant={camera.is_online ? "success" : "secondary"}>
                    {camera.is_online ? "online" : "offline"}
                  </Badge>
                </div>

                <div className="relative aspect-video rounded border bg-black overflow-hidden mb-2">
                  {streamSrc ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={streamSrc}
                      alt={`Live ${camera.name}`}
                      className="h-full w-full object-cover"
                      onLoad={() => {
                        setPreviewStatus((current) => ({ ...current, [camera.id]: "ready" }));
                      }}
                      onError={() => {
                        setPreviewStatus((current) => ({ ...current, [camera.id]: "error" }));
                      }}
                    />
                  ) : (
                    <div className="absolute inset-0 bg-gradient-to-br from-black via-slate-900 to-zinc-950" />
                  )}

                  {status !== "ready" && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/45 text-white px-4 text-center">
                      {status === "loading" ? (
                        <>
                          <Video className="h-5 w-5 mb-2 animate-pulse" />
                          <p className="text-xs">Conectando stream...</p>
                        </>
                      ) : (
                        <>
                          <AlertTriangle className="h-5 w-5 mb-2" />
                          <p className="text-xs">Stream indisponivel</p>
                        </>
                      )}
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-between">
                  <button
                    onClick={() => void refreshPreviews()}
                    className="px-2 py-1 text-xs border rounded inline-flex items-center gap-1"
                  >
                    <RefreshCw className="h-3 w-3" />
                    Reconectar
                  </button>
                  <span className="text-[11px] text-muted-foreground">
                    {camera.connection_type.toUpperCase()}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
