"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import api from "@/lib/api";
import type { Camera } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Camera as CameraIcon, RefreshCw, Video, AlertTriangle, Radio } from "lucide-react";


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
  const [webrtcUrls, setWebrtcUrls] = useState<Record<string, string | null>>({});
  // Live em tempo real (WebRTC do go2rtc) é o PADRÃO quando disponível — é o
  // vídeo ao vivo de verdade. O botão "Ver preview" troca para o MJPEG
  // (same-origin via /api), útil de fora da LAN do go2rtc, onde o WebRTC (que
  // aponta para o IP da LAN) não conecta.
  const [webrtcOn, setWebrtcOn] = useState<Record<string, boolean>>({});
  const webrtcFetched = useRef<Set<string>>(new Set());

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

  const previewIntervalMs = useCallback((camera: Camera) => {
    const seconds = camera.preview_refresh_seconds > 0 ? camera.preview_refresh_seconds : 2.5;
    return Math.max(500, Math.round(seconds * 1000));
  }, []);

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

  const syncCameras = useCallback(async (initial: boolean) => {
    if (initial) {
      setLoading(true);
    }
    setError("");
    try {
      const camRes = await api.get<Camera[]>("/api/cameras");
      setCameras(camRes.data);
    } catch {
      setError("Erro ao carregar cameras.");
    } finally {
      if (initial) {
        setLoading(false);
      }
    }
  }, [buildStreamUrl]);

  useEffect(() => {
    void syncCameras(true);
  }, [syncCameras]);

  const toggleWebrtc = useCallback((cameraId: string) => {
    setWebrtcOn((current) => ({ ...current, [cameraId]: !current[cameraId] }));
  }, []);

  // Busca a URL do live WebRTC (go2rtc) por câmera RTSP no backend (com
  // verificação de acesso). O backend resolve o host público do go2rtc.
  useEffect(() => {
    for (const camera of cameras) {
      if (camera.connection_type !== "rtsp" || webrtcFetched.current.has(camera.id)) continue;
      webrtcFetched.current.add(camera.id);
      api
        .get<{ enabled: boolean; url: string | null }>(`/api/cameras/${camera.id}/webrtc`)
        .then((res) => {
          setWebrtcUrls((current) => ({ ...current, [camera.id]: res.data.enabled ? res.data.url : null }));
        })
        .catch(() => {
          setWebrtcUrls((current) => ({ ...current, [camera.id]: null }));
        });
    }
  }, [cameras]);

  useEffect(() => {
    if (cameras.length === 0) return;

    setPreviewMode((current) => {
      const next: Record<string, "stream" | "fallback"> = { ...current };
      for (const camera of cameras) {
        if (camera.is_active && (camera.connection_type === "rtsp" || camera.connection_type === "agent")) {
          next[camera.id] = current[camera.id] ?? "stream";
        }
      }
      return next;
    });

    setPreviewStatus((current) => {
      const next: Record<string, "loading" | "ready" | "error"> = { ...current };
      for (const camera of cameras) {
        next[camera.id] = current[camera.id] ?? "loading";
      }
      return next;
    });

    setPreviewUrls((current) => {
      const next = { ...current };
      for (const camera of cameras) {
        if (!next[camera.id] && camera.is_active && (camera.connection_type === "rtsp" || camera.connection_type === "agent")) {
          next[camera.id] = buildStreamUrl(camera.id);
        }
      }
      return next;
    });
  }, [buildStreamUrl, cameras]);

  useEffect(() => {
    if (activeCameras.length === 0) return;

    const interval = window.setInterval(() => {
      void syncCameras(false);
    }, 2500);

    return () => window.clearInterval(interval);
  }, [activeCameras.length, syncCameras]);

  useEffect(() => {
    if (activeCameras.length === 0) return;

    const timers = activeCameras
      .filter((camera) => previewMode[camera.id] === "fallback")
      .map((camera) =>
        window.setInterval(() => {
          void loadFallbackPreview(camera.id);
        }, previewIntervalMs(camera))
      );

    return () => {
      for (const timer of timers) {
        window.clearInterval(timer);
      }
    };
  }, [activeCameras, loadFallbackPreview, previewIntervalMs, previewMode]);

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
          onClick={() => void syncCameras(true)}
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
            const webrtcUrl = webrtcUrls[camera.id];
            const webrtcAvailable = camera.connection_type === "rtsp" && !!webrtcUrl;
            // Padrão = WebRTC (vídeo ao vivo). O operador pode trocar para o
            // preview MJPEG (botão "Ver preview") se o WebRTC não conectar.
            const useWebrtc = webrtcAvailable && (webrtcOn[camera.id] ?? true);

            return (
              <div key={camera.id} className="border rounded-lg p-3 bg-white shadow-sm">
                <div className="mb-2">
                  <p className="font-medium">{camera.name}</p>
                  <p className="text-xs text-muted-foreground">{camera.location || "Sem local"}</p>
                </div>

                <div className="relative aspect-video rounded border bg-black overflow-hidden mb-2">
                  {useWebrtc ? (
                    <iframe
                      title={`Live ${camera.name}`}
                      src={webrtcUrl ?? undefined}
                      className="h-full w-full border-0"
                      allow="autoplay; fullscreen; picture-in-picture"
                    />
                  ) : streamSrc ? (
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

                  {!useWebrtc && status !== "ready" && (
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

                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-1.5">
                    <Badge variant={camera.is_online ? "success" : "secondary"}>
                      {camera.is_online ? "online" : "offline"}
                    </Badge>
                    <span className="text-[11px] text-muted-foreground font-mono">
                      {camera.connection_type.toUpperCase()}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => restoreStreamPreview(camera.id)}
                      className="px-2 py-1 text-xs border rounded inline-flex items-center gap-1"
                    >
                      <RefreshCw className="h-3 w-3" />
                      Reconectar
                    </button>
                    {webrtcAvailable && (
                      <button
                        onClick={() => toggleWebrtc(camera.id)}
                        className={`px-2 py-1 text-xs border rounded inline-flex items-center gap-1 ${
                          useWebrtc ? "bg-black text-white" : ""
                        }`}
                        title="Vídeo ao vivo em HD (WebRTC). Requer acesso à rede local da câmera."
                      >
                        <Radio className="h-3 w-3" />
                        {useWebrtc ? "Preview" : "Ao vivo HD"}
                      </button>
                    )}
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2 text-[11px] text-muted-foreground">
                  <span>{camera.preview_fps.toFixed(1)} fps</span>
                  <span>{camera.preview_frames_last_minute} quadros/min</span>
                  <span>
                    {camera.preview_latency_seconds !== null
                      ? `${camera.preview_latency_seconds.toFixed(1)}s desde o último frame`
                      : "sem telemetria"}
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
