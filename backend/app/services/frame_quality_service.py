"""Score de qualidade de um recorte de objeto para escolher o "melhor frame".

Sistemas ANPR não leem a placa de um frame qualquer: capturam vários frames do
mesmo veículo e selecionam o de melhor qualidade para o OCR (menos borrão, placa
maior, objeto inteiro no quadro). Aqui calculamos um score 0..1 por recorte,
combinando:

- nitidez/exposição da imagem (reaproveita `image_quality_service`, base PIL);
- tamanho do objeto no frame (placa maior = mais legível);
- centralidade (bordas costumam ter mais distorção/borrão de movimento);
- confiança do detector;
- penalidade se o objeto não couber inteiro no frame.

`combine_quality` é pura (recebe o score de imagem já calculado) e portanto
testável sem decodificar imagem. `crop_quality` decodifica o JPEG do recorte e
chama `combine_quality`. Sem custo de cv2 — usa o pipeline PIL existente.
"""
from __future__ import annotations

from app.services.image_quality_service import analyze_image_quality

# Pesos da combinação. Nitidez e tamanho dominam: são o que mais afeta a leitura
# correta da placa pelo OCR.
_W_IMAGE = 0.50
_W_SIZE = 0.30
_W_CENTER = 0.05
_W_CONF = 0.15
# Razão de área (objeto/frame) na qual o componente de tamanho satura em 1.0.
_SIZE_SATURATION = 0.15
# Multiplicador quando o objeto não aparece inteiro no frame (placa pode estar
# cortada/entrando em cena).
_PARTIAL_PENALTY = 0.6


def combine_quality(
    image_score: float,
    *,
    confidence: float,
    area_ratio: float,
    centrality: float,
    fully_in_frame: bool,
) -> float:
    """Combina os componentes em um score 0..1.

    Args:
        image_score: nitidez/exposição já normalizada em 0..1.
        confidence: confiança do detector (0..1).
        area_ratio: área do objeto / área do frame (0..1).
        centrality: 0..1, 1 = centro do frame.
        fully_in_frame: se o objeto cabe inteiro no quadro.
    """
    image_c = _clamp01(image_score)
    conf_c = _clamp01(confidence)
    size_c = min(1.0, max(0.0, area_ratio) / _SIZE_SATURATION)
    center_c = _clamp01(centrality)
    score = (
        _W_IMAGE * image_c
        + _W_SIZE * size_c
        + _W_CENTER * center_c
        + _W_CONF * conf_c
    )
    if not fully_in_frame:
        score *= _PARTIAL_PENALTY
    return _clamp01(score)


def crop_quality(
    crop_bytes: bytes,
    *,
    confidence: float,
    bbox_w: int,
    bbox_h: int,
    frame_w: int,
    frame_h: int,
    fully_in_frame: bool,
    bbox_x: int = 0,
    bbox_y: int = 0,
) -> float:
    """Score 0..1 de um recorte (JPEG) para a seleção do melhor frame do OCR."""
    if not crop_bytes:
        return 0.0
    image_score = analyze_image_quality(crop_bytes).quality_score / 100.0

    frame_area = max(frame_w * frame_h, 1)
    area_ratio = (bbox_w * bbox_h) / frame_area if frame_w and frame_h else 0.0

    if frame_w and frame_h:
        center_x = (bbox_x + bbox_w / 2.0) / frame_w
        center_y = (bbox_y + bbox_h / 2.0) / frame_h
        centrality = 1.0 - min(1.0, abs(center_x - 0.5) + abs(center_y - 0.5))
    else:
        centrality = 0.5

    return combine_quality(
        image_score,
        confidence=confidence,
        area_ratio=area_ratio,
        centrality=centrality,
        fully_in_frame=fully_in_frame,
    )


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
