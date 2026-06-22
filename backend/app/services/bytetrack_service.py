"""ByteTrack embutido — associação BYTE em dois estágios (numpy/python puro).

Implementa a ideia central do ByteTrack (Zhang et al., 2022): associar primeiro as
detecções de **alta** confiança e, num **segundo estágio**, recuperar tracks ainda
sem par usando as detecções de **baixa** confiança (que normalmente seriam
descartadas — ex.: objeto parcialmente ocluído). Detecções de baixa confiança que
não casam com nenhum track NÃO iniciam um track novo (evita falsos positivos).

Diferenças vs. o tracker legacy (`object_tracker_service`):
- associação por IoU em dois estágios por confiança (legacy usa IoU+centro num
  estágio só);
- detecção de baixa confiança recupera track existente, mas não cria track novo.

Modelo de movimento: velocidade constante (mesma `vx/vy` suavizada que o legacy
guarda no track) — leve e serializável; sem filtro de Kalman/torch. Pensado para
rodar com **frames em rajada durante o movimento** (ver capture_runner), regime em
que o IoU entre frames consecutivos é alto.

`associate` é pura (sem Redis/cv2): recebe os tracks e detecções e devolve o
mapeamento detecção→track e o conjunto de detecções proibidas de nascer. A máquina
de estados (contagem, estacionário, voto, OCR) é aplicada por `object_tracker_service`.
"""
from __future__ import annotations

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


def _predict(track: dict, now: float) -> dict:
    """Posição esperada do track agora (velocidade constante)."""
    b = track["bbox"]
    dt = max(0.0, now - float(track.get("last_seen_at", now)))
    vx = float(track.get("vx", 0.0) or 0.0)
    vy = float(track.get("vy", 0.0) or 0.0)
    if dt <= 0 or (vx == 0.0 and vy == 0.0):
        return b
    return {
        "bbox_x": b["bbox_x"] + vx * dt,
        "bbox_y": b["bbox_y"] + vy * dt,
        "bbox_w": b["bbox_w"],
        "bbox_h": b["bbox_h"],
    }


def associate(
    tracks: list[dict],
    detections: list[dict],
    now: float,
    high_thresh: float | None = None,
    low_thresh: float | None = None,
    match_iou: float | None = None,
) -> tuple[dict[int, int], set[int]]:
    """Associa detecções a tracks (BYTE, 2 estágios). Mesma categoria.

    Returns:
        (matched_det, spawn_block):
        - matched_det: índice_da_detecção -> índice_do_track (em `tracks`).
        - spawn_block: índices de detecções que NÃO podem iniciar track novo
          (baixa confiança sem casamento).
    """
    high_thresh = settings.BYTETRACK_HIGH_THRESH if high_thresh is None else high_thresh
    low_thresh = settings.BYTETRACK_LOW_THRESH if low_thresh is None else low_thresh
    match_iou = settings.BYTETRACK_MATCH_IOU if match_iou is None else match_iou

    predicted = [_predict(tr, now) for tr in tracks]
    # Candidato a casar só na mesma categoria: pré-filtramos por categoria no IoU
    # usando uma cópia de bbox "infinitamente distante" quando a categoria difere.
    def _cat_ok(di: int, ti: int) -> bool:
        return detections[di]["category"] == tracks[ti]["category"]

    high = [i for i, d in enumerate(detections) if float(d.get("confidence", 1.0)) >= high_thresh]
    low = [
        i
        for i, d in enumerate(detections)
        if low_thresh <= float(d.get("confidence", 1.0)) < high_thresh
    ]

    matched_det: dict[int, int] = {}
    used_tracks: set[int] = set()

    def _match(det_indices: list[int]) -> None:
        pairs: list[tuple[float, int, int]] = []
        for di in det_indices:
            for ti in range(len(tracks)):
                if ti in used_tracks or not _cat_ok(di, ti):
                    continue
                iou = _iou(detections[di]["bbox"], predicted[ti])
                if iou >= match_iou:
                    pairs.append((iou, di, ti))
        pairs.sort(reverse=True)
        for _iou_val, di, ti in pairs:
            if di in matched_det or ti in used_tracks:
                continue
            matched_det[di] = ti
            used_tracks.add(ti)

    # Estágio 1: alta confiança. Estágio 2: baixa confiança recupera tracks restantes.
    _match(high)
    _match(low)

    # Detecções de baixa confiança sem casamento não iniciam track novo.
    spawn_block = {di for di in low if di not in matched_det}
    return matched_det, spawn_block
