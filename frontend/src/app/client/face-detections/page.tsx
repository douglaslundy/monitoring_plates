import { FaceDetectionsHistory } from "@/components/faces/FaceDetectionsHistory";

export default function ClientFaceDetectionsPage() {
  return (
    <FaceDetectionsHistory
      title="Reconhecimento facial"
      description="Pessoas reconhecidas pelas câmeras com faces ativas"
    />
  );
}
