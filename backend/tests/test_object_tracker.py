"""T1: rastreador multi-objeto — contagem única robusta + máquina de salvamento.

Config relevante (defaults): TRACK_MIN_HITS=2 (confirma em 2 frames),
TRACK_MAX_AGE_SECONDS=30 (sobrevive a gaps de movimento), gating "objeto inteiro
no frame" (quando há dimensões) e re-save por mudança de classe.
"""
from app.services.object_tracker_service import update_tracks, _fully_in_frame


def _box(x, y, w=50, h=50, category="vehicle", label="car"):
    return {
        "category": category,
        "label": label,
        "confidence": 0.8,
        "bbox": {"bbox_x": x, "bbox_y": y, "bbox_w": w, "bbox_h": h},
    }


def _count_new(newly):
    return sum(1 for n in newly if n.get("reason") == "new")


def test_objeto_parado_conta_uma_vez():
    box = _box(100, 100)
    state: list = []
    total = 0
    for i in range(10):
        state, newly, _, _ = update_tracks(state, [box], now=1000.0 + i * 0.5)
        total += _count_new(newly)
    assert total == 1


def test_dois_objetos_distintos_contam_dois():
    a = _box(50, 50)
    b = _box(600, 400)
    state: list = []
    total = 0
    for i in range(3):
        state, newly, _, _ = update_tracks(state, [a, b], now=2000.0 + i * 0.5)
        total += _count_new(newly)
    assert total == 2


def test_objeto_sai_por_muito_tempo_e_volta_conta_de_novo():
    box = _box(100, 100)
    state: list = []
    total = 0
    state, newly, _, _ = update_tracks(state, [box], now=3000.0)  # hit 1
    total += _count_new(newly)
    state, newly, _, _ = update_tracks(state, [box], now=3000.5)  # hit 2 -> conta
    total += _count_new(newly)
    # some por > TRACK_MAX_AGE_SECONDS (30s) e volta -> novo track -> conta de novo
    state, newly, _, _ = update_tracks(state, [box], now=3040.0)  # hit 1 (novo)
    total += _count_new(newly)
    state, newly, _, _ = update_tracks(state, [box], now=3040.5)  # hit 2 -> conta
    total += _count_new(newly)
    assert total == 2


def test_conta_uma_vez_e_nao_recontabiliza():
    # Inteiro no frame (dims None -> assume inteiro): conta ao confirmar e não
    # reconta enquanto o track permanece.
    box = _box(100, 100)
    state, newly, _, _ = update_tracks([], [box], now=4000.0)
    assert _count_new(newly) == 1
    state, newly, _, _ = update_tracks(state, [box], now=4000.5)
    assert _count_new(newly) == 0
    state, newly, _, _ = update_tracks(state, [box], now=4001.0)
    assert _count_new(newly) == 0


def test_objeto_em_movimento_sem_iou_segue_mesmo_track():
    # Move bastante (IoU=0) mas centro próximo -> mesmo track -> conta 1 vez.
    state: list = []
    total = 0
    for i in range(5):
        det = _box(100 + i * 60, 100)
        state, newly, _, _ = update_tracks(state, [det], now=5000.0 + i * 0.5)
        total += _count_new(newly)
    assert len(state) == 1
    assert total == 1


def test_det_to_track_referencia_mutavel():
    a = _box(50, 50, label="car")
    b = _box(600, 400, category="person", label="person")
    state, newly, det_to_track, _ = update_tracks([], [a, b], now=6000.0)
    assert _count_new(newly) == 2
    assert set(det_to_track.keys()) == {0, 1}
    det_to_track[0]["occurrence_id"] = "abc"
    assert any(t.get("occurrence_id") == "abc" for t in state)
    for t in newly:
        assert "det_index" in t and 0 <= t["det_index"] < 2


# ── Gating "objeto inteiro no frame" ─────────────────────────────────────────


def test_fully_in_frame_helper():
    assert _fully_in_frame({"bbox_x": 100, "bbox_y": 100, "bbox_w": 50, "bbox_h": 50}, 640, 480)
    # encostado na borda esquerda
    assert not _fully_in_frame({"bbox_x": 0, "bbox_y": 100, "bbox_w": 50, "bbox_h": 50}, 640, 480)
    # encostado na borda direita
    assert not _fully_in_frame({"bbox_x": 600, "bbox_y": 100, "bbox_w": 50, "bbox_h": 50}, 640, 480)
    # sem dimensões -> assume inteiro
    assert _fully_in_frame({"bbox_x": 0, "bbox_y": 0, "bbox_w": 50, "bbox_h": 50}, None, None)


