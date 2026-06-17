"""Desenha bounding boxes + rótulo das detecções sobre o frame salvo (T2).

A imagem persistida no histórico passa a mostrar uma caixa em volta de cada
objeto detectado com o nome (e confiança) — ajuda a entender o que foi detectado
e a validar erros de classificação.

`cv2`/`numpy` são importados de forma preguiçosa: sem eles (ambiente de teste sem
OpenCV) a função devolve os bytes originais, sem quebrar.
"""
from __future__ import annotations

from typing import Iterable

from app.core.config import settings

# Cor por categoria (BGR, p/ cv2).
_CATEGORY_COLORS: dict[str, tuple[int, int, int]] = {
    "vehicle": (0, 200, 0),     # verde
    "person": (255, 160, 0),    # azul
    "animal": (0, 165, 255),    # laranja
}
_DEFAULT_COLOR = (200, 200, 200)


def label_text(label: str, confidence: float) -> str:
    """Texto exibido na caixa: '<label> <conf>%'."""
    try:
        pct = int(round(float(confidence) * 100))
    except (TypeError, ValueError):
        pct = 0
    return f"{label} {pct}%"


def _color_for(category: str) -> tuple[int, int, int]:
    return _CATEGORY_COLORS.get(category, _DEFAULT_COLOR)


def draw_detections(frame_bytes: bytes, detections: Iterable) -> bytes:
    """Devolve o JPEG com as caixas/labels desenhadas.

    `detections` são objetos com category, vehicle_type, confidence e bbox_*.
    Aceita também um `label_override` opcional por detecção (Tarefa 5: agrupar
    'moto e pessoa'). Sem cv2/numpy ou sem detecções, devolve os bytes originais.
    """
    dets = list(detections)
    if not dets:
        return frame_bytes
    try:
        import cv2
        import numpy as np
    except Exception:  # pragma: no cover - ambiente sem OpenCV
        return frame_bytes

    arr = np.frombuffer(frame_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return frame_bytes

    h, w = img.shape[:2]
    thickness = max(2, int(round(min(w, h) / 400)))
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = max(0.5, min(w, h) / 1000.0)

    for d in dets:
        category = getattr(d, "category", "vehicle")
        label = getattr(d, "label_override", None) or getattr(d, "vehicle_type", "obj")
        color = _color_for(category)
        x1 = max(0, int(getattr(d, "bbox_x", 0)))
        y1 = max(0, int(getattr(d, "bbox_y", 0)))
        x2 = min(w, x1 + int(getattr(d, "bbox_w", 0)))
        y2 = min(h, y1 + int(getattr(d, "bbox_h", 0)))
        if x2 <= x1 or y2 <= y1:
            continue
        cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)

        text = label_text(label, getattr(d, "confidence", 0.0))
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
