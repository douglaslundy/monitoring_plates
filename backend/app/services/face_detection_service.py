"""Motor LOCAL de faces com OpenCV Zoo: YuNet (detecção) + SFace (embedding).

Espelha o padrão de `vehicle_detection_service`: importações de `cv2`/`numpy`
preguiçosas (mockáveis nos testes e tolerantes à ausência), lock para carregar
os modelos uma única vez, e modo degradado quando o modelo/cv2 não está
disponível (`detect` -> [], `embed` -> None).

Os modelos ONNX (licença comercial OK) são embutidos na imagem Docker no build;
os caminhos vêm de FACE_MODEL_DIR (cai p/ MODELS_DIR) + FACE_DETECTOR_MODEL /
FACE_RECOGNIZER_MODEL.
"""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from io import BytesIO
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FaceBox:
    bbox_x: int
    bbox_y: int
    bbox_w: int
    bbox_h: int
    confidence: float
    crop_bytes: bytes


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Similaridade de cosseno em Python puro (sem numpy obrigatório)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def _model_dir() -> str:
    return settings.FACE_MODEL_DIR or os.getenv("MODELS_DIR", "/app/models")


def _detector_path() -> str:
    return os.path.join(_model_dir(), settings.FACE_DETECTOR_MODEL)


def _recognizer_path() -> str:
    return os.path.join(_model_dir(), settings.FACE_RECOGNIZER_MODEL)


