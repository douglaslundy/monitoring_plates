"""Agrupamento piloto+moto (T5).

Uma pessoa em cima de uma moto gera duas detecções com quase o mesmo frame.
`group_riders` identifica esses pares (pessoa "em cima" da moto) para o pipeline
gravar UMA detecção (moto principal + pessoa como companion) e ainda contar os
dois nas estatísticas.

Função pura (sem cv2/Redis), testável diretamente.
"""
from __future__ import annotations

from typing import Sequence

from app.core.config import settings


def _bbox(d) -> tuple[int, int, int, int]:
    x1 = int(getattr(d, "bbox_x", 0))
    y1 = int(getattr(d, "bbox_y", 0))
    return x1, y1, x1 + int(getattr(d, "bbox_w", 0)), y1 + int(getattr(d, "bbox_h", 0))


def _area(b: tuple[int, int, int, int]) -> float:
    return max(0, b[2] - b[0]) * max(0, b[3] - b[1])


def _intersection(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    return max(0, ix2 - ix1) * max(0, iy2 - iy1)


def group_riders(detections: Sequence) -> dict[int, int]:
    """Mapeia índice_da_pessoa -> índice_da_moto para pilotos.

    Pessoa é piloto quando seu bbox sobrepõe a moto em >= RIDER_OVERLAP_MIN da
    área da pessoa E seu centro horizontal cai dentro da moto. Cada moto recebe
    no máximo um piloto (o de maior sobreposição).
    """
    persons = [
        i for i, d in enumerate(detections) if getattr(d, "category", "") == "person"
    ]
    motos = [
        i
        for i, d in enumerate(detections)
        if getattr(d, "category", "") == "vehicle"
        and getattr(d, "vehicle_type", "") == "motorcycle"
    ]
    if not persons or not motos:
        return {}

    overlap_min = settings.RIDER_OVERLAP_MIN
    candidates: list[tuple[float, int, int]] = []
    for pi in persons:
        pb = _bbox(detections[pi])
        pa = _area(pb)
        if pa <= 0:
            continue
        center_x = (pb[0] + pb[2]) / 2.0
        for mi in motos:
            mb = _bbox(detections[mi])
            overlap = _intersection(pb, mb) / pa
            within = mb[0] <= center_x <= mb[2]
            if overlap >= overlap_min and within:
                candidates.append((overlap, pi, mi))

    candidates.sort(reverse=True)
    result: dict[int, int] = {}
    used_moto: set[int] = set()
    for _overlap, pi, mi in candidates:
        if pi in result or mi in used_moto:
            continue
        result[pi] = mi
        used_moto.add(mi)
    return result
