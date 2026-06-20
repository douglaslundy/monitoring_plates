"""Detecção de objetos com YOLOv8s em ONNX Runtime (CPU, leve, offline).

Substitui a heurística antiga de bordas/contornos por um modelo real de
detecção de objetos. Roda as classes de interesse do COCO (veículos +
pessoas/animais conforme as flags), em uma única passada por frame. O modelo
(`yolov8s.onnx`, configurável pelo build-arg YOLO_MODEL) é embutido na imagem
Docker no build; o caminho vem de VEHICLE_MODEL_PATH.

Importações de `onnxruntime`/`cv2`/`numpy` são preguiçosas para permitir mock
nos testes e para não quebrar caso o modelo não esteja presente (modo
degradado: devolve o frame inteiro como um "veículo" para o OCR ainda tentar).
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

# COCO class id → (categoria, label) usados no sistema.
_COCO_CLASSES: dict[int, tuple[str, str]] = {
    0: ("person", "person"),
    2: ("vehicle", "car"),
    3: ("vehicle", "motorcycle"),
    5: ("vehicle", "bus"),
    7: ("vehicle", "truck"),
    14: ("animal", "bird"),
    15: ("animal", "cat"),
    16: ("animal", "dog"),
    17: ("animal", "horse"),
    18: ("animal", "sheep"),
    19: ("animal", "cow"),
    20: ("animal", "elephant"),
    21: ("animal", "bear"),
    22: ("animal", "zebra"),
    23: ("animal", "giraffe"),
}


def _active_classes() -> dict[int, tuple[str, str]]:
    """Classes COCO ativas conforme as flags (veículos sempre habilitados)."""
    active: dict[int, tuple[str, str]] = {}
    for cid, (category, label) in _COCO_CLASSES.items():
        if category == "vehicle":
            active[cid] = (category, label)
        elif category == "person" and settings.DETECT_PERSONS:
            active[cid] = (category, label)
        elif category == "animal" and settings.DETECT_ANIMALS:
            active[cid] = (category, label)
    return active

_INPUT_SIZE = 640


@dataclass(frozen=True)
class VehicleDetection:
    vehicle_type: str
    category: str
    confidence: float
    bbox_x: int
    bbox_y: int
    bbox_w: int
    bbox_h: int
    crop_bytes: bytes
    # Dimensões do frame analisado (para o gating "objeto inteiro no frame").
    frame_w: int = 0
    frame_h: int = 0


def _model_path() -> str:
    explicit = os.getenv("VEHICLE_MODEL_PATH")
    if explicit:
        return explicit
    return os.path.join(os.getenv("MODELS_DIR", "/app/models"), "yolov8s.onnx")


class VehicleDetector:
    """Detector de objetos baseado em YOLOv8s (ONNX Runtime, CPU)."""

    # Intervalo (s) p/ reler qual modelo o admin selecionou (sem custo por frame).
    _MODEL_CHECK_INTERVAL = 10.0

    def __init__(self) -> None:
        self._session = None
        self._input_name: Optional[str] = None
        self._lock = threading.Lock()
        self._unavailable = False
        self._loaded_model: Optional[str] = None  # modelo atualmente carregado
        self._model_name: Optional[str] = None     # último selecionado lido
        self._model_checked_at = 0.0

    def _selected_model(self) -> Optional[str]:
        """Nome do modelo selecionado pelo admin (cacheado por _MODEL_CHECK_INTERVAL)."""
        import time

        now = time.time()
        if self._model_name is None or now - self._model_checked_at > self._MODEL_CHECK_INTERVAL:
            try:
                from app.services.detector_model_service import get_selected_model

                self._model_name = get_selected_model()
            except Exception:
                pass
            self._model_checked_at = now
        return self._model_name

    def _resolve_path(self, model_name: Optional[str]) -> str:
        if model_name:
            try:
                from app.services.detector_model_service import model_path

                candidate = model_path(model_name)
                if os.path.exists(candidate):
                    return candidate
            except Exception:
                pass
        return _model_path()  # fallback: env/default

    # ── Sessão ONNX ────────────────────────────────────────────────────────
    def _get_session(self):
        desired = self._selected_model()
        # Admin trocou o modelo -> recarrega a sessão ONNX.
        if self._session is not None and desired and desired != self._loaded_model:
            with self._lock:
                logger.info("Detector: modelo alterado %s -> %s, recarregando", self._loaded_model, desired)
                self._session = None
                self._input_name = None
                self._unavailable = False

        if self._session is not None or self._unavailable:
            return self._session
        with self._lock:
            if self._session is not None or self._unavailable:
                return self._session
            try:
                import onnxruntime as ort
            except Exception as exc:  # pragma: no cover - ambiente sem onnxruntime
                logger.warning("onnxruntime indisponível (%s) — detector em modo degradado", exc)
                self._unavailable = True
                return None

            path = self._resolve_path(desired)
            if not os.path.exists(path):
                logger.warning("Modelo de veículos não encontrado em %s — modo degradado", path)
                self._unavailable = True
                return None

            try:
                providers = ["CPUExecutionProvider"]
                sess_options = ort.SessionOptions()
                sess_options.intra_op_num_threads = max(1, settings.VEHICLE_DETECTOR_THREADS)
                self._session = ort.InferenceSession(path, sess_options=sess_options, providers=providers)
                self._input_name = self._session.get_inputs()[0].name
                self._loaded_model = desired
                logger.info("Detector YOLO carregado de %s", path)
            except Exception as exc:
                logger.error("Falha ao carregar modelo de veículos (%s) — modo degradado", exc)
                self._unavailable = True
                self._session = None
            return self._session

    def warmup(self) -> None:
        self._get_session()

    # ── API pública ────────────────────────────────────────────────────────
    def best_detection(self, image_bytes: bytes) -> Optional[VehicleDetection]:
        detections = self.detect(image_bytes)
        return detections[0] if detections else None

    def detect(self, image_bytes: bytes) -> list[VehicleDetection]:
        image = self._decode_image(image_bytes)
        if image is None:
            return []

        session = self._get_session()
        if session is None:
            return self._fallback_detection(image)

        try:
            import numpy as np
        except Exception:  # pragma: no cover
            return self._fallback_detection(image)

        h, w = image.shape[:2]
        tensor, ratio, pad = self._preprocess(image)
        try:
            outputs = session.run(None, {self._input_name: tensor})
        except Exception as exc:
            logger.warning("Inferência do detector falhou (%s) — modo degradado", exc)
            return self._fallback_detection(image)

        boxes = self._postprocess(outputs[0], ratio, pad, w, h)
        detections: list[VehicleDetection] = []
        active = _active_classes()
        for (x1, y1, x2, y2, score, cls_id) in boxes:
            mapped = active.get(int(cls_id))
            if mapped is None:
                continue
            category, label = mapped
            crop = self._crop_with_padding(image, x1, y1, x2, y2, w, h)
            crop_bytes = self._encode_jpeg(crop)
            if not crop_bytes:
                continue
            detections.append(
                VehicleDetection(
                    vehicle_type=label,
                    category=category,
                    confidence=round(float(score), 3),
                    bbox_x=int(x1),
                    bbox_y=int(y1),
                    bbox_w=int(x2 - x1),
                    bbox_h=int(y2 - y1),
                    crop_bytes=crop_bytes,
                    frame_w=int(w),
                    frame_h=int(h),
                )
            )

        detections.sort(key=lambda d: self._score(d, w, h), reverse=True)
        # Cap mais alto que 3: em cenas reais (vários veículos + pessoa + animal)
        # o limite antigo, somado ao _score que privilegia objetos grandes/centrais,
        # descartava objetos pequenos (um cachorro) mesmo detectados. Cada objeto
        # vira um track contado uma vez — manter mais detecções é barato.
        return detections[: max(1, settings.MAX_DETECTIONS_PER_FRAME)]

    # ── Pré/pós-processamento ──────────────────────────────────────────────
    def _preprocess(self, image):
        """Letterbox para 640x640, BGR→RGB, NCHW float32 normalizado."""
        import numpy as np

        try:
            import cv2
        except Exception:  # pragma: no cover
            cv2 = None

        h, w = image.shape[:2]
        ratio = min(_INPUT_SIZE / h, _INPUT_SIZE / w)
        new_w, new_h = int(round(w * ratio)), int(round(h * ratio))
        pad_x = (_INPUT_SIZE - new_w) / 2
        pad_y = (_INPUT_SIZE - new_h) / 2

        if cv2 is not None:
            resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            canvas = np.full((_INPUT_SIZE, _INPUT_SIZE, 3), 114, dtype=np.uint8)
            top, left = int(round(pad_y - 0.1)), int(round(pad_x - 0.1))
            canvas[top : top + new_h, left : left + new_w] = resized
            rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        else:  # pragma: no cover - fallback sem cv2
            from PIL import Image

            pil = Image.fromarray(image[:, :, ::-1]).resize((new_w, new_h))
            canvas = np.full((_INPUT_SIZE, _INPUT_SIZE, 3), 114, dtype=np.uint8)
            top, left = int(round(pad_y - 0.1)), int(round(pad_x - 0.1))
            canvas[top : top + new_h, left : left + new_w] = np.array(pil)
            rgb = canvas

        tensor = rgb.astype(np.float32) / 255.0
        tensor = tensor.transpose(2, 0, 1)[np.newaxis, ...]
        return np.ascontiguousarray(tensor), ratio, (pad_x, pad_y)

    def _postprocess(self, output, ratio, pad, orig_w, orig_h):
        """YOLOv8 output [1,84,8400] → caixas [x1,y1,x2,y2,score,cls] no frame original."""
        import numpy as np

        preds = np.asarray(output)
        if preds.ndim == 3:
            preds = preds[0]
        # [84, N] → [N, 84]
        if preds.shape[0] < preds.shape[1]:
            preds = preds.transpose(1, 0)

        boxes_xywh = preds[:, :4]
        class_scores = preds[:, 4:]
        class_ids = np.argmax(class_scores, axis=1)
        confidences = class_scores[np.arange(class_scores.shape[0]), class_ids]

        active = _active_classes()
        cat_thr = {
            "vehicle": settings.VEHICLE_CONF_THRESHOLD,
            "person": settings.PERSON_CONF_THRESHOLD,
            "animal": settings.ANIMAL_CONF_THRESHOLD,
        }
        # Threshold por detecção conforme a categoria da classe; classes inativas
        # recebem 1.1 (sempre descartadas).
        thr_vec = np.array(
            [cat_thr.get(active[int(c)][0], 1.1) if int(c) in active else 1.1 for c in class_ids],
            dtype=np.float32,
        )
        keep = confidences >= thr_vec
        if not np.any(keep):
            return []

        boxes_xywh = boxes_xywh[keep]
        confidences = confidences[keep]
        class_ids = class_ids[keep]

        pad_x, pad_y = pad
        cx, cy, bw, bh = boxes_xywh[:, 0], boxes_xywh[:, 1], boxes_xywh[:, 2], boxes_xywh[:, 3]
        x1 = (cx - bw / 2 - pad_x) / ratio
        y1 = (cy - bh / 2 - pad_y) / ratio
        x2 = (cx + bw / 2 - pad_x) / ratio
        y2 = (cy + bh / 2 - pad_y) / ratio

        x1 = np.clip(x1, 0, orig_w)
        y1 = np.clip(y1, 0, orig_h)
        x2 = np.clip(x2, 0, orig_w)
        y2 = np.clip(y2, 0, orig_h)

        xyxy = np.stack([x1, y1, x2, y2], axis=1)
        # NMS class-aware: objetos de classes diferentes (ex.: uma pessoa e o
        # cachorro ao seu lado) podem se sobrepor sem que um deva suprimir o
        # outro. Deslocamos as caixas por um offset proporcional à classe antes
        # do NMS, de modo que só caixas da MESMA classe competem entre si. Sem
        # isto, o cachorro (menor confiança) sumia quando encostava na pessoa.
        max_coord = float(max(orig_w, orig_h)) + 1.0
        offset = class_ids.astype(np.float32)[:, None] * max_coord
        keep_idx = self._nms(xyxy + offset, confidences, settings.VEHICLE_IOU_THRESHOLD)

        results = []
        for i in keep_idx:
            results.append(
                (
                    float(xyxy[i, 0]),
                    float(xyxy[i, 1]),
                    float(xyxy[i, 2]),
                    float(xyxy[i, 3]),
                    float(confidences[i]),
                    int(class_ids[i]),
                )
            )
        return results

    @staticmethod
    def _nms(boxes, scores, iou_threshold: float) -> list[int]:
        import numpy as np

        if len(boxes) == 0:
            return []
        x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
        areas = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
        order = scores.argsort()[::-1]

        keep: list[int] = []
        while order.size > 0:
            i = int(order[0])
            keep.append(i)
            if order.size == 1:
                break
            rest = order[1:]
            xx1 = np.maximum(x1[i], x1[rest])
            yy1 = np.maximum(y1[i], y1[rest])
            xx2 = np.minimum(x2[i], x2[rest])
            yy2 = np.minimum(y2[i], y2[rest])
            inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
            union = areas[i] + areas[rest] - inter
            iou = np.where(union > 0, inter / union, 0.0)
            order = rest[iou <= iou_threshold]
        return keep

    # ── Imagem ─────────────────────────────────────────────────────────────
    def _decode_image(self, image_bytes: bytes):
        try:
            import cv2
            import numpy as np
        except Exception:  # pragma: no cover
            cv2 = None
            np = None

        if cv2 is not None and np is not None:
            arr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            return image

        try:
            from PIL import Image
            import numpy as np
        except Exception:  # pragma: no cover
            return None
        try:
            pil = Image.open(BytesIO(image_bytes)).convert("RGB")
        except Exception:
            return None
        return np.array(pil)[:, :, ::-1]  # RGB→BGR

    def _crop_with_padding(self, image, x1, y1, x2, y2, max_w, max_h):
        pad_x = max(8, int((x2 - x1) * 0.08))
        pad_y = max(8, int((y2 - y1) * 0.12))
        cx1 = max(0, int(x1) - pad_x)
        cy1 = max(0, int(y1) - pad_y)
        cx2 = min(max_w, int(x2) + pad_x)
        cy2 = min(max_h, int(y2) + pad_y)
        return self._upscale_to_min(image[cy1:cy2, cx1:cx2])

    def _upscale_to_min(self, crop):
        """Amplia (cúbico) recortes pequenos para a imagem salva ficar legível.

        Não recupera detalhe que a câmera não capturou — só evita que recortes de
        veículos distantes fiquem minúsculos/serrilhados ao serem exibidos.
        """
        min_side = settings.DETECTION_MIN_CROP_SIDE
        if min_side <= 0 or crop is None or getattr(crop, "size", 0) == 0:
            return crop
        h, w = crop.shape[:2]
        longest = max(h, w)
        if longest <= 0 or longest >= min_side:
            return crop
        import numpy as np
        try:
            import cv2
        except Exception:  # pragma: no cover
            cv2 = None
        scale = min_side / float(longest)
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        if cv2 is not None:
            return cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        try:  # pragma: no cover - fallback sem OpenCV
            from PIL import Image

            pil = Image.fromarray(crop[:, :, ::-1]).resize((new_w, new_h), resample=Image.Resampling.BICUBIC)
            return np.array(pil)[:, :, ::-1]
        except Exception:
            return crop

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

    def _score(self, detection: VehicleDetection, frame_w: int, frame_h: int) -> float:
        """Prioriza detecções confiáveis, centrais e de bom tamanho."""
        area_ratio = (detection.bbox_w * detection.bbox_h) / max(frame_w * frame_h, 1)
        center_x = (detection.bbox_x + detection.bbox_w / 2) / max(frame_w, 1)
        center_y = (detection.bbox_y + detection.bbox_h / 2) / max(frame_h, 1)
        center_bonus = 1.0 - min(1.0, abs(center_x - 0.5) + abs(center_y - 0.6))
        size_bonus = min(1.0, area_ratio / 0.15)
        return (detection.confidence * 0.6) + (center_bonus * 0.2) + (size_bonus * 0.2)

    def _fallback_detection(self, image) -> list[VehicleDetection]:
        """Modo degradado (sem modelo): devolve o frame inteiro p/ o OCR tentar."""
        h, w = image.shape[:2]
        crop_bytes = self._encode_jpeg(image)
        if not crop_bytes:
            return []
        return [
            VehicleDetection(
                vehicle_type="unknown",
                category="vehicle",
                confidence=0.5,
                bbox_x=0,
                bbox_y=0,
                bbox_w=int(w),
                bbox_h=int(h),
                crop_bytes=crop_bytes,
            )
        ]


vehicle_detector = VehicleDetector()
