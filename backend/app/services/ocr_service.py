"""Reconhecimento de placas (OCR) híbrido.

Motor local padrão: **fast-alpr** (detecção de placa + OCR em ONNX Runtime, CPU,
single-pass, ~dezenas de ms). Substitui o EasyOCR força-bruta que rodava ~18
recortes por frame (83s/frame).

Motor opcional por plano/câmera: **PlateRecognizer** (nuvem, paga, alta
precisão, devolve marca/cor/modelo). O `OcrRouter` resolve qual usar e cacheia a
resolução para não abrir sessão de banco a cada frame.

Importações de `fast_alpr`/`cv2` são preguiçosas para permitir mock nos testes.
"""
import os
import re
import logging
import threading
import time
from io import BytesIO
from typing import Optional, Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)

_PLATE_RE = re.compile(r"^[A-Z]{3}\d{4}$|^[A-Z]{3}\d[A-Z]\d{2}$")

# TTL (s) do cache de resolução de motor por câmera — evita hit de DB por frame.
_ENGINE_CACHE_TTL = 60.0


# ─── Interface comum ──────────────────────────────────────────────────────────

class OcrEngine(Protocol):
    def recognize(self, image_bytes: bytes) -> Optional[dict]:
        ...


# ─── Motor local: fast-alpr (ONNX) ─────────────────────────────────────────────

class FastAlprEngine:
    """Detecção de placa + OCR via fast-alpr (ONNX Runtime, CPU)."""

    def __init__(self) -> None:
        self._alpr = None
        self._lock = threading.Lock()
        self._unavailable = False

    def _get_alpr(self):
        if self._alpr is not None or self._unavailable:
            return self._alpr
        with self._lock:
            if self._alpr is not None or self._unavailable:
                return self._alpr
            try:
                from fast_alpr import ALPR
            except Exception as exc:  # pragma: no cover - ambiente sem fast_alpr
                logger.warning("fast-alpr indisponível (%s) — OCR local desligado", exc)
                self._unavailable = True
                return None

            # Tenta, em ordem: modelos do ambiente → defaults da lib → pares
            # conhecidos. Robusto a diferenças de versão do fast-alpr.
            candidates: list[dict] = []
            detector = os.getenv("FAST_ALPR_DETECTOR_MODEL")
            ocr = os.getenv("FAST_ALPR_OCR_MODEL")
            if detector or ocr:
                env_kwargs: dict = {}
                if detector:
                    env_kwargs["detector_model"] = detector
                if ocr:
                    env_kwargs["ocr_model"] = ocr
                candidates.append(env_kwargs)
            candidates.append({})  # defaults da versão instalada
            candidates.append({
                "detector_model": "yolo-v9-t-384-license-plate-end2end",
                "ocr_model": "global-plates-mobile-vit-v2-model",
            })
            candidates.append({
                "detector_model": "yolo-v9-t-384-license-plate-end2end",
                "ocr_model": "cct-xs-v1-global-model",
            })

            last_exc: Exception | None = None
            for cand in candidates:
                try:
                    self._alpr = ALPR(**cand)
                    logger.info("fast-alpr carregado (%s)", cand or "defaults")
                    return self._alpr
                except Exception as exc:
                    last_exc = exc
                    continue

            logger.error("Falha ao iniciar fast-alpr (%s) — OCR local desligado", last_exc)
            self._unavailable = True
            self._alpr = None
            return self._alpr

    def warmup(self) -> None:
        self._get_alpr()

    def recognize(self, image_bytes: bytes) -> Optional[dict]:
        alpr = self._get_alpr()
        if alpr is None:
            return None

        image = self._decode_image(image_bytes)
        if image is None:
            return None

        t0 = time.time()
        try:
            results = alpr.predict(image)
        except Exception as exc:
            logger.warning("fast-alpr predict falhou: %s", exc)
            return None

        min_conf = self._min_confidence()
        best_plate: Optional[str] = None
        best_conf = 0.0
        for result in results or []:
            text, conf = self._extract(result)
            if not text:
                continue
            normalized = re.sub(r"[^A-Z0-9]", "", text.upper())
            if _PLATE_RE.match(normalized) and conf >= min_conf and conf > best_conf:
                best_plate = normalized
                best_conf = conf

        if best_plate is None:
            return None

        logger.info("fast-alpr: plate=%s conf=%.2f time=%.3fs", best_plate, best_conf, time.time() - t0)
        return {"plate": best_plate, "confidence": float(best_conf), "engine": "fast_alpr"}

    @staticmethod
    def _min_confidence() -> float:
        return min(settings.AGENT_MIN_CONFIDENCE, 0.5)

    @staticmethod
    def _extract(result) -> tuple[Optional[str], float]:
        """Extrai (texto, confiança) de um resultado do fast-alpr de forma robusta."""
        ocr = None
        if isinstance(result, dict):
            ocr = result.get("ocr")
        else:
            ocr = getattr(result, "ocr", None)
        if ocr is None:
            return None, 0.0
        if isinstance(ocr, dict):
            text = ocr.get("text")
            conf = ocr.get("confidence", 0.0)
        else:
            text = getattr(ocr, "text", None)
            conf = getattr(ocr, "confidence", 0.0)
        try:
            conf = float(conf or 0.0)
        except (TypeError, ValueError):
            conf = 0.0
        return text, conf

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

        try:
            from PIL import Image
            import numpy as np
        except Exception:  # pragma: no cover
            return None
        try:
            pil = Image.open(BytesIO(image_bytes)).convert("RGB")
        except Exception:
            return None
        return np.array(pil)[:, :, ::-1]  # RGB→BGR (formato cv2/fast-alpr)


