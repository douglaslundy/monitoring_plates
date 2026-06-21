"""Score de qualidade de recorte para a seleção do "melhor frame" do OCR.

`combine_quality` é pura (sem decodificar imagem) — testada diretamente.
`crop_quality` decodifica o JPEG (via PIL) e combina com a geometria.
"""
from io import BytesIO

import pytest

from app.services.frame_quality_service import combine_quality, crop_quality


def test_combine_quality_no_intervalo_0_1():
    s = combine_quality(0.5, confidence=0.8, area_ratio=0.1, centrality=0.5, fully_in_frame=True)
    assert 0.0 <= s <= 1.0


def test_imagem_mais_nitida_pontua_mais():
    base = dict(confidence=0.8, area_ratio=0.1, centrality=0.5, fully_in_frame=True)
    nitido = combine_quality(0.9, **base)
    borrado = combine_quality(0.2, **base)
    assert nitido > borrado


def test_objeto_maior_pontua_mais():
    base = dict(image_score=0.6, confidence=0.8, centrality=0.5, fully_in_frame=True)
    grande = combine_quality(area_ratio=0.20, **base)
    pequeno = combine_quality(area_ratio=0.01, **base)
    assert grande > pequeno


def test_fora_do_frame_penaliza():
    base = dict(image_score=0.6, confidence=0.8, area_ratio=0.1, centrality=0.5)
    inteiro = combine_quality(fully_in_frame=True, **base)
    cortado = combine_quality(fully_in_frame=False, **base)
    assert cortado < inteiro


def test_maior_confianca_pontua_mais():
    base = dict(image_score=0.6, area_ratio=0.1, centrality=0.5, fully_in_frame=True)
    assert combine_quality(confidence=0.95, **base) > combine_quality(confidence=0.4, **base)


def _jpeg(color: int, size=(80, 80)) -> bytes:
    from PIL import Image

    img = Image.new("L", size, color=color)
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_crop_quality_decodifica_e_retorna_intervalo():
    pytest.importorskip("PIL")
    crop = _jpeg(128)
    s = crop_quality(crop, confidence=0.8, bbox_w=100, bbox_h=80, frame_w=640, frame_h=480, fully_in_frame=True)
    assert 0.0 <= s <= 1.0


def test_crop_quality_invalido_retorna_zero():
    assert crop_quality(b"", confidence=0.8, bbox_w=10, bbox_h=10, frame_w=640, frame_h=480, fully_in_frame=True) == 0.0
