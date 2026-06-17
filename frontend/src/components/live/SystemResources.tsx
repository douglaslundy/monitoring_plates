"use client";

import { useEffect, useState } from "react";
import api from "@/lib/api";
import type { SystemMetrics } from "@/types";
import { Cpu, HardDrive, MemoryStick, type LucideIcon } from "lucide-react";

function UsageBar({ percent }: { percent: number }) {
  const pct = Math.min(100, Math.max(0, percent));
  const color = pct >= 90 ? "bg-red-500" : pct >= 70 ? "bg-amber-500" : "bg-emerald-500";
  return (
    <div className="h-2 w-full rounded-full bg-gray-100">
      <div className={`h-2 rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function ResourceCard({
  icon: Icon,
  title,
  percent,
  primary,
  secondary,
}: {
  icon: LucideIcon;
  title: string;
  percent: number;
  primary: string;
  secondary: string;
}) {
  return (
    <div className="rounded-xl border bg-white p-4 shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
          {title}
        </div>
        <span className="text-sm font-semibold">{percent.toFixed(0)}%</span>
      </div>
      <UsageBar percent={percent} />
      <div className="mt-2 flex justify-between text-xs text-muted-foreground">
        <span>{primary}</span>
        <span>{secondary}</span>
      </div>
    </div>
  );
}

/** Painel "Recursos do servidor" (CPU/RAM/disco). Some para não-admin (403). */
export function SystemResources() {
  const [data, setData] = useState<SystemMetrics | null>(null);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const res = await api.get<SystemMetrics>("/api/ops/system");
        if (active) setData(res.data);
      } catch {
        if (active) setHidden(true); // 403 (não-admin) ou erro → esconde o painel
      }
    };
    void load();
    const id = window.setInterval(load, 5000);
    return () => {
      active = false;
      window.clearInterval(id);
    };
  }, []);

  if (hidden || !data) return null;

  if (!data.available) {
    return (
      <div className="mb-6 rounded-xl border bg-white p-4 text-sm text-muted-foreground">
        Recursos do servidor indisponíveis no momento.
      </div>
    );
  }

  const memUsedGb = (data.mem_used_mb / 1024).toFixed(1);
  const memTotalGb = (data.mem_total_mb / 1024).toFixed(1);
  const memFreeGb = (data.mem_available_mb / 1024).toFixed(1);

  return (
    <div className="mb-6">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        Recursos do servidor
      </h2>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <ResourceCard
          icon={Cpu}
          title="CPU"
          percent={data.cpu_percent}
          primary={`${data.cpu_count} núcleos`}
          secondary={`load ${data.load_avg_1m.toFixed(2)}`}
        />
        <ResourceCard
          icon={MemoryStick}
          title="Memória"
          percent={data.mem_percent}
          primary={`${memUsedGb} / ${memTotalGb} GB`}
          secondary={`${memFreeGb} GB livre`}
        />
        <ResourceCard
          icon={HardDrive}
          title="Disco"
          percent={data.disk_percent}
          primary={`${data.disk_used_gb.toFixed(1)} / ${data.disk_total_gb.toFixed(1)} GB`}
          secondary={`${data.disk_free_gb.toFixed(1)} GB livre`}
        />
      </div>
    </div>
  );
}
