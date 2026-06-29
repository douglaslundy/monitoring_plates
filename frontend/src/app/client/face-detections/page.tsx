import { FaceDetectionsHistory } from "@/components/faces/FaceDetectionsHistory";

export default function ClientFaceDetectionsPage() {
  return (
    <FaceDetectionsHistory
      viewStorageKey="client-face-detections-view"
      title="Reconhecimento facial"
      description="Pessoas reconhecidas pelas câmeras com faces ativas"
    />
  );
}
