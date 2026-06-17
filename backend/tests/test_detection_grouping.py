"""T5: agrupamento piloto+moto."""
from types import SimpleNamespace

from app.services.detection_grouping_service import group_riders


def _det(category, label, x, y, w, h):
    return SimpleNamespace(category=category, vehicle_type=label, bbox_x=x, bbox_y=y, bbox_w=w, bbox_h=h)


def test_pessoa_em_cima_da_moto_e_piloto():
    # Pessoa sobreposta à moto (mesma região) -> piloto.
    moto = _det("vehicle", "motorcycle", 100, 200, 120, 100)   # 100..220 x, 200..300 y
    person = _det("person", "person", 120, 130, 60, 150)        # 120..180 x, 130..280 y
    dets = [moto, person]
    pairs = group_riders(dets)
    assert pairs == {1: 0}  # person(idx1) -> moto(idx0)


def test_pessoa_longe_da_moto_nao_e_piloto():
    moto = _det("vehicle", "motorcycle", 100, 200, 120, 100)
    person = _det("person", "person", 500, 100, 60, 150)  # bem longe
    pairs = group_riders([moto, person])
    assert pairs == {}


def test_sem_moto_nao_agrupa():
    car = _det("vehicle", "car", 100, 200, 120, 100)
    person = _det("person", "person", 110, 150, 60, 150)
    assert group_riders([car, person]) == {}


def test_uma_moto_um_piloto():
    moto = _det("vehicle", "motorcycle", 100, 200, 120, 100)
    p1 = _det("person", "person", 120, 130, 60, 150)
    p2 = _det("person", "person", 130, 140, 60, 150)
    pairs = group_riders([moto, p1, p2])
    # apenas um piloto associado à moto
    assert list(pairs.values()) == [0]
    assert len(pairs) == 1