class OpenCVFaceEngine:
    """Detecção (YuNet) + embedding (SFace) via OpenCV, CPU, offline."""

    def __init__(self) -> None:
        self._detector = None
        self._recognizer = None
        self._lock = threading.Lock()
        self._unavailable = False

    # ── Carregamento dos modelos ───────────────────────────────────────────
    def _get_detector(self):
        if self._detector is not None or self._unavailable:
            return self._detector
        with self._lock:
            if self._detector is not None or self._unavailable:
                return self._detector
            try:
                import cv2
            except Exception as exc:  # pragma: no cover - ambiente sem cv2
                logger.warning("cv2 indisponível (%s) — faces em modo degradado", exc)
                self._unavailable = True
                return None
            path = _detector_path()
            if not os.path.exists(path):
                logger.warning("Modelo YuNet não encontrado em %s — modo degradado", path)
                self._unavailable = True
                return None
            try:
                # input size é redefinido por frame em detect(); 320x320 é placeholder.
                self._detector = cv2.FaceDetectorYN_create(
                    path, "", (320, 320), settings.FACE_MIN_DETECT_SCORE
                )
                logger.info("YuNet carregado de %s", path)
            except Exception as exc:
                logger.error("Falha ao carregar YuNet (%s) — modo degradado", exc)
                self._unavailable = True
                self._detector = None
            return self._detector

    def _get_recognizer(self):
        if self._recognizer is not None:
            return self._recognizer
        with self._lock:
            if self._recognizer is not None:
                return self._recognizer
            try:
                import cv2
            except Exception:  # pragma: no cover
                return None
            path = _recognizer_path()
            if not os.path.exists(path):
                logger.warning("Modelo SFace não encontrado em %s — embed degradado", path)
                return None
            try:
                self._recognizer = cv2.FaceRecognizerSF_create(path, "")
                logger.info("SFace carregado de %s", path)
            except Exception as exc:
                logger.error("Falha ao carregar SFace (%s) — embed degradado", exc)
                self._recognizer = None
            return self._recognizer

    def warmup(self) -> None:
        self._get_detector()
        self._get_recognizer()

    # ── API pública ────────────────────────────────────────────────────────
    def detect_and_embed(
        self, image_bytes: bytes
    ) -> Optional[tuple["FaceBox", Optional[list[float]]]]:
        """YuNet + SFace em passagem única — elimina o double-YuNet.

        Retorna (face_box, embedding) para o maior rosto, ou None se não
        encontrado. Embedding pode ser None se SFace não estiver disponível.
        """
        detector = self._get_detector()
        if detector is None:
            return None
        image = self._decode_image(image_bytes)
        if image is None:
            return None
        faces = self._run_detector(detector, image)
        if faces is None or len(faces) == 0:
            return None
        try:
            import numpy as np

            h, w = image.shape[:2]
            faces_arr = np.asarray(faces, dtype=np.float32)
            idx = int(np.argmax(faces_arr[:, 2] * faces_arr[:, 3]))
            face_row = faces_arr[idx]

            x, y, fw, fh = int(face_row[0]), int(face_row[1]), int(face_row[2]), int(face_row[3])
            score = float(face_row[-1]) if len(face_row) >= 15 else 1.0
            x0, y0 = max(0, x), max(0, y)
            x1, y1 = min(w, x + fw), min(h, y + fh)
            if x1 <= x0 or y1 <= y0:
                return None
            crop = self._upscale_to_min(image[y0:y1, x0:x1])
            crop_bytes = self._encode_jpeg(crop)
            if not crop_bytes:
                return None
            face_box = FaceBox(
                bbox_x=x0, bbox_y=y0, bbox_w=x1 - x0, bbox_h=y1 - y0,
                confidence=round(score, 3), crop_bytes=crop_bytes,
            )
            embedding: Optional[list[float]] = None
            recognizer = self._get_recognizer()
            if recognizer is not None:
                try:
                    aligned = recognizer.alignCrop(image, face_row)
                    feature = recognizer.feature(aligned)
                    embedding = np.asarray(feature).flatten().astype(float).tolist()
                except Exception as exc:
                    logger.warning("SFace embed falhou na passagem única (%s)", exc)
            return (face_box, embedding)
        except Exception as exc:
            logger.warning("detect_and_embed falhou (%s)", exc)
            return None

    def detect(self, image_bytes: bytes) -> list[FaceBox]:
        detector = self._get_detector()
        if detector is None:
            return []
        image = self._decode_image(image_bytes)
        if image is None:
            return []
        faces = self._run_detector(detector, image)
        if faces is None:
            return []

        h, w = image.shape[:2]
        results: list[FaceBox] = []
        for face in faces:
            x, y, fw, fh = int(face[0]), int(face[1]), int(face[2]), int(face[3])
            score = float(face[-1]) if len(face) >= 15 else 1.0
            x0, y0 = max(0, x), max(0, y)
            x1, y1 = min(w, x + fw), min(h, y + fh)
            if x1 <= x0 or y1 <= y0:
                continue
            crop = self._upscale_to_min(image[y0:y1, x0:x1])
            crop_bytes = self._encode_jpeg(crop)
            if not crop_bytes:
                continue
            results.append(
                FaceBox(
                    bbox_x=x0,
                    bbox_y=y0,
                    bbox_w=x1 - x0,
                    bbox_h=y1 - y0,
                    confidence=round(score, 3),
                    crop_bytes=crop_bytes,
                )
            )
        # Maior rosto primeiro (área).
        results.sort(key=lambda b: b.bbox_w * b.bbox_h, reverse=True)
        return results

    def embed(self, image_bytes: bytes) -> Optional[list[float]]:
        detector = self._get_detector()
        recognizer = self._get_recognizer()
        if detector is None or recognizer is None:
            return None
        image = self._decode_image(image_bytes)
        if image is None:
            return None
        faces = self._run_detector(detector, image)
        if faces is None or len(faces) == 0:
            return None
        try:
            import numpy as np

            # Maior rosto (área = w*h).
            faces_arr = np.asarray(faces, dtype=np.float32)
            idx = int(np.argmax(faces_arr[:, 2] * faces_arr[:, 3]))
            aligned = recognizer.alignCrop(image, faces_arr[idx])
            feature = recognizer.feature(aligned)
            return np.asarray(feature).flatten().astype(float).tolist()
        except Exception as exc:
            logger.warning("Falha ao gerar embedding de face (%s)", exc)
            return None

    # ── Helpers ────────────────────────────────────────────────────────────
    def _run_detector(self, detector, image):
        try:
            h, w = image.shape[:2]
            detector.setInputSize((w, h))
            _retval, faces = detector.detect(image)
            return faces if faces is not None else []
        except Exception as exc:
            logger.warning("Detecção de faces falhou (%s)", exc)
            return None

    def _decode_image(self, image_bytes: bytes):
        try:
            import cv2
            import numpy as np
        except Exception:  # pragma: no cover
            cv2 = None
            np = None
        if cv2 is not None and np is not None:
            arr = np.frombuffer(image_bytes, np.uint8)
            return cv2.imdecode(arr, cv2.IMREAD_COLOR)
        try:  # pragma: no cover - fallback sem cv2
            from PIL import Image
            import numpy as np
        except Exception:
            return None
        try:
            pil = Image.open(BytesIO(image_bytes)).convert("RGB")
        except Exception:
            return None
        return np.array(pil)[:, :, ::-1]

    def _upscale_to_min(self, crop):
        min_side = settings.FACE_MIN_CROP_SIDE
        if min_side <= 0 or crop is None or getattr(crop, "size", 0) == 0:
            return crop
        h, w = crop.shape[:2]
        longest = max(h, w)
        if longest <= 0 or longest >= min_side:
            return crop
        import numpy as np  # noqa: F401
        try:
            import cv2
        except Exception:  # pragma: no cover
            cv2 = None
        scale = min_side / float(longest)
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        if cv2 is not None:
            return cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        return crop  # pragma: no cover

    def _encode_jpeg(self, image) -> bytes | None:
        try:
            import cv2
        except Exception:  # pragma: no cover
            cv2 = None
        if cv2 is not None:
            ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, settings.DETECTION_JPEG_QUALITY])
            return buf.tobytes() if ok else None
        try:  # pragma: no cover
            from PIL import Image

            buffer = BytesIO()
            Image.fromarray(image[:, :, ::-1]).save(buffer, format="JPEG", quality=settings.DETECTION_JPEG_QUALITY)
            return buffer.getvalue()
        except Exception:
            return None


