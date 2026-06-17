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


def _center(b: dict) -> tuple[float, float]:
    return (b["bbox_x"] + b["bbox_w"] / 2.0, b["bbox_y"] + b["bbox_h"] / 2.0)


def _center_dist(a: dict, b: dict) -> float:
    ca, cb = _center(a), _center(b)
    return ((ca[0] - cb[0]) ** 2 + (ca[1] - cb[1]) ** 2) ** 0.5


def _dist_gate(a: dict, b: dict) -> float:
    """Limite de distância de centro aceitável = fator × tamanho médio do bbox."""
    mean_size = (a["bbox_w"] + a["bbox_h"] + b["bbox_w"] + b["bbox_h"]) / 4.0
    return mean_size * settings.TRACK_CENTER_DIST_GATE


def update_tracks(
    state: list[dict], detections: list[dict], now: float
) -> tuple[list[dict], list[dict], dict[int, dict]]:
    """Atualiza os tracks com as detecções do frame.

    Associação por IoU **e** por proximidade do centro: um objeto em movimento
    entre frames amostrados pode não ter sobreposição (IoU=0), mas seu centro
    continua próximo, então segue o mesmo track e **não é recontado**. Só conta
    após `TRACK_MIN_HITS` frames associados (confirma que está sendo rastreado).

    Args:
        state: tracks atuais (cada um: track_id, category, label, bbox,
            first_seen_at, last_seen_at, hits, counted, [plate, plate_confidence,
            occurrence_id]).
        detections: detecções do frame (category, label, confidence, bbox).
        now: timestamp (segundos).

    Returns:
        (novo_estado, newly_counted, det_to_track).
        - `newly_counted`: tracks que acabaram de ser contados neste frame, com
          `det_index` apontando para a detecção que o originou.
        - `det_to_track`: mapa índice_da_detecção → track (referência mutável
          dentro de `novo_estado`), para o pipeline amarrar a placa ao track.
    """
    iou_min = settings.TRACK_IOU_MIN
    max_age = settings.TRACK_MAX_AGE_SECONDS
    min_hits = settings.TRACK_MIN_HITS

    # 1. Expira tracks de objetos que saíram do frame.
    tracks = [t for t in state if now - float(t["last_seen_at"]) <= max_age]

    # 2. Associação gulosa (mesma categoria), 1-para-1. Candidato aceito por IoU
    #    suficiente OU centro dentro do gate de distância. Ordena por IoU (desc)
    #    e, empatado, pelo centro mais próximo.
    pairs: list[tuple[float, float, int, int]] = []
    for di, det in enumerate(detections):
        for ti, tr in enumerate(tracks):
            if det["category"] != tr["category"]:
                continue
            iou = _iou(det["bbox"], tr["bbox"])
            dist = _center_dist(det["bbox"], tr["bbox"])
            if iou >= iou_min or dist <= _dist_gate(det["bbox"], tr["bbox"]):
                # score: prioriza IoU; desempata pela menor distância (-dist).
                pairs.append((iou, -dist, di, ti))
    pairs.sort(reverse=True)

    matched_det: dict[int, int] = {}
    matched_track: set[int] = set()
    for _iou_val, _neg_dist, di, ti in pairs:
        if di in matched_det or ti in matched_track:
            continue
        matched_det[di] = ti
        matched_track.add(ti)

    newly: list[dict] = []
    det_to_track: dict[int, dict] = {}

    # 3. Atualiza tracks casados.
    for di, ti in matched_det.items():
        tr = tracks[ti]
        tr["bbox"] = detections[di]["bbox"]
        tr["label"] = detections[di]["label"]
        tr["last_seen_at"] = now
        tr["hits"] = int(tr.get("hits", 1)) + 1
        if not tr.get("counted") and tr["hits"] >= min_hits:
            tr["counted"] = True
            newly.append({**tr, "det_index": di})
        det_to_track[di] = tr

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
        det_to_track[di] = tr

    return tracks, newly, det_to_track


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
    """Carrega o estado, atualiza com as detecções, persiste e devolve newly_counted.

    Atalho que NÃO expõe o mapa det→track (sem amarração de placa). Para o
    pipeline com placa, use load_tracks/update_tracks/save_tracks explicitamente.
    """
    state = load_tracks(camera_id)
    state, newly, _det_to_track = update_tracks(state, detections, now)
    save_tracks(camera_id, state)
    return newly
