"""Tests for monitored-plates endpoint (Task 23)."""
import pytest

from app.core.security import hash_password
from app.models.monitored_plate import MonitoredPlate
from app.models.user import User, UserRole


# ── Auth helpers ──────────────────────────────────────────────────────────────

def login(client, email: str, password: str = "Admin@123") -> str:
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Task 23: clear error when client_id is missing ────────────────────────────

def test_create_plate_client_user_sem_cliente_retorna_400(client, db, basic_plan):
    """client_user with no linked client must get 400 with clear message, not 500."""
    orphan = User(
        email="orphan@test.com",
        name="Orphan",
        password_hash=hash_password("Admin@123"),
        role=UserRole.client_user,
        client_id=None,
        is_active=True,
    )
    db.add(orphan)
    db.commit()
    db.refresh(orphan)

    token = login(client, "orphan@test.com")
    res = client.post(
        "/api/monitored-plates",
        json={"plate": "ABC1234"},
        headers=auth(token),
    )
    assert res.status_code == 400, res.text
    data = res.json()
    assert "detail" in data
    assert "não está vinculado" in data["detail"]


def test_create_plate_super_admin_sem_client_id_retorna_400(client, db, super_admin_user):
    """super_admin without client_id in payload must get 400 with clear message."""
    token = login(client, "sa@sistema.com")
    res = client.post(
        "/api/monitored-plates",
        json={"plate": "ABC1234"},
        headers=auth(token),
    )
    assert res.status_code == 400, res.text
    data = res.json()
    assert "detail" in data
    assert "client_id" in data["detail"].lower()


def test_create_plate_super_admin_com_client_id_cria_com_sucesso(
    client, db, super_admin_user, client_a
):
    """super_admin WITH client_id in payload must create the plate (201)."""
    token = login(client, "sa@sistema.com")
    res = client.post(
        "/api/monitored-plates",
        json={"plate": "ABC1234", "client_id": str(client_a.id)},
        headers=auth(token),
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["plate"] == "ABC1234"
    assert data["client_id"] == str(client_a.id)


def test_create_plate_client_user_com_cliente_cria_com_sucesso(
    client, db, user_a, client_a
):
    """client_user with linked client must create successfully (201)."""
    token = login(client, "user@client-a.com")
    res = client.post(
        "/api/monitored-plates",
        json={"plate": "XYZ9876"},
        headers=auth(token),
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["plate"] == "XYZ9876"
    assert data["client_id"] == str(client_a.id)