face_engine = OpenCVFaceEngine()


# ─── InsightFace (ArcFace) ────────────────────────────────────────────────────

class InsightFaceEngine:
    """ArcFace via InsightFace — local, CPU, gratuito. Muito mais preciso que SFace.

    Usa o pacote `buffalo_sc` (modelos leves ~190 MB) com CPUExecutionProvider.
    Requer `pip install insightface onnxruntime`.
    """

    def __init__(self) -> None:
        self._app = None
        self._lock = threading.Lock()
        self._init_done = False

    def _get_app(self):
        if self._init_done:
            return self._app
        with self._lock:
            if self._init_done:
                return self._app
            try:
                from insightface.app import FaceAnalysis  # lazy import

                app = FaceAnalysis(
                    name="buffalo_sc",
                    providers=["CPUExecutionProvider"],
                )
                app.prepare(ctx_id=0, det_size=(640, 640))
                self._app = app
                logger.info("InsightFace buffalo_sc carregado")
            except Exception as exc:
                logger.warning("InsightFace não disponível (%s) — modo degradado", exc)
                self._app = None
            self._init_done = True
        return self._app

    def warmup(self) -> None:
        self._get_app()

    def _decode_bgr(self, image_bytes: bytes):
        try:
            import cv2
            import numpy as np
        except Exception:
            return None
        arr = np.frombuffer(image_bytes, np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    def detect_and_embed(
        self, image_bytes: bytes
    ) -> Optional[tuple["FaceBox", Optional[list[float]]]]:
        app = self._get_app()
        if app is None:
            return None
        try:
            import cv2
            import numpy as np

            image_bgr = self._decode_bgr(image_bytes)
            if image_bgr is None:
                return None
            h, w = image_bgr.shape[:2]
            # InsightFace espera RGB
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            faces = app.get(image_rgb)
            if not faces:
                return None
            # Maior rosto por área do bbox
            face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
            x1, y1, x2, y2 = (int(v) for v in face.bbox)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            if x2 <= x1 or y2 <= y1:
                return None
            crop = image_bgr[y1:y2, x1:x2]
            ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, settings.DETECTION_JPEG_QUALITY])
            crop_bytes = buf.tobytes() if ok else None
            if not crop_bytes:
                return None
            det_score = float(face.det_score) if hasattr(face, "det_score") else 1.0
            face_box = FaceBox(
                bbox_x=x1, bbox_y=y1, bbox_w=x2 - x1, bbox_h=y2 - y1,
                confidence=round(det_score, 3), crop_bytes=crop_bytes,
            )
            embedding: Optional[list[float]] = None
            if hasattr(face, "normed_embedding") and face.normed_embedding is not None:
                embedding = np.asarray(face.normed_embedding).flatten().tolist()
            return (face_box, embedding)
        except Exception as exc:
            logger.warning("InsightFace detect_and_embed falhou (%s)", exc)
            return None

    def detect(self, image_bytes: bytes) -> list["FaceBox"]:
        app = self._get_app()
        if app is None:
            return []
        try:
            import cv2

            image_bgr = self._decode_bgr(image_bytes)
            if image_bgr is None:
                return []
            h, w = image_bgr.shape[:2]
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            faces = app.get(image_rgb)
            if not faces:
                return []
            results: list[FaceBox] = []
            for face in faces:
                x1, y1, x2, y2 = (int(v) for v in face.bbox)
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                if x2 <= x1 or y2 <= y1:
                    continue
                crop = image_bgr[y1:y2, x1:x2]
                ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, settings.DETECTION_JPEG_QUALITY])
                if not ok:
                    continue
                det_score = float(face.det_score) if hasattr(face, "det_score") else 1.0
                results.append(FaceBox(
                    bbox_x=x1, bbox_y=y1, bbox_w=x2 - x1, bbox_h=y2 - y1,
                    confidence=round(det_score, 3), crop_bytes=buf.tobytes(),
                ))
            results.sort(key=lambda b: b.bbox_w * b.bbox_h, reverse=True)
            return results
        except Exception as exc:
            logger.warning("InsightFace detect falhou (%s)", exc)
            return []

    def embed(self, image_bytes: bytes) -> Optional[list[float]]:
        result = self.detect_and_embed(image_bytes)
        if result is None:
            return None
        _, embedding = result
        return embedding


