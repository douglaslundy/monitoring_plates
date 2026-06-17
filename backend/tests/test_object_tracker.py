"""Task 2.1 / T1: rastreador multi-objeto (IoU+distância, count-once)."""
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
        state, newly, _ = update_tracks(state, [box], now=1000.0 + i * 0.5)
        total += len(newly)
    assert total == 1


def test_dois_objetos_distintos_contam_dois():
    a = _box(50, 50)
    b = _box(600, 400)
    state: list = []
    total = 0
    for i in range(3):
        state, newly, _ = update_tracks(state, [a, b], now=2000.0 + i * 0.5)
        total += len(newly)
    assert total == 2


def test_objeto_sai_e_volta_conta_de_novo():
    box = _box(100, 100)
    state: list = []
    total = 0
    # presente -> conta 1
    state, newly, _ = update_tracks(state, [box], now=3000.0)
    total += len(newly)
    state, newly, _ = update_tracks(state, [box], now=3000.5)
    total += len(newly)
    # some por > TRACK_MAX_AGE_SECONDS (sem frames) e volta -> conta de novo
    state, newly, _ = update_tracks(state, [box], now=3012.0)
    total += len(newly)
    state, newly, _ = update_tracks(state, [box], now=3012.5)
    total += len(newly)
    assert total == 2


def test_um_frame_ja_conta_e_nao_recontabiliza():
    # TRACK_MIN_HITS=1: conta ao aparecer; o track impede recontagem enquanto
    # o objeto permanece (mesmo que o bbox mude um pouco entre frames).
    box = _box(100, 100)
    state, newly, _ = update_tracks([], [box], now=4000.0)
    assert len(newly) == 1
    state, newly2, _ = update_tracks(state, [box], now=4000.5)
    assert len(newly2) == 0
    state, newly3, _ = update_tracks(state, [box], now=4001.0)
    assert len(newly3) == 0


def test_objeto_em_movimento_sem_iou_segue_mesmo_track():
    # Veículo que se move bastante entre frames (IoU=0) mas com centro próximo
    # deve manter o MESMO track pela associação por distância -> conta 1 vez.
    state: list = []
    total = 0
    # passos de 60px (box 50px): IoU=0 entre frames consecutivos
    for i in range(5):
        det = _box(100 + i * 60, 100)
        state, newly, _ = update_tracks(state, [det], now=5000.0 + i * 0.5)
        total += len(newly)
    assert len(state) == 1
    assert total == 1


def test_det_to_track_referencia_mutavel():
    a = _box(50, 50, label="car")
    b = _box(600, 400, category="person", label="person")
    state, newly, det_to_track = update_tracks([], [a, b], now=6000.0)
    assert len(newly) == 2
    assert set(det_to_track.keys()) == {0, 1}
    # mutação no mapa reflete no estado (amarração de placa pelo pipeline)
    det_to_track[0]["occurrence_id"] = "abc"
    assert any(t.get("occurrence_id") == "abc" for t in state)
    for t in newly:
        assert "det_index" in t and 0 <= t["det_index"] < 2