# Aliases de compatibilidade — código/testes antigos importam estes nomes.
EasyOcrEngine = FastAlprEngine
PlateRecognizer = FastAlprEngine


def warm_ocr_models() -> None:
    _local_engine.warmup()


# ─── Motor de nuvem: Plate Recognizer ──────────────────────────────────────────

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
    """Resolve qual motor OCR usar com base no plano do cliente da câmera.

    A resolução é cacheada por `_ENGINE_CACHE_TTL` segundos para não abrir sessão
    de banco a cada frame processado.
    """

    def __init__(self) -> None:
        self._cache: dict[str, tuple[OcrEngine, float]] = {}
        self._cache_lock = threading.Lock()

    def recognize(self, image_bytes: bytes, camera_id: Optional[str] = None) -> Optional[dict]:
        engine = self._resolve_engine(camera_id)
        try:
            result = engine.recognize(image_bytes)
        except Exception as e:
            logger.error("OCR engine failed (%s): %s — fallback para motor local", type(engine).__name__, e)
            result = None

        # Fallback para o motor local se o motor principal falhar.
        if result is None and not isinstance(engine, FastAlprEngine):
            logger.info("Fallback para fast-alpr local")
            result = _local_engine.recognize(image_bytes)

        return result

    def _resolve_engine(self, camera_id: Optional[str]) -> OcrEngine:
        cache_key = camera_id or "__system__"
        now = time.time()
        with self._cache_lock:
            cached = self._cache.get(cache_key)
            if cached and cached[1] > now:
                return cached[0]

        engine = self._build_engine(camera_id)
        with self._cache_lock:
            self._cache[cache_key] = (engine, now + _ENGINE_CACHE_TTL)
        return engine

    def _build_engine(self, camera_id: Optional[str]) -> OcrEngine:
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

        return _local_engine

    def _get_active_engine(self, preferred: str) -> OcrEngine:
        if preferred == "system_default" or preferred is None:
            preferred = self._get_system_default()

        if preferred == "plate_recognizer":
            engine = self._build_plate_recognizer()
            if engine:
                return engine

        return _local_engine

    def _get_system_default(self) -> str:
        try:
            from app.core.database import SessionLocal
            from app.models.ocr_engine_config import OcrEngineConfig

            db = SessionLocal()
            try:
                cfg = (
                    db.query(OcrEngineConfig)
                    .filter(OcrEngineConfig.is_active == True)  # noqa: E712
                    .order_by(OcrEngineConfig.updated_at.desc())
                    .first()
                )
                if cfg:
                    return cfg.engine_type
            finally:
                db.close()
        except Exception as e:
            logger.warning("Could not fetch system default OCR engine: %s", e)

        return "fast_alpr"

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
                        OcrEngineConfig.is_active == True,  # noqa: E712
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

_local_engine = FastAlprEngine()
_easyocr_engine = _local_engine  # alias de compatibilidade
recognizer = OcrRouter()
