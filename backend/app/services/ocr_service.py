import re
import logging
import time
from io import BytesIO
from typing import Optional, Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)

_PLATE_RE = re.compile(r"^[A-Z]{3}\d{4}$|^[A-Z]{3}\d[A-Z]\d{2}$")


# ─── Interface comum ──────────────────────────────────────────────────────────

class OcrEngine(Protocol):
    def recognize(self, image_bytes: bytes) -> Optional[dict]:
        ...


# ─── EasyOCR ──────────────────────────────────────────────────────────────────

class EasyOcrEngine:
    def __init__(self) -> None:
        self._reader = None

    def _get_reader(self):
        if self._reader is None:
            import easyocr
            self._reader = easyocr.Reader(["pt", "en"], gpu=False)
        return self._reader

    def recognize(self, image_bytes: bytes) -> Optional[dict]:
        import numpy as np

        t0 = time.time()
        image = self._decode_image(image_bytes)
        if image is None:
            return None

        reader = self._get_reader()
        candidates = []
        roi = self._find_plate_roi(image)
        if roi is not None:
            candidates.append(roi)
        candidates.append(image)
        shape = getattr(image, "shape", None)
        if shape and len(shape) >= 2 and min(shape[:2]) < 900:
            candidates.append(np.repeat(np.repeat(image, 2, axis=0), 2, axis=1))

        for candidate in candidates:
            result = self._extract_plate(reader.readtext(candidate), t0)
            if result is not None:
                return result

        return None

    def _extract_plate(self, results, started_at: float) -> Optional[dict]:
        for _, text, confidence in results:
            normalized = re.sub(r"[^A-Z0-9]", "", text.upper())
            if _PLATE_RE.match(normalized) and confidence >= settings.AGENT_MIN_CONFIDENCE:
                elapsed = time.time() - started_at
                logger.info("EasyOCR: plate=%s conf=%.2f time=%.2fs", normalized, confidence, elapsed)
                return {
                    "plate": normalized,
                    "confidence": float(confidence),
                    "engine": "easyocr",
                }
        return None

    def _decode_image(self, image_bytes: bytes):
        import numpy as np
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps

        try:
            import cv2
        except ImportError:
            cv2 = None

        if cv2 is not None:
            arr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                return None

            h, w = img.shape[:2]
            if w > 1280:
                scale = 1280 / w
                img = cv2.resize(img, (1280, int(h * scale)))

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            return enhanced

        try:
            image = Image.open(BytesIO(image_bytes)).convert("L")
        except Exception:
            return None

        if image.width > 1280:
            scale = 1280 / image.width
            image = image.resize((1280, int(image.height * scale)))

        image = ImageOps.autocontrast(image)
        image = ImageEnhance.Sharpness(image).enhance(1.6)
        image = image.filter(ImageFilter.SHARPEN)
        return np.array(image)

    def _find_plate_roi(self, gray):
        try:
            import cv2
        except ImportError:
            return gray

        blurred = cv2.bilateralFilter(gray, 11, 17, 17)
        edges = cv2.Canny(blurred, 30, 200)
        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:30]

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if h == 0:
                continue
            ratio = w / h
            if 3.0 <= ratio <= 5.0 and w > 80:
                return gray[y: y + h, x: x + w]

        return gray


class PlateRecognizer(EasyOcrEngine):
    """Backward-compatible alias kept for tests and older imports."""

    pass


# ─── Plate Recognizer ─────────────────────────────────────────────────────────

