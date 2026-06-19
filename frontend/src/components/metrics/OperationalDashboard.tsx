"use client";

import { useCallback, useEffect, useState } from "react";
import api from "@/lib/api";
import { getMe } from "@/lib/auth";
import type { OperationalMetrics } from "@/types";
import { MetricCard } from "@/components/ui/MetricCard";
import { Badge } from "@/components/ui/Badge";
import { SystemResources } from "@/components/live/SystemResources";
import { Trash2 } from "lucide-react";

function ocrVariant(status: OperationalMetrics["ocr_pipeline_status"]) {
  if (status === "healthy") return "success";
  if (status === "warning") return "warning";
  if (status === "degraded") return "danger";
  if (status === "idle") return "secondary";
  return "secondary";
}

function ocrLabel(status: OperationalMetrics["ocr_pipeline_status"]) {
  if (status === "healthy") return "saudavel";
  if (status === "warning") return "atencao";
  if (status === "degraded") return "degradado";
  if (status === "idle") return "aguardando";
  return "vazio";
}

function operationalVariant(status: OperationalMetrics["operational_status"]) {
  if (status === "healthy") return "success";
  if (status === "warning") return "warning";
  if (status === "degraded") return "danger";
  if (status === "offline") return "secondary";
  return "secondary";
}

function operationalLabel(status: OperationalMetrics["operational_status"]) {
  if (status === "healthy") return "saudavel";
  if (status === "warning") return "atencao";
  if (status === "degraded") return "degradado";
  if (status === "offline") return "offline";
  return "vazio";
}

export function OperationalDashboard() {
  const [metrics, setMetrics] = useState<OperationalMetrics | null>(null);
  const [canReset, setCanReset] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState("");

  const loadMetrics = useCallback(async () => {
    try {
      const res = await api.get<OperationalMetrics>("/api/ops/metrics");
      setMetrics(res.data);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    void loadMetrics();
    getMe()
      .then((me) => setCanReset(me.role === "super_admin" || me.role === "client_admin"))
      .catch(() => setCanReset(false));
    const id = window.setInterval(() => void loadMetrics(), 5000);
    return () => window.clearInterval(id);
  }, [loadMetrics]);

  const resetMetrics = useCallback(async () => {
    if (resetting) return;
    setResetting(true);
    setError("");
    try {
      await api.post("/api/ops/metrics/reset");
      await loadMetrics();
    } catch {
      setError("Erro ao resetar metricas.");
    } finally {
      setResetting(false);
    }
  }, [resetting, loadMetrics]);

  return (
    <div>
      <SystemResources />

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
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <MetricCard
            title="Saude OCR"
            value={ocrLabel(metrics.ocr_pipeline_status)}
            description={metrics.ocr_pipeline_status_detail}
            className="col-span-2 lg:col-span-1"
          />
          <MetricCard title="OCR saudavel" value={metrics.ocr_pipeline_healthy_cameras} description="cameras" />
          <MetricCard
            title="OCR em alerta"
            value={metrics.ocr_pipeline_warning_cameras + metrics.ocr_pipeline_degraded_cameras}
            description="cameras"
          />
          <MetricCard title="OCR aguardando" value={metrics.ocr_pipeline_idle_cameras} description="sem leitura ainda" />
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

      {canReset && (
        <div className="mb-4">
          <button
            onClick={() => void resetMetrics()}
            className="px-3 py-2 rounded border border-red-300 text-red-700 text-sm inline-flex items-center gap-2 disabled:opacity-60"
            disabled={resetting}
            title="Zera as métricas acumuladas (OCR, FPS, latência, qualidade) das câmeras"
          >
            <Trash2 className="h-4 w-4" />
            {resetting ? "Resetando..." : "Resetar métricas"}
          </button>
        </div>
      )}

      {error && <div className="mb-4 p-3 border rounded text-red-700 bg-red-50">{error}</div>}
    </div>
  );
}