def test_nao_salva_enquanto_objeto_cortado_na_borda():
    # Objeto confirmado mas entrando pela borda (não inteiro) -> não conta/salva.
    state: list = []
    total = 0
    for i in range(2):
        det = _box(0, 100)  # encostado na borda esquerda
        state, newly, _, _ = update_tracks(state, [det], now=7000.0 + i * 0.5, frame_w=640, frame_h=480)
        total += _count_new(newly)
    assert total == 0
    # Avança um pouco (segue o mesmo track) e agora aparece inteiro -> conta 1x.
    state, newly, _, _ = update_tracks(state, [_box(40, 100)], now=7001.5, frame_w=640, frame_h=480)
    assert _count_new(newly) == 1


def test_force_save_apos_n_hits_mesmo_cortado():
    # Objeto SEMPRE cortado na borda: após TRACK_FORCE_SAVE_HITS (4) salva mesmo assim.
    state: list = []
    total = 0
    for i in range(4):
        det = _box(0, 100)
        state, newly, _, _ = update_tracks(state, [det], now=8000.0 + i * 0.5, frame_w=640, frame_h=480)
        total += _count_new(newly)
    assert total == 1


def test_resave_so_quando_classe_muda_de_forma_estavel():
    # Conta como car; só re-salva quando truck vira maioria com MARGEM (>=3 votos),
    # nao a cada flicker. car:1 fixo; truck precisa chegar a 4 (margem 3).
    state: list = []
    state, newly, _, _ = update_tracks(state, [_box(100, 100, label="car")], now=9000.0, frame_w=640, frame_h=480)
    assert _count_new(newly) == 1  # contou como car (car:1)
    # 3 frames de truck: empate/maioria fraca -> NAO re-salva (margem < 3)
    for i, t in enumerate((9000.5, 9001.0, 9001.5)):
        state, newly, _, _ = update_tracks(state, [_box(100, 100, label="truck")], now=t, frame_w=640, frame_h=480)
        assert newly == [], f"flicker nao deve re-salvar (frame {i})"
    # 4o truck -> truck:4 vs car:1 (margem 3) -> re-save
    state, newly, _, _ = update_tracks(state, [_box(100, 100, label="truck")], now=9002.0, frame_w=640, frame_h=480)
    assert [n.get("reason") for n in newly] == ["class_change"]
    assert _count_new(newly) == 0  # não conta de novo


def test_velocidade_mantem_track_apos_frame_lento():
    # Estabelece velocidade com um passo curto; depois um GAP longo (worker lento)
    # cujo deslocamento (180px) superaria o gate (2.5*60=150) SEM previsao. A
    # previsao por velocidade preve a posicao e mantem 1 unico track.
    state: list = []
    total = 0
    state, newly, _, _ = update_tracks(state, [_box(100, 300, w=60, h=60)], now=20000.0, frame_w=2000, frame_h=600)
    total += _count_new(newly)  # conta (1)
    # passo curto (60px em 0.5s) -> estabelece vx=120 px/s
    state, newly, _, _ = update_tracks(state, [_box(160, 300, w=60, h=60)], now=20000.5, frame_w=2000, frame_h=600)
    total += _count_new(newly)
    assert len(state) == 1
    # gap de 1.5s: objeto a 120px/s anda 180px (>150 gate). So associa por previsao.
    state, newly, _, _ = update_tracks(state, [_box(340, 300, w=60, h=60)], now=20002.0, frame_w=2000, frame_h=600)
    total += _count_new(newly)
    assert len(state) == 1   # continua 1 track (previsao manteve a associacao)
    assert total == 1        # contado uma unica vez


# ── Voto temporal de classe (T4) ─────────────────────────────────────────────


