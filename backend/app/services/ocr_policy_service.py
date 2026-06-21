"""Política de OCR híbrida — decisão pura (sem db/cv2/redis), por track/frame.

Decide o que fazer com o recorte de um veículo confirmado, dado o estado de OCR
do track e a qualidade do frame atual. Mantida pura para ser testável sem o
ambiente pesado (cv2/celery): o `frame_processor` só aplica a ação.

Ações:
- ``read``    : 1ª leitura do track — roda OCR e cria a ocorrência (+ alerta).
- ``refine``  : track já lido, surgiu frame bem melhor — re-OCR p/ refinar.
- ``dormant`` : objeto parado já resolvido (lido ou esgotou tentativas) — o
                caller marca ``ocr_state='dormant'`` e nunca mais roda OCR.
- ``skip``    : nada a fazer neste frame.
"""
from __future__ import annotations


def decide_ocr_action(
    *,
    ocr_state: str,
    stationary: bool,
    ocr_attempts: int,
    quality: float,
    best_quality: float,
    min_quality: float,
    refine_margin: float,
    stationary_max_attempts: int,
) -> str:
    """Decide a ação de OCR para um track de veículo neste frame.

    Args:
        ocr_state: estado atual ('pending' | 'read' | 'dormant').
        stationary: se o track está parado.
        ocr_attempts: nº de OCRs já tentados neste track.
        quality: qualidade do recorte do frame atual (0..1).
        best_quality: qualidade do melhor frame já usado no OCR (0..1).
        min_quality: qualidade mínima p/ rodar OCR.
        refine_margin: fração mínima de melhora p/ refinar (ex.: 0.15 = 15%).
        stationary_max_attempts: tentativas antes de dormir um parado sem leitura.

    Returns:
        'read' | 'refine' | 'dormant' | 'skip'.
    """
    if ocr_state == "dormant":
        return "skip"

    # Parado e já resolvido (lido) OU já tentou demais sem ler -> dorme. Tem
    # prioridade sobre o refino: não faz sentido refinar um objeto estacionado.
    if stationary and (ocr_state == "read" or ocr_attempts >= stationary_max_attempts):
        return "dormant"

    if quality < min_quality:
        return "skip"

    if ocr_state == "read":
        if quality < best_quality * (1.0 + refine_margin):
            return "skip"
        return "refine"

    return "read"
