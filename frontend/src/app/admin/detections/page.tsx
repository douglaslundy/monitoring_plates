"use client";

import DetectionHistory from "@/components/detections/DetectionHistory";

export default function AdminDetectionsPage() {
  return (
    <DetectionHistory
      title="Histórico de Detecções"
      description="Veículos, pessoas e animais detectados em todas as câmeras."
    />
  );
}
