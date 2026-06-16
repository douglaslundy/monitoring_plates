"""Rastreador multi-objeto por câmera (IoU + tempo), com contagem única.

Substitui o dedup de slot-único. Cada objeto vira um *track*; um track só é
contado **uma vez** (quando confirma `TRACK_MIN_HITS` frames). Enquanto o objeto
permanece no frame — inclusive **parado** — o IoU mantém o mesmo track, então não
há recontagem. Se o objeto sai (track expira por `TRACK_MAX_AGE_SECONDS`) e volta,
um novo track é criado e ele conta de novo.

`update_tracks` é pura (testável sem Redis). `track_camera` adiciona persistência
do estado no Redis por câmera.
"""
from __future__ import annotations

import json
import uuid
from functools import lru_cache
from typing import Any

from app.core.config import settings


def _iou(a: dict, b: dict) -> float:
    ax1, ay1 = a["bbox_x"], a["bbox_y"]
    ax2, ay2 = ax1 + a["bbox_w"], ay1 + a["bbox_h"]
    bx1, by1 = b["bbox_x"], b["bbox_y"]
    bx2, by2 = bx1 + b["bbox_w"], by1 + b["bbox_h"]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    union = (a["bbox_w"] * a["bbox_h"]) + (b["bbox_w"] * b["bbox_h"]) - inter
    return inter / union if union > 0 else 0.0


def update_tracks(
    state: list[dict], detections: list[dict], now: float
) -> tuple[list[dict], list[dict]]:
    """Atualiza os tracks com as detecções do frame.

    Args:
        state: tracks atuais (cada um: track_id, category, label, bbox,
            first_seen_at, last_seen_at, hits, counted).
        detections: detecções do frame (category, label, confidence, bbox).
        now: timestamp (segundos).

    Returns:
        (novo_estado, newly_counted). Cada item de `newly_counted` é o track que
        acabou de ser contado, com `det_index` apontando para a detecção que o
        originou neste frame (para o pipeline recortar/gravar o frame).
    """
    iou_min = settings.TRACK_IOU_MIN
    max_age = settings.TRACK_MAX_AGE_SECONDS
    min_hits = settings.TRACK_MIN_HITS

    # 1. Expira tracks de objetos que saíram do frame.
    tracks = [t for t in state if now - float(t["last_seen_at"]) <= max_age]

    # 2. Associação gulosa por IoU (mesma categoria), 1-para-1.
    pairs: list[tuple[float, int, int]] = []
    for di, det in enumerate(detections):
        for ti, tr in enumerate(tracks):
            if det["category"] != tr["category"]:
                continue
            iou = _iou(det["bbox"], tr["bbox"])
            if iou >= iou_min:
                pairs.append((iou, di, ti))
    pairs.sort(reverse=True)

    matched_det: dict[int, int] = {}
    matched_track: set[int] = set()
    for _iou_val, di, ti in pairs:
        if di in matched_det or ti in matched_track:
            continue
        matched_det[di] = ti
        matched_track.add(ti)

    newly: list[dict] = []

    # 3. Atualiza tracks casados.
    for di, ti in matched_det.items():
        tr = tracks[ti]
        tr["bbox"] = detections[di]["bbox"]
        tr["last_seen_at"] = now
        tr["hits"] = int(tr.get("hits", 1)) + 1
        if not tr.get("counted") and tr["hits"] >= min_hits:
            tr["counted"] = True
            newly.append({**tr, "det_index": di})

    # 4. Detecções sem casamento → novos tracks.
    for di, det in enumerate(detections):
        if di in matched_det:
            continue
        tr = {
            "track_id": uuid.uuid4().hex[:16],
            "category": det["category"],
            "label": det["label"],
            "bbox": det["bbox"],
            "first_seen_at": now,
            "last_seen_at": now,
            "hits": 1,
            "counted": False,
        }
        if tr["hits"] >= min_hits:
            tr["counted"] = True
            newly.append({**tr, "det_index": di})
        tracks.append(tr)

    return tracks, newly


# ─── Persistência por câmera (Redis) ──────────────────────────────────────────


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


def _key(camera_id: str) -> str:
    return f"camera-tracks:{camera_id}"


def load_tracks(camera_id: str) -> list[dict]:
    client = _redis_client()
    if client is None:
        return []
    try:
        raw = client.get(_key(camera_id))
        return json.loads(raw) if raw else []
    except Exception:
        return []


def save_tracks(camera_id: str, state: list[dict]) -> None:
    client = _redis_client()
    if client is None:
        return
    try:
        ttl = max(int(settings.TRACK_MAX_AGE_SECONDS * 4), 120)
        client.set(_key(camera_id), json.dumps(state), ex=ttl)
    except Exception:
        return


def track_camera(camera_id: str, detections: list[dict], now: float) -> list[dict]:
    """Carrega o estado, atualiza com as detecções, persiste e devolve newly_counted."""
    state = load_tracks(camera_id)
    state, newly = update_tracks(state, detections, now)
    save_tracks(camera_id, state)
    return newly
