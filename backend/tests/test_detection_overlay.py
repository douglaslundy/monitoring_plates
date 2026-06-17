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
