"""
Etapa 8 — Testes de isolamento multi-tenant.

Verifica que um cliente nunca pode acessar dados de outro cliente.
Usa fixtures compartilhadas do conftest.py.
"""

import pytest
from datetime import datetime, timezone

from app.core.security import create_access_token
from app.models.occurrence import Occurrence
from app.models.user import User


def _tok(user: User) -> str:
    return create_access_token({"sub": str(user.id), "role": user.role})


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {_tok(user)}"}


def _occ(db, camera, plate: str) -> Occurrence:
    occ = Occurrence(
        camera_id=camera.id,
        plate=plate,
        confidence=0.95,
        image_path="cameras/x/img.jpg",
        detected_at=datetime.now(timezone.utc),
    )
    db.add(occ)
    db.commit()
    db.refresh(occ)
    return occ


# ── Câmeras ───────────────────────────────────────────────────────────────────

def test_admin_a_nao_ve_camera_de_outro_cliente(
    client, db, admin_a, camera_rtsp_a, camera_b
):
    """admin_a cannot GET a camera belonging to client_b."""
    res = client.get(f"/api/cameras/{camera_b.id}", headers=_auth(admin_a))
    assert res.status_code == 403


def test_admin_a_nao_deleta_camera_de_outro_cliente(
    client, db, admin_a, camera_rtsp_a, camera_b
):
    """admin_a cannot DELETE a camera belonging to client_b."""
    res = client.delete(f"/api/cameras/{camera_b.id}", headers=_auth(admin_a))
    assert res.status_code == 403


def test_lista_cameras_retorna_apenas_do_proprio_cliente(
    client, db, user_a, camera_rtsp_a, camera_agent_a, camera_b
):
    """user_a list returns only client_a's cameras, not camera_b."""
    res = client.get("/api/cameras", headers=_auth(user_a))
    assert res.status_code == 200
    ids = {c["id"] for c in res.json()}
    assert str(camera_rtsp_a.id) in ids
    assert str(camera_agent_a.id) in ids
    assert str(camera_b.id) not in ids


# ── Usuários ──────────────────────────────────────────────────────────────────

def test_admin_a_nao_ve_usuario_de_outro_cliente(
    client, db, admin_a, user_b
):
    """admin_a cannot GET user_b who belongs to client_b."""
    res = client.get(f"/api/users/{user_b.id}", headers=_auth(admin_a))
    assert res.status_code == 403


def test_admin_a_nao_edita_usuario_de_outro_cliente(
    client, db, admin_a, user_b
):
    """admin_a cannot PATCH user_b who belongs to client_b."""
    res = client.patch(
        f"/api/users/{user_b.id}",
        json={"name": "Invasor"},
        headers=_auth(admin_a),
    )
    assert res.status_code == 403


def test_admin_a_nao_ve_usuario_b_na_listagem(
    client, db, admin_a, user_a, user_b
):
    """admin_a's user list does not include user_b."""
    res = client.get("/api/users", headers=_auth(admin_a))
    assert res.status_code == 200
    emails = {u["email"] for u in res.json()}
    assert user_a.email in emails
    assert user_b.email not in emails


# ── Ocorrências ───────────────────────────────────────────────────────────────

def test_admin_a_nao_ve_ocorrencia_de_outro_cliente(
    client, db, admin_a, camera_b
):
    """admin_a cannot GET an occurrence from camera_b (client_b)."""
    occ = _occ(db, camera_b, "BBB2222")
    res = client.get(f"/api/occurrences/{occ.id}", headers=_auth(admin_a))
    assert res.status_code == 403


def test_busca_ocorrencias_isolada_por_cliente(
    client, db, user_a, camera_rtsp_a, camera_b
):
    """user_a search only returns occurrences from client_a's cameras."""
    _occ(db, camera_rtsp_a, "AAA1111")
    _occ(db, camera_b, "BBB2222")

    res = client.post(
        "/api/occurrences/search",
        json={"plate": ""},
        headers=_auth(user_a),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["plate"] == "AAA1111"


def test_csv_export_isolado_por_cliente(
    client, db, user_a, camera_rtsp_a, camera_b
):
    """CSV export for user_a only contains client_a's occurrences."""
    _occ(db, camera_rtsp_a, "AAA1111")
    _occ(db, camera_b, "BBB2222")

    res = client.get("/api/occurrences/export", headers=_auth(user_a))
    assert res.status_code == 200
    assert "AAA1111" in res.text
    assert "BBB2222" not in res.text


# ── Admin cria usuário apenas no próprio cliente ───────────────────────────────

def test_admin_a_nao_cria_usuario_em_cliente_b(
    client, db, admin_a, client_b
):
    """admin_a cannot create a user assigned to client_b."""
    res = client.post(
        "/api/users",
        json={
            "name": "Invasor",
            "email": "invasor@clienteb.com",
            "password": "Senha@123",
            "role": "client_user",
            "client_id": str(client_b.id),
            "is_active": True,
        },
        headers=_auth(admin_a),
    )
    assert res.status_code == 403
