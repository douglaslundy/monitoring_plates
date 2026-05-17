import pytest
from datetime import timedelta
from app.core.security import hash_password, create_access_token
from app.models.user import User, UserRole


@pytest.fixture
def admin_user(db):
    user = User(
        email="admin@sistema.com",
        name="Administrador",
        password_hash=hash_password("Admin@123"),
        role=UserRole.super_admin,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def regular_user(db):
    user = User(
        email="user@cliente.com",
        name="Usuário Cliente",
        password_hash=hash_password("User@123"),
        role=UserRole.client_user,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_login_com_credenciais_corretas(client, admin_user):
    res = client.post(
        "/api/auth/login",
        json={"email": "admin@sistema.com", "password": "Admin@123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "admin@sistema.com"
    assert data["user"]["role"] == "super_admin"


def test_login_com_senha_errada(client, admin_user):
    res = client.post(
        "/api/auth/login",
        json={"email": "admin@sistema.com", "password": "senhaerrada"},
    )
    assert res.status_code == 401


def test_me_sem_token(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_me_com_token_valido(client, admin_user):
    login = client.post(
        "/api/auth/login",
        json={"email": "admin@sistema.com", "password": "Admin@123"},
    )
    token = login.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    data = me.json()
    assert data["email"] == "admin@sistema.com"
    assert data["role"] == "super_admin"


def test_rota_super_admin_com_token_client_user(client, regular_user):
    login = client.post(
        "/api/auth/login",
        json={"email": "user@cliente.com", "password": "User@123"},
    )
    token = login.json()["access_token"]

    res = client.get("/api/clients", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_login_usuario_inativo_retorna_400(client, db):
    inactive = User(
        email="inactive@test.com",
        name="Inativo",
        password_hash=hash_password("Senha@123"),
        role=UserRole.client_user,
        is_active=False,
    )
    db.add(inactive)
    db.commit()

    res = client.post(
        "/api/auth/login",
        json={"email": "inactive@test.com", "password": "Senha@123"},
    )
    assert res.status_code == 400


def test_token_expirado_retorna_401(client, admin_user):
    expired_token = create_access_token(
        {"sub": str(admin_user.id), "role": admin_user.role},
        expires_delta=timedelta(seconds=-1),
    )
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401


def test_change_password_sucesso(client, admin_user):
    login = client.post(
        "/api/auth/login",
        json={"email": "admin@sistema.com", "password": "Admin@123"},
    )
    token = login.json()["access_token"]

    res = client.post(
        "/api/auth/change-password",
        json={"current_password": "Admin@123", "new_password": "NovoAdmin@456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

    # Confirm new password works
    login2 = client.post(
        "/api/auth/login",
        json={"email": "admin@sistema.com", "password": "NovoAdmin@456"},
    )
    assert login2.status_code == 200


def test_change_password_senha_atual_errada(client, admin_user):
    login = client.post(
        "/api/auth/login",
        json={"email": "admin@sistema.com", "password": "Admin@123"},
    )
    token = login.json()["access_token"]

    res = client.post(
        "/api/auth/change-password",
        json={"current_password": "senhaerrada", "new_password": "NovoAdmin@456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
