import { FaceDetectionsHistory } from "@/components/faces/FaceDetectionsHistory";

export default function AdminFaceDetectionsPage() {
  return (
    <FaceDetectionsHistory
      viewStorageKey="admin-face-detections-view"
      title="Reconhecimento facial"
      description="Detecções de faces de todas as câmeras"
    />
  );
}
