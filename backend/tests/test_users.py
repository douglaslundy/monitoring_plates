import pytest
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.models.plan import Plan
from app.models.client import Client


@pytest.fixture
def test_plan(db):
    plan = Plan(
        name="Plano Usuários",
        max_cameras=3,
        retention_days=30,
        email_alerts=False,
        realtime_alerts=True,
        price_monthly=99.90,
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@pytest.fixture
def super_admin_user(db):
    user = User(
        email="superadmin@users.com",
        name="Super Admin",
        password_hash=hash_password("Admin@123"),
        role=UserRole.super_admin,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def client_a(db, test_plan):
    c = Client(name="Cliente A", email="a@clientes.com", plan_id=test_plan.id, is_active=True)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture
def client_b(db, test_plan):
    c = Client(name="Cliente B", email="b@clientes.com", plan_id=test_plan.id, is_active=True)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture
def admin_a(db, client_a):
    user = User(
        name="Admin A",
        email="admin@clientea.com",
        password_hash=hash_password("Admin@123"),
        role=UserRole.client_admin,
        client_id=client_a.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def user_b(db, client_b):
    user = User(
        name="User B",
        email="user@clienteb.com",
        password_hash=hash_password("User@123"),
        role=UserRole.client_user,
        client_id=client_b.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_token(http_client, email, password):
    res = http_client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login falhou: {res.json()}"
    return res.json()["access_token"]


def test_super_admin_ve_todos_usuarios(client, super_admin_user, admin_a, user_b):
    token = get_token(client, "superadmin@users.com", "Admin@123")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/users", headers=headers)
    assert res.status_code == 200
    emails = {u["email"] for u in res.json()}
    assert "admin@clientea.com" in emails
    assert "user@clienteb.com" in emails


def test_client_admin_ve_apenas_proprios_usuarios(client, admin_a, user_b):
    token = get_token(client, "admin@clientea.com", "Admin@123")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/users", headers=headers)
    assert res.status_code == 200
    emails = {u["email"] for u in res.json()}
    assert "admin@clientea.com" in emails
    assert "user@clienteb.com" not in emails


def test_client_admin_nao_acessa_usuario_de_outro_cliente(client, admin_a, user_b):
    token = get_token(client, "admin@clientea.com", "Admin@123")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get(f"/api/users/{user_b.id}", headers=headers)
    assert res.status_code == 403


def test_client_user_nao_pode_listar_usuarios(client, user_b):
    token = get_token(client, "user@clienteb.com", "User@123")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/users", headers=headers)
    assert res.status_code == 403


def test_client_admin_cria_usuario_para_proprio_cliente(client, db, client_a, admin_a):
    token = get_token(client, "admin@clientea.com", "Admin@123")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "name": "Novo Usuário",
        "email": "novo@clientea.com",
        "password": "Senha@123",
        "role": "client_user",
        "client_id": str(client_a.id),
        "is_active": True,
    }

    res = client.post("/api/users", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "novo@clientea.com"
    assert data["role"] == "client_user"


def test_client_admin_nao_cria_usuario_para_outro_cliente(client, client_b, admin_a):
    token = get_token(client, "admin@clientea.com", "Admin@123")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "name": "Invasor",
        "email": "invasor@clienteb.com",
        "password": "Senha@123",
        "role": "client_user",
        "client_id": str(client_b.id),
        "is_active": True,
    }

    res = client.post("/api/users", json=payload, headers=headers)
    assert res.status_code == 403