# ─── DeepFace (ArcFace backend) ───────────────────────────────────────────────

class DeepFaceEngine:
    """ArcFace via DeepFace — local, CPU, gratuito.

    Modelos (~170 MB) baixados na primeira chamada. Requer `pip install deepface`.
    Usa enforce_detection=False para tolerar fotos sem rosto (retorna embedding vazio).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._init_done = False
        self._available = False

    def _ensure_ready(self) -> bool:
        if self._init_done:
            return self._available
        with self._lock:
            if self._init_done:
                return self._available
            try:
                from deepface import DeepFace  # noqa: F401 — only checking availability

                self._available = True
                logger.info("DeepFace disponível")
            except Exception as exc:
                logger.warning("DeepFace não disponível (%s) — modo degradado", exc)
                self._available = False
            self._init_done = True
        return self._available

    def warmup(self) -> None:
        self._ensure_ready()

    def detect_and_embed(
        self, image_bytes: bytes
    ) -> Optional[tuple["FaceBox", Optional[list[float]]]]:
        if not self._ensure_ready():
            return None
        try:
            import cv2
            import numpy as np
            from deepface import DeepFace

            arr = np.frombuffer(image_bytes, np.uint8)
            image_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if image_bgr is None:
                return None
            h, w = image_bgr.shape[:2]

            representations = DeepFace.represent(
                img_path=image_bgr,
                model_name="ArcFace",
                detector_backend="opencv",
                enforce_detection=False,
                align=True,
            )
            if not representations:
                return None
            # Maior rosto por área (facial_area fornecida pelo DeepFace)
            rep = max(
                representations,
                key=lambda r: r.get("facial_area", {}).get("w", 0) * r.get("facial_area", {}).get("h", 0),
            )
            area = rep.get("facial_area", {})
            x, y, fw, fh = area.get("x", 0), area.get("y", 0), area.get("w", w), area.get("h", h)
            x0, y0 = max(0, x), max(0, y)
            x1, y1 = min(w, x + fw), min(h, y + fh)
            if x1 <= x0 or y1 <= y0:
                return None
            crop = image_bgr[y0:y1, x0:x1]
            ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, settings.DETECTION_JPEG_QUALITY])
            crop_bytes = buf.tobytes() if ok else None
            if not crop_bytes:
                return None
            face_box = FaceBox(
                bbox_x=x0, bbox_y=y0, bbox_w=x1 - x0, bbox_h=y1 - y0,
                confidence=round(float(rep.get("face_confidence", 1.0)), 3),
                crop_bytes=crop_bytes,
            )
            raw_emb = rep.get("embedding") or []
            if not raw_emb:
                return None
            emb_arr = np.asarray(raw_emb, dtype=float)
            norm = float(np.linalg.norm(emb_arr))
            embedding = (emb_arr / norm).tolist() if norm > 0 else emb_arr.tolist()
            return (face_box, embedding)
        except Exception as exc:
            logger.warning("DeepFace detect_and_embed falhou (%s)", exc)
            return None

    def detect(self, image_bytes: bytes) -> list["FaceBox"]:
        result = self.detect_and_embed(image_bytes)
        if result is None:
            return []
        face_box, _ = result
        return [face_box]

    def embed(self, image_bytes: bytes) -> Optional[list[float]]:
        result = self.detect_and_embed(image_bytes)
        if result is None:
            return None
        _, embedding = result
        return embedding


# ─── Registro de motores locais ───────────────────────────────────────────────

_insightface_engine = InsightFaceEngine()
_deepface_engine = DeepFaceEngine()

_LOCAL_ENGINES: dict[str, object] = {
    "opencv": face_engine,
    "insightface": _insightface_engine,
    "deepface": _deepface_engine,
}


def get_local_engine(engine_type: str) -> "OpenCVFaceEngine | InsightFaceEngine | DeepFaceEngine":
    """Retorna a instância singleton do motor local correspondente ao tipo."""
    return _LOCAL_ENGINES.get(engine_type, face_engine)  # type: ignore[return-value]
