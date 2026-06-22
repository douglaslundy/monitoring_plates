"""ByteTrack embutido — associação BYTE de 2 estágios (pura, sem deps pesadas)."""
from app.services.bytetrack_service import associate


def _box(x, y, w=50, h=50, conf=0.9, category="vehicle"):
    return {"category": category, "label": "car", "confidence": conf,
            "bbox": {"bbox_x": x, "bbox_y": y, "bbox_w": w, "bbox_h": h}}


def _track(x, y, w=50, h=50, category="vehicle", now=1000.0):
    return {
        "category": category, "label": "car", "bbox": {"bbox_x": x, "bbox_y": y, "bbox_w": w, "bbox_h": h},
        "vx": None, "vy": None, "last_seen_at": now,
    }


def test_associa_alta_confianca_por_iou():
    tracks = [_track(100, 100)]
    dets = [_box(102, 101, conf=0.9)]  # sobreposto, alta conf
    matched, spawn_block = associate(tracks, dets, now=1000.5)
    assert matched == {0: 0}
    assert spawn_block == set()


def test_deteccao_sem_track_alta_conf_pode_nascer():
    tracks: list = []
    dets = [_box(100, 100, conf=0.9)]
    matched, spawn_block = associate(tracks, dets, now=1000.0)
    assert matched == {}
    assert 0 not in spawn_block  # alta conf -> pode criar track


def test_baixa_confianca_sem_track_nao_nasce():
    """ByteTrack: detecção de BAIXA confiança sem track não inicia track novo."""
    tracks: list = []
    dets = [_box(100, 100, conf=0.25)]  # baixa conf
    matched, spawn_block = associate(tracks, dets, now=1000.0)
    assert matched == {}
    assert 0 in spawn_block  # bloqueada de nascer


def test_baixa_confianca_recupera_track_existente():
    """2º estágio: detecção de baixa conf casa com track existente (recupera)."""
    tracks = [_track(100, 100)]
    dets = [_box(101, 100, conf=0.25)]  # baixa conf, sobreposta ao track
    matched, spawn_block = associate(tracks, dets, now=1000.5)
    assert matched == {0: 0}
    assert spawn_block == set()


def test_dois_objetos_distintos_dois_matches():
    tracks = [_track(50, 50), _track(600, 400)]
    dets = [_box(52, 51), _box(602, 401)]
    matched, _ = associate(tracks, dets, now=1000.5)
    assert matched == {0: 0, 1: 1}


def test_categorias_diferentes_nao_casam():
    tracks = [_track(100, 100, category="vehicle")]
    dets = [_box(100, 100, category="person")]
    matched, _ = associate(tracks, dets, now=1000.5)
    assert matched == {}


# ── Integração via update_tracks(backend="bytetrack") ────────────────────────

from app.services.object_tracker_service import update_tracks


def _count_new(newly):
    return sum(1 for n in newly if n.get("reason") == "new")


def test_bytetrack_objeto_em_movimento_um_track():
    # Rajada (passos pequenos, IoU alto entre frames) -> 1 track, contado 1 vez.
    state: list = []
    total = 0
    for i in range(5):
        det = _box(100 + i * 10, 100, w=50, h=50, conf=0.9)
        state, newly, _, _ = update_tracks(
            state, [det], now=1000.0 + i * 0.15, frame_w=640, frame_h=480, backend="bytetrack"
        )
        total += _count_new(newly)
    assert len(state) == 1
    assert total == 1


def test_bytetrack_tres_veiculos_tres_tracks_R2():
    # R2: vários veículos no MESMO frame -> todos viram track contado (todos vão ao OCR).
    a = _box(50, 50, w=60, h=50, conf=0.9)
    b = _box(300, 60, w=60, h=50, conf=0.9)
    c = _box(540, 380, w=60, h=50, conf=0.9)
    state, newly, det_to_track, _ = update_tracks(
        [], [a, b, c], now=2000.0, frame_w=640, frame_h=480, backend="bytetrack"
    )
    assert _count_new(newly) == 3
    assert len(det_to_track) == 3


def test_bytetrack_baixa_conf_isolada_nao_cria_track():
    # Detecção de baixa confiança sem track não nasce (ByteTrack).
    det = _box(100, 100, conf=0.25)
    state, newly, _, _ = update_tracks([], [det], now=3000.0, frame_w=640, frame_h=480, backend="bytetrack")
    assert state == []
    assert _count_new(newly) == 0
