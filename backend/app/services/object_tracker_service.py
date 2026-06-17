"""Rastreador multi-objeto por câmera (IoU + distância de centro), com contagem
única e máquina de estados de salvamento.

Cada objeto vira um *track*. Um track é **contado/salvo uma única vez** — quando
está confirmado (≥ `TRACK_MIN_HITS` frames associados) **e** aparece por completo
no frame (bbox sem tocar as bordas) — ou, como fallback, após `TRACK_FORCE_SAVE_HITS`
frames mesmo sem caber inteiro (veículo grande/cortado). Enquanto o objeto
permanece no frame — inclusive **parado** — a associação por IoU/centro mantém o
mesmo track, então **não há recontagem nem re-salvamento**.

Só há um novo salvamento (re-save) do mesmo track quando muda a **classe** do
objeto detectado. A mudança de **placa** é tratada pelo pipeline (occurrence).

Sobre objeto parado + motion gating: a captura só enfileira frames quando há
movimento, então uma cena estática não atualiza os tracks. Para um carro parado
não ser "redescoberto" como novo a cada vez que algo passa, `TRACK_MAX_AGE_SECONDS`
é generoso: o track sobrevive aos intervalos sem movimento e re-associa pelo
centro/IoU quando o objeto reaparece na mesma posição.

`update_tracks` é pura (testável sem Redis). `load_tracks/save_tracks` adicionam a
persistência por câmera no Redis.
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


def _fully_in_frame(bbox: dict, frame_w: int | None, frame_h: int | None) -> bool:
    """True se o bbox aparece por completo no frame (sem tocar as bordas).

    Quando as dimensões do frame não são conhecidas (testes puros), assume True —
    o gating de "objeto inteiro no frame" só se aplica quando há dimensões.
    """
    if not frame_w or not frame_h:
        return True
    margin_x = max(2.0, frame_w * settings.TRACK_EDGE_MARGIN_RATIO)
    margin_y = max(2.0, frame_h * settings.TRACK_EDGE_MARGIN_RATIO)
    x1 = bbox["bbox_x"]
    y1 = bbox["bbox_y"]
    x2 = x1 + bbox["bbox_w"]
    y2 = y1 + bbox["bbox_h"]
    return (
        x1 >= margin_x
        and y1 >= margin_y
        and x2 <= frame_w - margin_x
        and y2 <= frame_h - margin_y
    )


def update_tracks(
    state: list[dict],
    detections: list[dict],
    now: float,
    frame_w: int | None = None,
    frame_h: int | None = None,
) -> tuple[list[dict], list[dict], dict[int, dict]]:
    """Atualiza os tracks com as detecções do frame.

    Associação por IoU **e** por proximidade do centro: um objeto em movimento
    entre frames amostrados pode não ter sobreposição (IoU=0), mas seu centro
    continua próximo, então segue o mesmo track e **não é recontado**.

    Um track é registrado (contado + frame salvo) quando confirmado
    (`hits >= TRACK_MIN_HITS`) e: aparece inteiro no frame, OU já foi visto
    `TRACK_FORCE_SAVE_HITS` vezes (fallback p/ objeto que nunca cabe inteiro).
    Depois de registrado, só volta a `newly` se a **classe** mudar (re-save).

    Args:
        state: tracks atuais.
        detections: detecções do frame (category, label, confidence, bbox).
        now: timestamp (segundos).
        frame_w, frame_h: dimensões do frame (para o gating "inteiro no frame").

    Returns:
        (novo_estado, newly, det_to_track).
        - `newly`: registros deste frame. Cada item tem `det_index` e `reason`
          ("new" = 1ª vez/contagem; "class_change" = re-save por mudança de classe).
        - `det_to_track`: índice_da_detecção → track (referência mutável dentro de
          `novo_estado`), p/ o pipeline amarrar a placa ao track.
    """
    iou_min = settings.TRACK_IOU_MIN
    max_age = settings.TRACK_MAX_AGE_SECONDS
    min_hits = settings.TRACK_MIN_HITS
    force_hits = settings.TRACK_FORCE_SAVE_HITS

    # 1. Expira tracks de objetos que saíram do frame há mais que max_age.
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

    def _maybe_register(tr: dict, di: int) -> None:
        """Decide se o track gera um registro (1ª vez ou re-save por classe)."""
        bbox = detections[di]["bbox"]
        confirmed = tr["hits"] >= min_hits
        if not tr.get("counted"):
            if not confirmed:
                return
            if _fully_in_frame(bbox, frame_w, frame_h) or tr["hits"] >= force_hits:
                tr["counted"] = True
                tr["saved_label"] = tr["label"]
                newly.append({**tr, "det_index": di, "reason": "new"})
        else:
            # Já contado: re-save apenas se a classe detectada mudou.
            if tr["label"] != tr.get("saved_label"):
                tr["saved_label"] = tr["label"]
                newly.append({**tr, "det_index": di, "reason": "class_change"})

    # 3. Atualiza tracks casados.
    for di, ti in matched_det.items():
        tr = tracks[ti]
        tr["bbox"] = detections[di]["bbox"]
        tr["label"] = detections[di]["label"]
        tr["last_seen_at"] = now
        tr["hits"] = int(tr.get("hits", 1)) + 1
        _maybe_register(tr, di)
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
            "saved_label": None,
        }
        _maybe_register(tr, di)
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
    """Carrega o estado, atualiza com as detecções, persiste e devolve newly.

    Atalho que NÃO expõe o mapa det→track (sem amarração de placa). Para o
    pipeline com placa, use load_tracks/update_tracks/save_tracks explicitamente.
    """
    state = load_tracks(camera_id)
    state, newly, _det_to_track = update_tracks(state, detections, now)
    save_tracks(camera_id, state)
    return newly
