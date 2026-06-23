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
        if not faces or len(faces) == 0:
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
