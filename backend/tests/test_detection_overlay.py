"""T2: overlay de bounding box + rótulo no frame salvo."""
from types import SimpleNamespace

from app.services.detection_overlay_service import draw_detections, label_text


def _det(label="car", category="vehicle", conf=0.91):
    return SimpleNamespace(
        category=category,
        vehicle_type=label,
        confidence=conf,
        bbox_x=10,
        bbox_y=20,
        bbox_w=100,
        bbox_h=80,
    )


def test_label_text_formata_label_e_confianca():
    assert label_text("car", 0.91) == "car 91%"
    assert label_text("dog", 0.4) == "dog 40%"


def test_label_text_confianca_invalida():
    assert label_text("person", None) == "person 0%"


def test_draw_sem_deteccoes_retorna_original():
    original = b"\xff\xd8\xff\xe0qualquer-bytes"
    assert draw_detections(original, []) == original


def test_draw_bytes_invalidos_retorna_original():
    # Bytes que não decodificam como imagem (ou ambiente sem cv2) -> original.
    original = b"nao-e-um-jpeg-valido"
    assert draw_detections(original, [_det()]) == original


def test_draw_aceita_highlight_e_only_index():
    # Smoke: parâmetros de destaque/solo aceitos e retornam bytes (Tarefas B/D).
    original = b"nao-e-um-jpeg-valido"
    out = draw_detections(
        original, [_det(), _det(label="truck")], highlight_index=1, highlight_label="ABC1234", only_index=1
    )
    assert isinstance(out, bytes)


def test_draw_only_index_desenha_apenas_uma_caixa():
    """Com only_index, apenas a caixa daquela detecção é desenhada (verifica via
    cv2: a saída de only_index difere da de todas as caixas)."""
    import pytest

    cv2 = pytest.importorskip("cv2")
    import numpy as np

    img = np.full((200, 300, 3), 50, dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    base = buf.tobytes()
    a = _det()  # bbox (10,20,100,80)
    b = SimpleNamespace(category="vehicle", vehicle_type="truck", confidence=0.8,
                        bbox_x=180, bbox_y=100, bbox_w=90, bbox_h=70)

    all_boxes = draw_detections(base, [a, b])
    only_first = draw_detections(base, [a, b], only_index=0)
    # Desenhar só uma caixa produz imagem diferente de desenhar as duas.
    assert all_boxes != only_first
    assert isinstance(only_first, bytes) and len(only_first) > 0
