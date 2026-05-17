"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { Camera } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Camera as CameraIcon, Video, Cpu } from "lucide-react";

export default function ClientCamerasPage() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchCameras = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.get<Camera[]>("/api/cameras");
      setCameras(res.data);
    } catch {
      setError("Erro ao carregar câmeras. Verifique sua conexão.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCameras();
  }, [fetchCameras]);

  function formatLastSeen(dateStr: string | null) {
    if (!dateStr) return "Nunca conectou";
    const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 60000);
    if (diff < 1) return "Agora mesmo";
    if (diff < 60) return `${diff}m atrás`;
    const h = Math.floor(diff / 60);
    if (h < 24) return `${h}h atrás`;
    return new Date(dateStr).toLocaleDateString("pt-BR");
  }

  const online = cameras.filter((c) => c.is_online).length;

  return (
    <div className="p-6">
      <PageHeader
        title="Minhas Câmeras"
        description="Câmeras de monitoramento do seu sistema"
      />

      {cameras.length > 0 && (
        <div className="flex gap-4 mb-6 text-sm">
          <span className="text-muted-foreground">
            {cameras.length} câmera{cameras.length !== 1 ? "s" : ""}
          </span>
          <span className="text-green-600 font-medium">{online} online</span>
          <span className="text-gray-400">{cameras.length - online} offline</span>
        </div>
      )}

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={fetchCameras} className="underline text-xs ml-4">
            Tentar novamente
          </button>
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="border rounded-lg p-4 animate-pulse bg-gray-50 h-36"
            />
          ))}
        </div>
      ) : cameras.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <CameraIcon className="h-12 w-12 mx-auto mb-3 opacity-30" />
          <p>Nenhuma câmera configurada ainda.</p>
          <p className="text-xs mt-1">
            Fale com o administrador para adicionar câmeras.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {cameras.map((cam) => (
            <div
              key={cam.id}
              className="border rounded-lg p-4 bg-white shadow-sm"
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex-1 min-w-0">
                  <p className="font-semibold truncate">{cam.name}</p>
                  {cam.location && (
                    <p className="text-xs text-muted-foreground truncate">
                      {cam.location}
                    </p>
                  )}
                </div>
                <div className="ml-2 shrink-0">
                  {cam.is_online ? (
                    <span className="flex items-center gap-1 text-xs text-green-600">
                      <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
                      </span>
                      Online
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-xs text-gray-400">
                      <span className="h-2 w-2 rounded-full bg-gray-300" />
                      Offline
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2 mb-3">
                <Badge
                  variant={
                    cam.connection_type === "rtsp" ? "default" : "secondary"
                  }
                >
                  <span className="flex items-center gap-1">
                    {cam.connection_type === "rtsp" ? (
                      <>
                        <Video className="h-3 w-3" /> RTSP
                      </>
                    ) : (
                      <>
                        <Cpu className="h-3 w-3" /> Agente
                      </>
                    )}
                  </span>
                </Badge>
              </div>

              <p className="text-xs text-muted-foreground">
                Última atividade: {formatLastSeen(cam.last_seen_at)}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
