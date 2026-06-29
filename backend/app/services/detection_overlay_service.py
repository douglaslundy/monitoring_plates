"""Desenha bounding boxes + rótulo das detecções sobre o frame salvo (T2).

A imagem persistida no histórico passa a mostrar uma caixa em volta de cada
objeto detectado com o nome (e confiança) — ajuda a entender o que foi detectado
e a validar erros de classificação.

`cv2`/`numpy` são importados de forma preguiçosa: sem eles (ambiente de teste sem
OpenCV) a função devolve os bytes originais, sem quebrar.
"""
from __future__ import annotations

import logging
from typing import Iterable

from app.core.config import settings

logger = logging.getLogger(__name__)

# Cor por categoria (BGR, p/ cv2).
_CATEGORY_COLORS: dict[str, tuple[int, int, int]] = {
    "vehicle": (0, 200, 0),     # verde
    "person": (255, 160, 0),    # azul
    "animal": (0, 165, 255),    # laranja
}
_DEFAULT_COLOR = (200, 200, 200)
# Cor do veículo destacado (o da ocorrência) — amarelo (BGR), bem visível.
_HIGHLIGHT_COLOR = (0, 255, 255)


def draw_labeled_boxes(
    frame_bytes: bytes,
    boxes: list[dict],
) -> str:
    """Desenha bboxes com rótulos em uma imagem e retorna base64 JPEG.

    Cada item de `boxes`: {"x", "y", "w", "h", "label": str, "highlight": bool}.
    Usado nos endpoints de teste (OCR e face) para visualização imediata.
    Retorna string base64 vazia se cv2 não estiver disponível.
    """
    try:
        import base64
        import cv2
        import numpy as np
    except Exception:
        return ""

    arr = np.frombuffer(frame_bytes, np.uint8).copy()
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return ""

    h, w = img.shape[:2]
    thickness = max(2, int(round(min(w, h) / 300)))
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = max(0.5, min(w, h) / 800.0)

    for box in boxes:
        x1 = max(0, int(box["x"]))
        y1 = max(0, int(box["y"]))
        x2 = min(w, x1 + int(box["w"]))
        y2 = min(h, y1 + int(box["h"]))
        if x2 <= x1 or y2 <= y1:
            continue

        color = _HIGHLIGHT_COLOR if box.get("highlight") else (0, 200, 0)
        box_t = thickness * 2 if box.get("highlight") else thickness
        cv2.rectangle(img, (x1, y1), (x2, y2), color, box_t)

        text = str(box.get("label", ""))
        if text:
            (tw, th), baseline = cv2.getTextSize(text, font, font_scale, thickness)
            ty = y1 - 4
            top = ty - th - baseline
            if top < 0:
                ty = y1 + th + baseline + 4
                top = y1
            cv2.rectangle(img, (x1, top), (x1 + tw + 6, ty + baseline), color, -1)
            cv2.putText(img, text, (x1 + 3, ty), font, font_scale, (0, 0, 0), thickness, cv2.LINE_AA)

    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    if not ok:
        return ""
    return base64.b64encode(buf.tobytes()).decode()


def label_text(label: str, confidence: float) -> str:
    """Texto exibido na caixa: '<label> <conf>%'."""
    try:
        pct = int(round(float(confidence) * 100))
    except (TypeError, ValueError):
        pct = 0
    return f"{label} {pct}%"


def _color_for(category: str) -> tuple[int, int, int]:
    return _CATEGORY_COLORS.get(category, _DEFAULT_COLOR)


def draw_detections(
    frame_bytes: bytes,
    detections: Iterable,
    highlight_index: int | None = None,
    highlight_label: str | None = None,
    only_index: int | None = None,
    annotations: dict[int, dict] | None = None,
) -> bytes:
    """Devolve o JPEG com as caixas/labels desenhadas.

    `detections` são objetos com category, vehicle_type, confidence e bbox_*.
    Aceita também um `label_override` opcional por detecção (Tarefa 5: agrupar
    'moto e pessoa'). Sem cv2/numpy ou sem detecções, devolve os bytes originais.

    Tarefa B: `highlight_index` marca o veículo da ocorrência atual — sua caixa é
    desenhada destacada (amarela, mais grossa) e recebe `highlight_label` (a PLACA)
    escrita por cima, para identificar de qual veículo é a placa quando há vários
    no frame. Os demais objetos ficam com a caixa/label normais.

    Tarefa D (visual): `only_index` faz desenhar SOMENTE a caixa daquela detecção
    (as outras ficam sem caixa). Assim o frame salvo de cada detecção mostra só o
    objeto a que se refere — sem parecer "detecção triplicada" quando passam vários
    veículos. É apenas a imagem salva; o rastreamento usa TODAS as detecções.

    Imagem única por frame: `annotations` = {índice_da_detecção: {"label": str,
    "highlight": bool}}. Quando informado, desenha SOMENTE os índices anotados —
    cada um com seu rótulo (placa ou classe) e realce opcional (amarelo, para o
    veículo com placa). Usado para uma imagem só por frame com bbox apenas nos
    objetos NOVOS daquele frame.
    """
    dets = list(detections)
    if not dets:
        return frame_bytes
    try:
        import cv2
        import numpy as np
    except Exception:  # pragma: no cover - ambiente sem OpenCV
        return frame_bytes

    arr = np.frombuffer(frame_bytes, np.uint8).copy()
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        logger.warning("draw_detections: cv2.imdecode falhou (bytes=%d) — salvando frame original", len(frame_bytes))
        return frame_bytes

    h, w = img.shape[:2]
    thickness = max(2, int(round(min(w, h) / 400)))
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = max(0.5, min(w, h) / 1000.0)

    for idx, d in enumerate(dets):
        forced_label: str | None = None
        if annotations is not None:
            if idx not in annotations:
                continue  # Imagem única: desenha só os índices anotados.
            ann = annotations[idx]
            is_highlight = bool(ann.get("highlight"))
            forced_label = ann.get("label")
        else:
            if only_index is not None and idx != only_index:
                continue  # Tarefa D: desenha só a caixa desta detecção.
            is_highlight = highlight_index is not None and idx == highlight_index
            if is_highlight and highlight_label:
                forced_label = highlight_label
        category = getattr(d, "category", "vehicle")
        label = getattr(d, "label_override", None) or getattr(d, "vehicle_type", "obj")
        color = _HIGHLIGHT_COLOR if is_highlight else _color_for(category)
        box_thickness = thickness * 2 if is_highlight else thickness
        x1 = max(0, int(getattr(d, "bbox_x", 0)))
        y1 = max(0, int(getattr(d, "bbox_y", 0)))
        x2 = min(w, x1 + int(getattr(d, "bbox_w", 0)))
        y2 = min(h, y1 + int(getattr(d, "bbox_h", 0)))
        if x2 <= x1 or y2 <= y1:
            continue
        cv2.rectangle(img, (x1, y1), (x2, y2), color, box_thickness)

        text = forced_label if forced_label else label_text(label, getattr(d, "confidence", 0.0))
        (tw, th), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        # Faixa de fundo do texto, acima da caixa (ou dentro se colar no topo).
        ty = y1 - 4
        top = ty - th - baseline
        if top < 0:
            ty = y1 + th + baseline + 4
            top = y1
        cv2.rectangle(img, (x1, top), (x1 + tw + 6, ty + baseline), color, -1)
        cv2.putText(img, text, (x1 + 3, ty), font, font_scale, (0, 0, 0), thickness, cv2.LINE_AA)

    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, settings.CAPTURE_JPEG_QUALITY])
    return buf.tobytes() if ok else frame_bytes
