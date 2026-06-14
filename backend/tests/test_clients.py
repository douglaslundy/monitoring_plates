import pytest
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.models.plan import Plan
from app.models.client import Client


@pytest.fixture
def test_plan(db):
    plan = Plan(
        name="Básico Teste",
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
def super_admin(db):
    user = User(
        email="super@sistema.com",
        name="Super Admin",
        password_hash=hash_password("Admin@123"),
        role=UserRole.super_admin,
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


def test_criar_cliente_com_admin(client, db, super_admin, test_plan):
    token = get_token(client, "super@sistema.com", "Admin@123")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "name": "Empresa Alfa",
        "email": "alfa@empresa.com",
        "plan_id": str(test_plan.id),
        "is_active": True,
        "admin_name": "Admin Alfa",
        "admin_email": "admin@alfa.com",
        "admin_password": "Senha@123",
    }

    res = client.post("/api/clients", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Empresa Alfa"
    assert data["email"] == "alfa@empresa.com"
    assert data["camera_count"] == 0

    admin = db.query(User).filter(User.email == "admin@alfa.com").first()
    assert admin is not None
    assert admin.role == UserRole.client_admin
    assert str(admin.client_id) == data["id"]


def test_listar_clientes_inclui_plano_e_contagem_cameras(client, db, super_admin, test_plan):
    token = get_token(client, "super@sistema.com", "Admin@123")
    headers = {"Authorization": f"Bearer {token}"}

    db_client = Client(
        name="Empresa Lista",
        email="lista@empresa.com",
        plan_id=test_plan.id,
        is_active=True,
    )
    db.add(db_client)
    db.commit()

    res = client.get("/api/clients", headers=headers)
    assert res.status_code == 200
    data = res.json()

    found = next((c for c in data if c["email"] == "lista@empresa.com"), None)
    assert found is not None
    assert found["camera_count"] == 0
    assert found["plan"] is not None
    assert found["plan"]["name"] == "Básico Teste"


def test_desativar_cliente_desativa_usuarios(client, db, super_admin, test_plan):
    token = get_token(client, "super@sistema.com", "Admin@123")
    headers = {"Authorization": f"Bearer {token}"}

    db_client = Client(
        name="Empresa Desativar",
        email="desativar@empresa.com",
        plan_id=test_plan.id,
        is_active=True,
    )
    db.add(db_client)
    db.flush()

    user = User(
        name="Usuário Ativo",
        email="user@desativar.com",
        password_hash=hash_password("Senha@123"),
        role=UserRole.client_user,
        client_id=db_client.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    client_id = db_client.id
    user_id = user.id

    res = client.delete(f"/api/clients/{client_id}", headers=headers)
    assert res.status_code == 204

    refreshed_client = db.query(Client).filter(Client.id == client_id).first()
    assert refreshed_client is None

    refreshed_user = db.query(User).filter(User.id == user_id).first()
    assert refreshed_user is None


def test_acesso_negado_para_client_admin(client, db, test_plan):
    db_client = Client(
        name="Empresa Acesso",
        email="acesso@empresa.com",
        plan_id=test_plan.id,
        is_active=True,
    )
    db.add(db_client)
    db.flush()

    client_admin = User(
        name="Admin Cliente",
        email="admin@acesso.com",
        password_hash=hash_password("Senha@123"),
        role=UserRole.client_admin,
        client_id=db_client.id,
        is_active=True,
    )
    db.add(client_admin)
    db.commit()

    token = get_token(client, "admin@acesso.com", "Senha@123")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/clients", headers=headers)
    assert res.status_code == 403


def test_email_duplicado_retorna_400(client, db, super_admin, test_plan):
    token = get_token(client, "super@sistema.com", "Admin@123")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "name": "Empresa Dup",
        "email": "dup@empresa.com",
        "plan_id": str(test_plan.id),
        "is_active": True,
        "admin_name": "Admin Dup",
        "admin_email": "admin.dup@empresa.com",
        "admin_password": "Senha@123",
    }

    res1 = client.post("/api/clients", json=payload, headers=headers)
    assert res1.status_code == 201

    res2 = client.post("/api/clients", json=payload, headers=headers)
    assert res2.status_code == 400
