"use client";

import { PageHeader } from "@/components/ui/PageHeader";
import { OperationalDashboard } from "@/components/metrics/OperationalDashboard";

export default function MetricasPage() {
  return (
    <div className="p-6">
      <PageHeader
        title="Métricas"
        description="Saúde operacional, pipeline OCR e recursos do servidor em tempo real"
      />
      <OperationalDashboard />
    </div>
  );
}
