from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from statistics import mean, pstdev
from time import time
from typing import Any

from app.core.config import settings

QUALITY_STALE_SECONDS = 30


@dataclass(slots=True)
class ImageQuality:
    quality_score: float
    quality_label: str
    blur_score: float
    brightness: float
    contrast: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "quality_score": self.quality_score,
            "quality_label": self.quality_label,
            "blur_score": self.blur_score,
            "brightness": self.brightness,
            "contrast": self.contrast,
        }


@lru_cache(maxsize=1)
def _redis_client() -> Any | None:
    try:
        import redis
    except Exception:
        return None

    try:
        return redis.from_url(settings.REDIS_URL, decode_responses=True)
    except Exception:
        return None


def _quality_key(camera_id: str) -> str:
    return f"camera-telemetry:{camera_id}:quality"


def analyze_image_quality(image_bytes: bytes) -> ImageQuality:
    try:
        from PIL import Image
    except ImportError:
        return ImageQuality(
            quality_score=0.0,
            quality_label="unknown",
            blur_score=0.0,
            brightness=0.0,
            contrast=0.0,
        )

    try:
        image = Image.open(BytesIO(image_bytes)).convert("L")
    except Exception:
        return ImageQuality(
            quality_score=0.0,
            quality_label="unknown",
            blur_score=0.0,
            brightness=0.0,
            contrast=0.0,
        )

    image = image.resize((64, 64))
    pixels = list(image.tobytes())
    brightness = round(mean(pixels) / 255.0 * 100.0, 2) if pixels else 0.0
    contrast = round((pstdev(pixels) / 255.0 * 100.0) if len(pixels) > 1 else 0.0, 2)
    blur_score = round(_laplacian_variance(pixels, 64, 64), 2)
    quality_score = round(_combine_quality_score(blur_score, brightness, contrast), 2)
    quality_label = _label_for_score(quality_score)
    return ImageQuality(
        quality_score=quality_score,
        quality_label=quality_label,
        blur_score=blur_score,
        brightness=brightness,
        contrast=contrast,
    )


def record_image_quality(camera_id: str, image_bytes: bytes) -> ImageQuality:
    quality = analyze_image_quality(image_bytes)
    client = _redis_client()
    if client is None:
        return quality

    try:
        payload = {
            "quality_score": quality.quality_score,
            "quality_label": quality.quality_label,
            "blur_score": quality.blur_score,
            "brightness": quality.brightness,
            "contrast": quality.contrast,
            "updated_at": time(),
        }
        client.set(_quality_key(camera_id), json.dumps(payload), ex=QUALITY_STALE_SECONDS)
    except Exception:
        pass
    return quality


def get_image_quality(camera_id: str) -> ImageQuality:
    client = _redis_client()
    if client is None:
        return ImageQuality(0.0, "unknown", 0.0, 0.0, 0.0)

    try:
        raw = client.get(_quality_key(camera_id))
    except Exception:
        raw = None

    if not raw:
        return ImageQuality(0.0, "unknown", 0.0, 0.0, 0.0)

    try:
        data = json.loads(raw)
    except Exception:
        return ImageQuality(0.0, "unknown", 0.0, 0.0, 0.0)

    return ImageQuality(
        quality_score=float(data.get("quality_score", 0.0)),
        quality_label=str(data.get("quality_label", "unknown")),
        blur_score=float(data.get("blur_score", 0.0)),
        brightness=float(data.get("brightness", 0.0)),
        contrast=float(data.get("contrast", 0.0)),
    )


def _laplacian_variance(pixels: list[int], width: int, height: int) -> float:
    if width < 3 or height < 3 or len(pixels) != width * height:
        return 0.0

    values: list[float] = []
    for y in range(1, height - 1):
        row = y * width
        for x in range(1, width - 1):
            idx = row + x
            center = pixels[idx]
            lap = (
                4 * center
                - pixels[idx - 1]
                - pixels[idx + 1]
                - pixels[idx - width]
                - pixels[idx + width]
            )
            values.append(float(lap))

    if len(values) < 2:
        return 0.0

    avg = mean(values)
    return round(sum((value - avg) ** 2 for value in values) / len(values), 2)


def _combine_quality_score(blur_score: float, brightness: float, contrast: float) -> float:
    blur_component = min(100.0, blur_score / 4.0)
    brightness_component = max(0.0, 100.0 - abs(brightness - 55.0) * 2.0)
    contrast_component = min(100.0, contrast * 2.5)
    score = (blur_component * 0.45) + (brightness_component * 0.25) + (contrast_component * 0.30)
    return max(0.0, min(100.0, score))


def _label_for_score(score: float) -> str:
    if score >= 75:
        return "excellent"
    if score >= 55:
        return "good"
    if score >= 35:
        return "fair"
    return "poor"
