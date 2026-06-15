"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import api from "@/lib/api";
import type { Camera, OperationalMetrics } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { MetricCard } from "@/components/ui/MetricCard";
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
  const [metrics, setMetrics] = useState<OperationalMetrics | null>(null);

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

  const syncCameras = useCallback(async (initial: boolean) => {
    if (initial) {
      setLoading(true);
    }
    setError("");
    try {
      const [camRes, metricsRes] = await Promise.all([
        api.get<Camera[]>("/api/cameras"),
        api.get<OperationalMetrics>("/api/ops/metrics"),
      ]);
      setCameras(camRes.data);
      setMetrics(metricsRes.data);
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

  const detectorVariant = (status: Camera["detector_status"]) => {
    if (status === "healthy") return "success";
    if (status === "warning") return "warning";
    if (status === "degraded") return "danger";
    if (status === "idle") return "secondary";
    return "secondary";
  };

  const detectorLabel = (status: Camera["detector_status"]) => {
    if (status === "healthy") return "saudável";
    if (status === "warning") return "atenção";
    if (status === "degraded") return "degradado";
    if (status === "idle") return "aguardando";
    return "offline";
  };

  const operationalVariant = (status: OperationalMetrics["operational_status"]) => {
    if (status === "healthy") return "success";
    if (status === "warning") return "warning";
    if (status === "degraded") return "danger";
    if (status === "offline") return "secondary";
    return "secondary";
  };

  const operationalLabel = (status: OperationalMetrics["operational_status"]) => {
    if (status === "healthy") return "saudavel";
    if (status === "warning") return "atencao";
    if (status === "degraded") return "degradado";
    if (status === "offline") return "offline";
    return "vazio";
  };

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

      {metrics && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <MetricCard
            title="Saude operacional"
            value={operationalLabel(metrics.operational_status)}
            description={metrics.operational_status_detail}
            className="col-span-2 lg:col-span-1"
          />
          <MetricCard title="Fila OCR" value={metrics.queue_depth} description="frames aguardando" />
          <MetricCard title="FPS medio" value={metrics.avg_preview_fps.toFixed(1)} description="preview total" />
          <MetricCard
            title="Latencia media"
            value={metrics.avg_preview_latency_seconds === null ? "n/d" : `${metrics.avg_preview_latency_seconds.toFixed(1)}s`}
            description="tempo do ultimo frame"
          />
        </div>
      )}

      {metrics && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <MetricCard
            title="Captura media"
            value={metrics.avg_capture_seconds === null ? "n/d" : `${metrics.avg_capture_seconds.toFixed(3)}s`}
            description="tempo medio de recepcao"
          />
          <MetricCard
            title="OCR medio"
            value={metrics.avg_ocr_seconds === null ? "n/d" : `${metrics.avg_ocr_seconds.toFixed(3)}s`}
            description="tempo medio de leitura"
          />
          <MetricCard
            title="Persistencia media"
            value={metrics.avg_persistence_seconds === null ? "n/d" : `${metrics.avg_persistence_seconds.toFixed(3)}s`}
            description="tempo medio de escrita"
          />
          <MetricCard
            title="Sucesso OCR"
            value={metrics.avg_ocr_success_rate === null ? "n/d" : `${(metrics.avg_ocr_success_rate * 100).toFixed(0)}%`}
            description={
              metrics.avg_ocr_false_positive_rate === null
                ? "taxa de falso positivo indisponivel"
                : `${(metrics.avg_ocr_false_positive_rate * 100).toFixed(0)}% de falso positivo`
            }
          />
        </div>
      )}

      {metrics && (
        <div className="flex flex-wrap gap-2 mb-6">
          <Badge variant={operationalVariant(metrics.operational_status)}>
            Operacao {operationalLabel(metrics.operational_status)}
          </Badge>
          <Badge variant="secondary">
            {metrics.online_cameras}/{metrics.total_cameras} cameras online
          </Badge>
          <Badge variant={metrics.degraded_cameras > 0 ? "danger" : "success"}>
            {metrics.degraded_cameras} degradadas
          </Badge>
          <Badge variant={metrics.low_quality_cameras > 0 ? "warning" : "success"}>
            {metrics.low_quality_cameras} com baixa qualidade
          </Badge>
          <Badge variant={metrics.streaming_cameras > 0 ? "success" : "secondary"}>
            {metrics.streaming_cameras} com stream fluido
          </Badge>
        </div>
      )}

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
                  <div className="flex flex-col items-end gap-1">
                    <Badge variant={camera.is_online ? "success" : "secondary"}>
                      {camera.is_online ? "online" : "offline"}
                    </Badge>
                    <Badge variant={detectorVariant(camera.detector_status)}>
                      detector {detectorLabel(camera.detector_status)} ({camera.detector_health_score.toFixed(0)})
                    </Badge>
                    <Badge
                      variant={
                        camera.preview_status === "streaming"
                          ? "success"
                          : camera.preview_status === "degraded"
                            ? "warning"
                            : camera.preview_status === "stale"
                              ? "secondary"
                              : "info"
                      }
                      >
                      {camera.preview_status === "streaming"
                        ? "preview fluido"
                        : camera.preview_status === "degraded"
                          ? "preview lento"
                          : camera.preview_status === "stale"
                            ? "preview parado"
                            : camera.preview_status === "idle"
                              ? "aguardando"
                              : "offline"}
                    </Badge>
                    <Badge
                      variant={
                        camera.quality_label === "excellent" || camera.quality_label === "good"
                          ? "success"
                          : camera.quality_label === "fair"
                            ? "warning"
                            : camera.quality_label === "poor"
                              ? "danger"
                              : "secondary"
                      }
                    >
                      Qualidade{" "}
                      {camera.quality_label === "unknown"
                        ? "indisponível"
                        : `${camera.quality_label} (${camera.quality_score.toFixed(0)})`}
                    </Badge>
                  </div>
                </div>
                {camera.detector_status_detail && (
                  <p className="mb-2 text-[11px] text-muted-foreground">{camera.detector_status_detail}</p>
                )}

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
                <div className="mt-2 grid grid-cols-3 gap-2 text-[11px] text-muted-foreground">
                  <span>{camera.preview_fps.toFixed(1)} fps</span>
                  <span>{camera.preview_frames_last_minute} quadros/min</span>
                  <span>
                    {camera.preview_latency_seconds !== null
                      ? `${camera.preview_latency_seconds.toFixed(1)}s desde o último frame`
                      : "sem telemetria"}
                  </span>
                </div>
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Blur {camera.blur_score.toFixed(1)} | Brilho {camera.brightness.toFixed(0)} | Contraste {camera.contrast.toFixed(0)}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
