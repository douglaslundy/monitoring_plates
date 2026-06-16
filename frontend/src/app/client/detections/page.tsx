"use client";

import DetectionHistory from "@/components/detections/DetectionHistory";

export default function ClientDetectionsPage() {
  return (
    <DetectionHistory
      title="Histórico de Detecções"
      description="Veículos, pessoas e animais com frame, câmera, tipo e período."
    />
  );
}
