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
  const [previewMode, setPreviewMode] = useState<Record<string, "stream" | "fallback">>({});

  const activeCameras = useMemo(
    () => cameras.filter((camera) => camera.is_active),
    [cameras]
  );

  const buildStreamUrl = useCallback((cameraId: string) => {
    return `/api/cameras/${cameraId}/stream?t=${Date.now()}`;
  }, []);

  const restoreStreamPreview = useCallback((cameraId: string) => {
    setPreviewUrls((current) => ({ ...current, [cameraId]: buildStreamUrl(cameraId) }));
    setPreviewMode((current) => ({ ...current, [cameraId]: "stream" }));
    setPreviewStatus((current) => ({ ...current, [cameraId]: "loading" }));
  }, [buildStreamUrl]);

  const loadFallbackPreview = useCallback(async (cameraId: string) => {
    try {
      const response = await api.get<{ image_url: string | null }>(`/api/cameras/${cameraId}/last-frame`);
      const imageUrl = response.data.image_url;
      if (!imageUrl) {
        throw new Error("preview-not-available");
      }

      const delimiter = imageUrl.includes("?") ? "&" : "?";
      setPreviewUrls((current) => ({ ...current, [cameraId]: `${imageUrl}${delimiter}t=${Date.now()}` }));
      setPreviewMode((current) => ({ ...current, [cameraId]: "fallback" }));
      setPreviewStatus((current) => ({ ...current, [cameraId]: "ready" }));
      return true;
    } catch {
      setPreviewStatus((current) => ({ ...current, [cameraId]: "error" }));
      return false;
    }
  }, []);

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
      setPreviewMode((current) => {
        const next: Record<string, "stream" | "fallback"> = { ...current };
        for (const camera of res.data) {
          if (camera.is_active && (camera.connection_type === "rtsp" || camera.connection_type === "agent")) {
            next[camera.id] = "stream";
          }
        }
        return next;
      });
      setPreviewUrls((current) => {
        const next = { ...current };
        for (const camera of res.data) {
          if (camera.is_active && (camera.connection_type === "rtsp" || camera.connection_type === "agent")) {
            next[camera.id] = buildStreamUrl(camera.id);
          }
        }
        return next;
      });
    } catch {
      setError("Erro ao carregar cameras.");
    } finally {
      setLoading(false);
    }
  }, [buildStreamUrl]);

  useEffect(() => {
    fetchCameras();
  }, [fetchCameras]);

  const refreshFallbackPreviews = useCallback(async () => {
    const fallbackItems = activeCameras.filter((camera) => previewMode[camera.id] === "fallback");
    if (fallbackItems.length === 0) return;

    const results = await Promise.allSettled(fallbackItems.map(async (camera) => {
      await loadFallbackPreview(camera.id);
      return camera.id;
    }));

    if (results.some((result) => result.status === "rejected")) {
      setError("Erro ao atualizar previews.");
    } else {
      setError("");
    }
  }, [activeCameras, loadFallbackPreview, previewMode]);

  useEffect(() => {
    if (activeCameras.length === 0) return;

    const interval = window.setInterval(() => {
      void refreshFallbackPreviews();
    }, 2500);

    return () => window.clearInterval(interval);
  }, [activeCameras.length, refreshFallbackPreviews]);

  const reloadAllStreams = useCallback(() => {
    setError("");
    for (const camera of activeCameras) {
      if (camera.connection_type === "rtsp" || camera.connection_type === "agent") {
        restoreStreamPreview(camera.id);
      }
    }
  }, [activeCameras, restoreStreamPreview]);

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
                        if (previewMode[camera.id] === "stream") {
                          void loadFallbackPreview(camera.id);
                          return;
                        }
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
                    onClick={() => restoreStreamPreview(camera.id)}
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
