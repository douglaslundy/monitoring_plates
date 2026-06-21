"""Política de OCR híbrida (pura) — decide a ação por track/frame.

Ações: 'skip' | 'dormant' | 'read' | 'refine'.
"""
from app.services.ocr_policy_service import decide_ocr_action

BASE = dict(min_quality=0.30, refine_margin=0.15, stationary_max_attempts=6)


def test_pending_com_qualidade_baixa_pula():
    a = decide_ocr_action(ocr_state="pending", stationary=False, ocr_attempts=0,
                          quality=0.10, best_quality=0.0, **BASE)
    assert a == "skip"


def test_pending_com_qualidade_boa_le():
    a = decide_ocr_action(ocr_state="pending", stationary=False, ocr_attempts=0,
                          quality=0.50, best_quality=0.0, **BASE)
    assert a == "read"


def test_read_com_frame_pouco_melhor_pula():
    # best=0.50; precisa de >= 0.575 (margem 15%) p/ refinar.
    a = decide_ocr_action(ocr_state="read", stationary=False, ocr_attempts=1,
                          quality=0.55, best_quality=0.50, **BASE)
    assert a == "skip"


def test_read_com_frame_bem_melhor_refina():
    a = decide_ocr_action(ocr_state="read", stationary=False, ocr_attempts=1,
                          quality=0.70, best_quality=0.50, **BASE)
    assert a == "refine"


def test_parado_e_lido_dorme():
    a = decide_ocr_action(ocr_state="read", stationary=True, ocr_attempts=1,
                          quality=0.90, best_quality=0.50, **BASE)
    assert a == "dormant"


def test_parado_sem_ler_apos_muitas_tentativas_dorme():
    # Caminhao parado com placa ilegivel: desiste apos OCR_STATIONARY_MAX_ATTEMPTS.
    a = decide_ocr_action(ocr_state="pending", stationary=True, ocr_attempts=6,
                          quality=0.90, best_quality=0.0, **BASE)
    assert a == "dormant"


def test_parado_sem_ler_ainda_tenta():
    # Parado, ainda dentro do limite de tentativas -> tenta ler.
    a = decide_ocr_action(ocr_state="pending", stationary=True, ocr_attempts=2,
                          quality=0.50, best_quality=0.0, **BASE)
    assert a == "read"


def test_dormant_sempre_pula():
    a = decide_ocr_action(ocr_state="dormant", stationary=False, ocr_attempts=10,
                          quality=0.99, best_quality=0.10, **BASE)
    assert a == "skip"


def test_read_parado_tem_prioridade_sobre_refino():
    # Mesmo com frame melhor, se parou e ja leu, dorme (nao fica refinando parado).
    a = decide_ocr_action(ocr_state="read", stationary=True, ocr_attempts=3,
                          quality=0.99, best_quality=0.20, **BASE)
    assert a == "dormant"
