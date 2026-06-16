"""Task 2.1: rastreador multi-objeto (IoU+tempo, count-once)."""
from app.services.object_tracker_service import update_tracks


def _box(x, y, w=50, h=50, category="vehicle", label="car"):
    return {
        "category": category,
        "label": label,
        "confidence": 0.8,
        "bbox": {"bbox_x": x, "bbox_y": y, "bbox_w": w, "bbox_h": h},
    }


def test_objeto_parado_conta_uma_vez():
    box = _box(100, 100)
    state: list = []
    total = 0
    for i in range(10):
        state, newly = update_tracks(state, [box], now=1000.0 + i * 0.5)
        total += len(newly)
    assert total == 1


def test_dois_objetos_distintos_contam_dois():
    a = _box(50, 50)
    b = _box(600, 400)
    state: list = []
    total = 0
    for i in range(3):
        state, newly = update_tracks(state, [a, b], now=2000.0 + i * 0.5)
        total += len(newly)
    assert total == 2


def test_objeto_sai_e_volta_conta_de_novo():
    box = _box(100, 100)
    state: list = []
    total = 0
    # presente por 2 frames -> conta 1
    state, newly = update_tracks(state, [box], now=3000.0)
    total += len(newly)
    state, newly = update_tracks(state, [box], now=3000.5)
    total += len(newly)
    # some por > TRACK_MAX_AGE_SECONDS (sem frames) e volta
    state, newly = update_tracks(state, [box], now=3010.0)
    total += len(newly)
    state, newly = update_tracks(state, [box], now=3010.5)
    total += len(newly)
    assert total == 2


def test_aparicao_de_um_frame_nao_conta():
    box = _box(100, 100)
    state, newly = update_tracks([], [box], now=4000.0)
    assert len(newly) == 0  # hits=1 < TRACK_MIN_HITS


def test_newly_counted_aponta_para_a_deteccao():
    a = _box(50, 50, label="car")
    b = _box(600, 400, category="person", label="person")
    state, _ = update_tracks([], [a, b], now=5000.0)
    state, newly = update_tracks(state, [a, b], now=5000.5)
    assert len(newly) == 2
    # cada track contado referencia o indice da deteccao que o originou
    for t in newly:
        assert "det_index" in t and 0 <= t["det_index"] < 2
        assert t["category"] in ("vehicle", "person")
