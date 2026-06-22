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


def _predict_bbox(tr: dict, now: float) -> dict:
    """Posição ESPERADA do track agora, extrapolando pela velocidade (px/s).

    O worker processa frames mais devagar que a captura (latência do OCR), então
    um objeto em movimento se desloca bastante entre frames processados. Prever a
    posição pela velocidade do track evita que ele perca a associação e seja
    recontado (causa de 3-4 registros do mesmo objeto). Sem velocidade ainda
    (track novo), devolve o próprio bbox.
    """
    dt = max(0.0, now - float(tr.get("last_seen_at", now)))
    vx = float(tr.get("vx", 0.0) or 0.0)
    vy = float(tr.get("vy", 0.0) or 0.0)
    b = tr["bbox"]
    if dt <= 0 or (vx == 0.0 and vy == 0.0):
        return b
    return {
        "bbox_x": b["bbox_x"] + vx * dt,
        "bbox_y": b["bbox_y"] + vy * dt,
        "bbox_w": b["bbox_w"],
        "bbox_h": b["bbox_h"],
    }


def _vote_key(category: str, label: str) -> str:
    return f"{category}|{label}"


def _winning_class(votes: dict) -> tuple[str, str]:
    """Categoria/label com mais votos no track (voto temporal de classe)."""
    key = max(votes, key=lambda k: votes[k])
    category, _, label = key.partition("|")
    return category, label


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
    backend: str = "legacy",
) -> tuple[list[dict], list[dict], dict[int, dict], list[dict]]:
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
        (novo_estado, newly, det_to_track, expired).
        - `newly`: registros deste frame. Cada item tem `det_index` e `reason`
          ("new" = 1ª vez/contagem; "class_change" = re-save por mudança de classe).
        - `det_to_track`: índice_da_detecção → track (referência mutável dentro de
          `novo_estado`), p/ o pipeline amarrar a placa ao track.
        - `expired`: tracks removidos por idade NESTE frame (cada um mantém seus
          campos, incl. `track_id`, `first_seen_at`, `last_seen_at`, `category` e
          eventuais `face_detection_id` gravados pelo pipeline facial).
    """
    iou_min = settings.TRACK_IOU_MIN
    max_age = settings.TRACK_MAX_AGE_SECONDS
    min_hits = settings.TRACK_MIN_HITS
    force_hits = settings.TRACK_FORCE_SAVE_HITS

    # 1. Expira tracks de objetos que saíram do frame. Um track ESTACIONÁRIO
    #    (objeto parado) sobrevive muito mais tempo, para não ser redescoberto
    #    como novo quando algo passa após um longo período sem movimento.
    def _eff_max_age(t: dict) -> float:
        if t.get("stationary"):
            return settings.TRACK_STATIONARY_MAX_AGE_SECONDS
        return max_age

    expired = [t for t in state if now - float(t["last_seen_at"]) > _eff_max_age(t)]
    tracks = [t for t in state if now - float(t["last_seen_at"]) <= _eff_max_age(t)]

    # 2. Associação detecção→track. Dois backends, MESMA máquina de estados depois.
    #    spawn_block = detecções proibidas de iniciar track novo (ByteTrack: baixa
    #    confiança sem casamento).
    matched_det: dict[int, int] = {}
    spawn_block: set[int] = set()
    if backend == "bytetrack":
        from app.services.bytetrack_service import associate as _bt_associate

        matched_det, spawn_block = _bt_associate(tracks, detections, now)
    else:
        # Legacy: associação gulosa (mesma categoria), 1-para-1. Candidato aceito
        # por IoU suficiente OU centro dentro do gate. Ordena por IoU (desc) e,
        # empatado, pelo centro mais próximo.
        matched_track: set[int] = set()
        pairs: list[tuple[float, float, int, int]] = []
        for di, det in enumerate(detections):
            for ti, tr in enumerate(tracks):
                if det["category"] != tr["category"]:
                    continue
                ptr = _predict_bbox(tr, now)
                iou = _iou(det["bbox"], ptr)
                dist = _center_dist(det["bbox"], ptr)
                if iou >= iou_min or dist <= _dist_gate(det["bbox"], ptr):
                    pairs.append((iou, -dist, di, ti))
        pairs.sort(reverse=True)
        for _iou_val, _neg_dist, di, ti in pairs:
            if di in matched_det or ti in matched_track:
                continue
            matched_det[di] = ti
            matched_track.add(ti)

        # 2b. Associação CROSS-CATEGORY por IoU muito alto: o mesmo objeto físico
        #     classificado de formas diferentes entre frames (cão ora "dog" ora
        #     "person") mantém caixas quase idênticas. Sobreposição >= limiar alto =
        #     mesmo objeto -> associa para o track VOTAR a classe (corrige o erro
        #     por maioria), sem fundir objetos realmente distintos.
        same_obj_iou = settings.TRACK_SAME_OBJECT_IOU
        cross: list[tuple[float, int, int]] = []
        for di, det in enumerate(detections):
            if di in matched_det:
                continue
            for ti, tr in enumerate(tracks):
                if ti in matched_track or det["category"] == tr["category"]:
                    continue
                iou = _iou(det["bbox"], _predict_bbox(tr, now))
                if iou >= same_obj_iou:
                    cross.append((iou, di, ti))
        cross.sort(reverse=True)
        for _iou_val, di, ti in cross:
            if di in matched_det or ti in matched_track:
                continue
            matched_det[di] = ti
            matched_track.add(ti)

    newly: list[dict] = []
    det_to_track: dict[int, dict] = {}

    def _maybe_register(tr: dict, di: int) -> None:
        """Decide se o track gera um registro (1ª vez ou re-save por classe).

        A classe usada é a VOTADA (maioria ao longo do track), não a do frame —
        um erro pontual de classificação não vira registro nem dispara re-save.

        Regras de contagem por categoria:
        - **veículo**: conta quando confirmado E aparece inteiro no frame (ou após
          `TRACK_FORCE_SAVE_HITS`). Precisa do frame bom p/ a imagem/placa.
        - **pessoa/animal**: conta quando confirmado E a classe vencedora tem
          `TRACK_MIN_REGISTER_VOTES` votos. NÃO exige caber inteiro — um animal
          que cruza rápido pela borda ainda é contado; o voto evita registrar uma
          classificação errada de 1 frame (cão<->pessoa).
        """
        bbox = detections[di]["bbox"]
        confirmed = tr["hits"] >= min_hits
        current_class = _vote_key(tr["category"], tr["label"])
        if not tr.get("counted"):
            if not confirmed:
                return
            if tr["category"] == "vehicle":
                ready = _fully_in_frame(bbox, frame_w, frame_h) or tr["hits"] >= force_hits
            else:
                ready = tr.get("votes", {}).get(current_class, 0) >= settings.TRACK_MIN_REGISTER_VOTES
            if ready:
                tr["counted"] = True
                tr["saved_class"] = current_class
                newly.append({**tr, "det_index": di, "reason": "new"})
        else:
            # Já contado: re-save só se a classe VOTADA mudar DE FORMA ESTÁVEL —
            # a nova classe precisa ter uma margem de votos sobre a salva. Isso
            # evita re-save a cada flicker do detector (ex.: bus<->car alternando),
            # que gerava vários registros do mesmo objeto.
            saved_class = tr.get("saved_class")
            if current_class != saved_class:
                votes = tr.get("votes", {})
                margin = votes.get(current_class, 0) - votes.get(saved_class, 0)
                if margin >= settings.TRACK_CLASS_CHANGE_MARGIN:
                    tr["saved_class"] = current_class
                    newly.append({**tr, "det_index": di, "reason": "class_change"})

    # 3. Atualiza tracks casados.
    for di, ti in matched_det.items():
        tr = tracks[ti]
        new_bbox = detections[di]["bbox"]
        # Estacionariedade: média móvel (EMA) do deslocamento do centro por frame.
        # Parado -> deslocamento ~0; em movimento -> grande. Um objeto que parou
        # após se mover passa a estacionário em poucos frames (a EMA decai).
        disp = _center_dist(new_bbox, tr["bbox"])
        ema = tr.get("avg_disp")
        tr["avg_disp"] = disp if ema is None else (0.6 * float(ema) + 0.4 * disp)
        mean_size = (new_bbox["bbox_w"] + new_bbox["bbox_h"]) / 2.0
        tr["stationary"] = (
            int(tr.get("hits", 1)) + 1 >= settings.TRACK_STATIONARY_MIN_HITS
            and mean_size > 0
            and tr["avg_disp"] <= settings.TRACK_STATIONARY_RADIUS_RATIO * mean_size
        )
        # Velocidade (px/s) do centro, com suavização (EMA), p/ prever a posição
        # no próximo frame processado e manter a associação de objetos em movimento.
        dt = now - float(tr["last_seen_at"])
        if dt > 0:
            oc = _center(tr["bbox"])
            nc = _center(new_bbox)
            vx, vy = (nc[0] - oc[0]) / dt, (nc[1] - oc[1]) / dt
            if tr.get("vx") is None:
                tr["vx"], tr["vy"] = vx, vy
            else:
                tr["vx"] = 0.5 * float(tr["vx"]) + 0.5 * vx
                tr["vy"] = 0.5 * float(tr["vy"]) + 0.5 * vy
        tr["bbox"] = new_bbox
        # Voto temporal de classe: acumula votos e adota a categoria/label de maioria.
        votes = tr.setdefault("votes", {})
        vk = _vote_key(detections[di]["category"], detections[di]["label"])
        votes[vk] = votes.get(vk, 0) + 1
        tr["category"], tr["label"] = _winning_class(votes)
        tr["last_seen_at"] = now
        tr["hits"] = int(tr.get("hits", 1)) + 1
        _maybe_register(tr, di)
        det_to_track[di] = tr

    # 4. Detecções sem casamento → novos tracks (exceto as bloqueadas: no
    #    ByteTrack, detecções de baixa confiança sem par não iniciam track).
    for di, det in enumerate(detections):
        if di in matched_det or di in spawn_block:
            continue
        tr = {
            "track_id": uuid.uuid4().hex[:16],
            "category": det["category"],
            "label": det["label"],
            "votes": {_vote_key(det["category"], det["label"]): 1},
            "bbox": det["bbox"],
            "first_seen_at": now,
            "last_seen_at": now,
            "hits": 1,
            "counted": False,
            "saved_class": None,
            "avg_disp": None,
            "stationary": False,
            "vx": None,
            "vy": None,
            # Máquina de OCR (gerida pelo frame_processor): pending -> read ->
            # dormant. best_quality = qualidade (0..1) do melhor frame já usado no
            # OCR deste track, p/ decidir refino. Persistem no Redis (JSON-safe).
            "ocr_state": "pending",
            "best_quality": 0.0,
            "occurrence_id": None,
            "plate": None,
            "plate_confidence": 0.0,
            "stationary_since": None,
        }
        _maybe_register(tr, di)
        tracks.append(tr)
        det_to_track[di] = tr

    return tracks, newly, det_to_track, expired


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
        # TTL deve cobrir a vida de um track ESTACIONÁRIO (senão a chave expira no
        # Redis antes de TRACK_STATIONARY_MAX_AGE_SECONDS e o objeto parado é
        # recontado quando a próxima detecção chega). Bug anterior: 120s fixo, bem
        # menor que a vida do estacionário (300s+).
        ttl = int(max(settings.TRACK_STATIONARY_MAX_AGE_SECONDS, settings.TRACK_MAX_AGE_SECONDS) * 2)
        ttl = max(ttl, 120)
        client.set(_key(camera_id), json.dumps(state), ex=ttl)
    except Exception:
        return


def track_camera(camera_id: str, detections: list[dict], now: float) -> list[dict]:
    """Carrega o estado, atualiza com as detecções, persiste e devolve newly.

    Atalho que NÃO expõe o mapa det→track (sem amarração de placa). Para o
    pipeline com placa, use load_tracks/update_tracks/save_tracks explicitamente.
    """
    state = load_tracks(camera_id)
    state, newly, _det_to_track, _expired = update_tracks(state, detections, now)
    save_tracks(camera_id, state)
    return newly
