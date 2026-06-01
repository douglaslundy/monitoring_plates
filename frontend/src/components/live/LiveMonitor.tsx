"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import api from "@/lib/api";
import type { Camera } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Camera as CameraIcon, RefreshCw, Play, Pause } from "lucide-react";

type FrameState = {
  image?: string;
  loading?: boolean;
  error?: string;
  updatedAt?: number;
};

export default function LiveMonitor({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [frames, setFrames] = useState<Record<string, FrameState>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(false);

  const rtspCameras = useMemo(
    () => cameras.filter((c) => c.connection_type === "rtsp" && c.is_active),
    [cameras]
  );

  const fetchCameras = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.get<Camera[]>("/api/cameras");
      setCameras(res.data);
    } catch {
      setError("Erro ao carregar cameras.");
    } finally {
      setLoading(false);
    }
  }, []);

  const testCamera = useCallback(async (cameraId: string) => {
    setFrames((s) => ({ ...s, [cameraId]: { ...s[cameraId], loading: true, error: "" } }));
    try {
      const res = await api.post<{ frame_base64: string; content_type: string }>(
        `/api/cameras/${cameraId}/test`
      );
      setFrames((s) => ({
        ...s,
        [cameraId]: {
          image: `data:${res.data.content_type};base64,${res.data.frame_base64}`,
          loading: false,
          updatedAt: Date.now(),
          error: "",
        },
      }));
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setFrames((s) => ({
        ...s,
        [cameraId]: {
          ...s[cameraId],
          loading: false,
          error: typeof detail === "string" ? detail : "Falha ao capturar frame",
        },
      }));
    }
  }, []);

  const refreshAll = useCallback(async () => {
    const ids = rtspCameras.map((c) => c.id);
    await Promise.all(ids.map((id) => testCamera(id)));
  }, [rtspCameras, testCamera]);

  useEffect(() => {
    fetchCameras();
  }, [fetchCameras]);

  useEffect(() => {
    if (!autoRefresh) return;
    refreshAll();
    const id = setInterval(refreshAll, 7000);
    return () => clearInterval(id);
  }, [autoRefresh, refreshAll]);

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
          onClick={() => setAutoRefresh((v) => !v)}
          className="px-3 py-2 rounded border text-sm inline-flex items-center gap-2"
        >
          {autoRefresh ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          {autoRefresh ? "Parar auto refresh" : "Iniciar auto refresh"}
        </button>
        <button
          onClick={refreshAll}
          className="px-3 py-2 rounded bg-black text-white text-sm"
          disabled={rtspCameras.length === 0}
        >
          Testar todas RTSP
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
          {cameras.map((cam) => {
            const frame = frames[cam.id];
            return (
              <div key={cam.id} className="border rounded-lg p-3 bg-white">
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <p className="font-medium">{cam.name}</p>
                    <p className="text-xs text-muted-foreground">{cam.location || "Sem local"}</p>
                  </div>
                  <Badge variant={cam.is_online ? "success" : "secondary"}>
                    {cam.is_online ? "online" : "offline"}
                  </Badge>
                </div>

                {cam.connection_type !== "rtsp" ? (
                  <div className="text-xs p-3 rounded bg-amber-50 text-amber-800 border border-amber-200">
                    Camera tipo agente: sem preview RTSP. Valide por status online/heartbeat.
                  </div>
                ) : (
                  <>
                    <div className="aspect-video rounded border bg-black/5 overflow-hidden mb-2 flex items-center justify-center">
                      {frame?.image ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={frame.image} alt={`Frame ${cam.name}`} className="w-full h-full object-cover" />
                      ) : (
                        <span className="text-xs text-muted-foreground">Sem frame</span>
                      )}
                    </div>
                    <div className="flex items-center justify-between">
                      <button
                        onClick={() => testCamera(cam.id)}
                        className="px-2 py-1 text-xs border rounded"
                        disabled={frame?.loading}
                      >
                        {frame?.loading ? "Testando..." : "Testar camera"}
                      </button>
                      <span className="text-[11px] text-muted-foreground">
                        {frame?.updatedAt ? new Date(frame.updatedAt).toLocaleTimeString("pt-BR") : ""}
                      </span>
                    </div>
                    {frame?.error && <p className="mt-2 text-xs text-red-600">{frame.error}</p>}
                  </>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
