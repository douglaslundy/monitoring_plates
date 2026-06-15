from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from time import time
from typing import Any
from uuid import uuid4

from app.core.config import settings

WINDOW_SECONDS = 60
STALE_SECONDS = 12
DEGRADED_SECONDS = 4


@dataclass(slots=True)
class PreviewTelemetry:
    preview_fps: float
    preview_frames_last_minute: int
    preview_last_frame_at: float | None
    preview_latency_seconds: float | None
    preview_status: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "preview_fps": self.preview_fps,
            "preview_frames_last_minute": self.preview_frames_last_minute,
            "preview_last_frame_at": self.preview_last_frame_at,
            "preview_latency_seconds": self.preview_latency_seconds,
            "preview_status": self.preview_status,
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


def _frames_key(camera_id: str) -> str:
    return f"camera-telemetry:{camera_id}:preview-frames"


def record_preview_frame(camera_id: str) -> None:
    client = _redis_client()
    if client is None:
        return

    now = time()
    key = _frames_key(camera_id)
    member = f"{now:.6f}:{uuid4().hex}"

    try:
        pipeline = client.pipeline()
        pipeline.zadd(key, {member: now})
        pipeline.zremrangebyscore(key, 0, now - WINDOW_SECONDS)
        pipeline.expire(key, WINDOW_SECONDS + 30)
        pipeline.execute()
    except Exception:
        return


def get_preview_telemetry(camera_id: str, is_online: bool) -> PreviewTelemetry:
    client = _redis_client()
    if client is None:
        return PreviewTelemetry(
            preview_fps=0.0,
            preview_frames_last_minute=0,
            preview_last_frame_at=None,
            preview_latency_seconds=None,
            preview_status="offline" if not is_online else "idle",
        )

    key = _frames_key(camera_id)
    now = time()

    try:
        pipeline = client.pipeline()
        pipeline.zremrangebyscore(key, 0, now - WINDOW_SECONDS)
        pipeline.zcard(key)
        pipeline.zrevrange(key, 0, 0, withscores=True)
        _, frames_last_minute, last_frame = pipeline.execute()
    except Exception:
        return PreviewTelemetry(
            preview_fps=0.0,
            preview_frames_last_minute=0,
            preview_last_frame_at=None,
            preview_latency_seconds=None,
            preview_status="offline" if not is_online else "idle",
        )

    last_frame_at: float | None = None
    if last_frame:
        try:
            _, score = last_frame[0]
            last_frame_at = float(score)
        except Exception:
            last_frame_at = None

    preview_latency_seconds: float | None = None
    if last_frame_at is not None:
        preview_latency_seconds = max(0.0, now - last_frame_at)

    if frames_last_minute <= 0:
        preview_status = "idle" if is_online else "offline"
    elif preview_latency_seconds is not None and preview_latency_seconds <= DEGRADED_SECONDS:
        preview_status = "streaming"
    elif preview_latency_seconds is not None and preview_latency_seconds <= STALE_SECONDS:
        preview_status = "degraded"
    else:
        preview_status = "stale"

    preview_fps = round(float(frames_last_minute) / WINDOW_SECONDS, 2)
    return PreviewTelemetry(
        preview_fps=preview_fps,
        preview_frames_last_minute=int(frames_last_minute),
        preview_last_frame_at=last_frame_at,
        preview_latency_seconds=preview_latency_seconds,
        preview_status=preview_status,
    )