class PlateRecognizerEngine:
    def __init__(self, api_token: str, api_url: str, regions: list, enable_mmc: bool) -> None:
        self.api_token = api_token
        self.api_url = api_url.rstrip("/") + "/"
        self.regions = regions or ["br"]
        self.enable_mmc = enable_mmc

    def recognize(self, image_bytes: bytes) -> Optional[dict]:
        import requests as req

        t0 = time.time()
        try:
            payload: dict = {"regions": self.regions}
            if self.enable_mmc:
                payload["mmc"] = True

            response = req.post(
                self.api_url,
                headers={"Authorization": f"Token {self.api_token}"},
                files={"upload": ("frame.jpg", image_bytes, "image/jpeg")},
                data=payload,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.warning("PlateRecognizer request failed: %s", e)
            return None

        results = data.get("results", [])
        if not results:
            return None

        best = results[0]
        plate_raw = re.sub(r"[^A-Z0-9]", "", best.get("plate", "").upper())

        if not _PLATE_RE.match(plate_raw):
            logger.debug("PlateRecognizer: invalid plate format %s", plate_raw)
            return None

        elapsed = time.time() - t0
        logger.info("PlateRecognizer: plate=%s conf=%.2f time=%.2fs", plate_raw, best.get("confidence", 0), elapsed)

        vehicle = best.get("vehicle", {})
        region = best.get("region", {})

        result: dict = {
            "plate": plate_raw,
            "confidence": float(best.get("confidence", 0)),
            "engine": "plate_recognizer",
            "vehicle_type": vehicle.get("type"),
            "vehicle_color": vehicle.get("color"),
            "vehicle_make_model": vehicle.get("make_model") if self.enable_mmc else None,
            "region_code": region.get("code"),
            "candidates": [
                {"plate": re.sub(r"[^A-Z0-9]", "", c.get("plate", "").upper()), "confidence": c.get("confidence")}
                for c in best.get("candidates", [])
            ],
        }
        return result


# ─── Router ───────────────────────────────────────────────────────────────────

class OcrRouter:
    """Resolve qual motor OCR usar com base no plano do cliente da câmera."""

    def recognize(self, image_bytes: bytes, camera_id: Optional[str] = None) -> Optional[dict]:
        engine = self._resolve_engine(camera_id)
        try:
            result = engine.recognize(image_bytes)
        except Exception as e:
            logger.error("OCR engine failed (%s): %s — falling back to EasyOCR", type(engine).__name__, e)
            result = None

        # Fallback para EasyOCR se o motor principal falhar
        if result is None and not isinstance(engine, EasyOcrEngine):
            logger.info("Falling back to EasyOCR")
            result = _easyocr_engine.recognize(image_bytes)

        return result

    def _resolve_engine(self, camera_id: Optional[str]) -> OcrEngine:
        if camera_id is None:
            return self._get_active_engine("system_default")

        try:
            from app.core.database import SessionLocal
            from app.models.camera import Camera
            import uuid

            db = SessionLocal()
            try:
                camera = db.query(Camera).filter(Camera.id == uuid.UUID(camera_id)).first()
                if camera and camera.client and camera.client.plan:
                    plan_engine = camera.client.plan.ocr_engine
                    return self._get_active_engine(plan_engine)
            finally:
                db.close()
        except Exception as e:
            logger.warning("Could not resolve OCR engine for camera %s: %s", camera_id, e)

        return _easyocr_engine

    def _get_active_engine(self, preferred: str) -> OcrEngine:
        if preferred == "system_default" or preferred is None:
            preferred = self._get_system_default()

        if preferred == "plate_recognizer":
            engine = self._build_plate_recognizer()
            if engine:
                return engine

        return _easyocr_engine

    def _get_system_default(self) -> str:
        try:
            from app.core.database import SessionLocal
            from app.models.ocr_engine_config import OcrEngineConfig, OcrEngineType

            db = SessionLocal()
            try:
                cfg = (
                    db.query(OcrEngineConfig)
                    .filter(OcrEngineConfig.is_active == True)
                    .order_by(OcrEngineConfig.updated_at.desc())
                    .first()
                )
                if cfg:
                    return cfg.engine_type
            finally:
                db.close()
        except Exception as e:
            logger.warning("Could not fetch system default OCR engine: %s", e)

        return "easyocr"

    def _build_plate_recognizer(self) -> Optional[PlateRecognizerEngine]:
        try:
            from app.core.database import SessionLocal
            from app.models.ocr_engine_config import OcrEngineConfig, OcrEngineType

            db = SessionLocal()
            try:
                cfg = (
                    db.query(OcrEngineConfig)
                    .filter(
                        OcrEngineConfig.engine_type == OcrEngineType.plate_recognizer,
                        OcrEngineConfig.is_active == True,
                    )
                    .first()
                )
                if cfg and cfg.api_token and cfg.api_url:
                    return PlateRecognizerEngine(
                        api_token=cfg.api_token,
                        api_url=cfg.api_url,
                        regions=cfg.regions or ["br"],
                        enable_mmc=cfg.enable_mmc,
                    )
            finally:
                db.close()
        except Exception as e:
            logger.warning("Could not build PlateRecognizer engine: %s", e)

        return None


# ─── Instâncias globais ────────────────────────────────────────────────────────

_easyocr_engine = EasyOcrEngine()
recognizer = OcrRouter()