def test_voto_corrige_erro_pontual_cross_category():
    # Mesmo objeto (mesma caixa) ora "person" ora "bear": cross-category associa,
    # a maioria (person) vence e o track NÃO vira dois objetos.
    person = _box(200, 150, w=60, h=120, category="person", label="person")
    bear = _box(200, 150, w=60, h=120, category="animal", label="bear")
    state: list = []
    state, _, _, _ = update_tracks(state, [person], now=14000.0, frame_w=640, frame_h=480)
    state, _, _, _ = update_tracks(state, [bear], now=14000.5, frame_w=640, frame_h=480)
    state, _, _, _ = update_tracks(state, [person], now=14001.0, frame_w=640, frame_h=480)
    assert len(state) == 1
    assert state[0]["category"] == "person"
    assert state[0]["label"] == "person"


def test_cross_category_nao_funde_objetos_distantes():
    # Pessoa e cão em posições diferentes (IoU baixo) NÃO se fundem.
    person = _box(50, 50, category="person", label="person")
    dog = _box(500, 400, category="animal", label="dog")
    state: list = []
    state, _, _, _ = update_tracks(state, [person, dog], now=15000.0, frame_w=640, frame_h=480)
    assert len(state) == 2


def test_parado_com_gap_curto_de_movimento_nao_reconta():
    # Carro parado: gaps de movimento < max_age não recontam (mesma posição).
    box = _box(200, 150)
    state: list = []
    total = 0
    state, newly, _, _ = update_tracks(state, [box], now=10000.0, frame_w=640, frame_h=480)
    total += _count_new(newly)
    state, newly, _, _ = update_tracks(state, [box], now=10000.5, frame_w=640, frame_h=480)
    total += _count_new(newly)  # contou (1)
    # gap de 20s (< 30s max_age) sem frames, depois reaparece na mesma posição
    state, newly, _, _ = update_tracks(state, [box], now=10020.5, frame_w=640, frame_h=480)
    total += _count_new(newly)
    assert total == 1


def test_carro_parado_nao_reconta_quando_objeto_passa():
    """T3: um carro parado não é re-gravado quando uma pessoa passa pela cena."""
    car = _box(300, 250, w=120, h=90, category="vehicle", label="car")
    state: list = []
    car_total = 0
    person_total = 0
    now = 11000.0
    # Carro parado é confirmado/estacionário ao longo de alguns frames.
    for _ in range(4):
        state, newly, _, _ = update_tracks(state, [car], now=now, frame_w=640, frame_h=480)
        car_total += _count_new(newly)
        now += 0.5
    # Uma pessoa atravessa a cena (frames com movimento contêm carro + pessoa).
    for i in range(5):
        person = _box(50 + i * 80, 260, w=40, h=90, category="person", label="person")
        state, newly, _, _ = update_tracks(state, [car, person], now=now, frame_w=640, frame_h=480)
        car_total += sum(1 for n in newly if n["category"] == "vehicle" and n.get("reason") == "new")
        person_total += sum(1 for n in newly if n["category"] == "person" and n.get("reason") == "new")
        now += 0.5
    assert car_total == 1  # carro contado/salvo só uma vez
    assert person_total == 1  # pessoa contada uma vez


def test_carro_parado_estacionario_sobrevive_gap_longo():
    """T3: carro parado vira estacionário e sobrevive a um gap > max_age (30s)."""
    car = _box(300, 250, w=120, h=90)
    state: list = []
    total = 0
    now = 12000.0
    for _ in range(4):  # confirma e marca estacionário
        state, newly, _, _ = update_tracks(state, [car], now=now, frame_w=640, frame_h=480)
        total += _count_new(newly)
        now += 0.5
    assert any(t.get("stationary") for t in state)
    # gap de 60s (> 30s max_age normal) e reaparece: NÃO reconta (estacionário).
    state, newly, _, _ = update_tracks(state, [car], now=now + 60.0, frame_w=640, frame_h=480)
    total += _count_new(newly)
    assert total == 1


def test_veiculo_que_passou_e_saiu_nao_e_estacionario():
    """Um veículo em movimento que sai expira no max_age normal (não estacionário)."""
    state: list = []
    now = 13000.0
    for i in range(4):  # atravessa a cena (centro se desloca muito)
        det = _box(50 + i * 120, 250, w=120, h=90)
        state, _, _, _ = update_tracks(state, [det], now=now, frame_w=640, frame_h=480)
        now += 0.5
    assert all(not t.get("stationary") for t in state)
