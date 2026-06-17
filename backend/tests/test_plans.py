"""
Etapa 8 — Testes de planos (plans CRUD).
"""

import pytest
from app.core.security import hash_password, create_access_token
from app.models.user import User, UserRole
from app.models.plan import Plan


@pytest.fixture
def sa_user(db):
    user = User(
        email="sa@planos.com",
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
def regular_plan(db):
    plan = Plan(
        name="Plano Teste",
        max_cameras=5,
        retention_days=60,
        email_alerts=True,
        realtime_alerts=True,
        price_monthly=199.90,
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def _tok(user: User) -> str:
    return create_access_token({"sub": str(user.id), "role": user.role})


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {_tok(user)}"}


def test_listar_planos(client, sa_user, regular_plan):
    """GET /api/plans/ returns active plans."""
    res = client.get("/api/plans/", headers=_auth(sa_user))
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    names = [p["name"] for p in data]
    assert "Plano Teste" in names


def test_criar_plano_super_admin(client, sa_user):
    """Super admin can create a plan."""
    res = client.post(
        "/api/plans/",
        json={
            "name": "Novo Plano",
            "max_cameras": 10,
            "retention_days": 90,
            "email_alerts": True,
            "realtime_alerts": True,
            "price_monthly": 299.90,
            "is_active": True,
        },
        headers=_auth(sa_user),
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Novo Plano"
    assert data["max_cameras"] == 10
    assert data["client_count"] == 0


def test_atualizar_plano(client, sa_user, regular_plan):
    """Super admin can update a plan."""
    res = client.patch(
        f"/api/plans/{regular_plan.id}",
        json={"name": "Plano Atualizado"},
        headers=_auth(sa_user),
    )
    assert res.status_code == 200
    assert res.json()["name"] == "Plano Atualizado"


def test_deletar_plano(client, db, sa_user, regular_plan):
    """Super admin can delete a plan."""
    res = client.delete(f"/api/plans/{regular_plan.id}", headers=_auth(sa_user))
    assert res.status_code == 204

    from app.models.plan import Plan
    assert db.query(Plan).filter(Plan.id == regular_plan.id).first() is None


def test_deletar_plano_em_uso_bloqueado(client, db, sa_user, regular_plan):
    """Plano com cliente vinculado não pode ser excluído (409)."""
    from app.models.client import Client

    cli = Client(name="Cli", email="cli@x.com", plan_id=regular_plan.id, is_active=True)
    db.add(cli)
    db.commit()

    res = client.delete(f"/api/plans/{regular_plan.id}", headers=_auth(sa_user))
    assert res.status_code == 409
    from app.models.plan import Plan
    assert db.query(Plan).filter(Plan.id == regular_plan.id).first() is not None


def test_listar_inclui_inativos_quando_pedido(client, db, sa_user):
    """include_inactive=true retorna também planos inativos (gestão)."""
    from app.models.plan import Plan

    inativo = Plan(
        name="Plano Inativo",
        max_cameras=1,
        retention_days=10,
        email_alerts=False,
        realtime_alerts=False,
        price_monthly=10,
        is_active=False,
    )
    db.add(inativo)
    db.commit()

    ativos = client.get("/api/plans/", headers=_auth(sa_user)).json()
    assert "Plano Inativo" not in [p["name"] for p in ativos]

    todos = client.get("/api/plans/?include_inactive=true", headers=_auth(sa_user)).json()
    assert "Plano Inativo" in [p["name"] for p in todos]


def test_atualizar_plano_para_ilimitado(client, db, sa_user, regular_plan):
    """PATCH com max_cameras/retention_days null torna o plano ilimitado."""
    res = client.patch(
        f"/api/plans/{regular_plan.id}",
        json={"max_cameras": None, "retention_days": None},
        headers=_auth(sa_user),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["max_cameras"] is None
    assert data["retention_days"] is None


def test_criar_plano_sem_permissao(client, db):
    """client_user cannot create a plan (requires super_admin)."""
    user = User(
        email="cu@test.com",
        name="User",
        password_hash=hash_password("Pwd@123"),
        role=UserRole.client_user,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    res = client.post(
        "/api/plans/",
        json={"name": "Plano Indevido", "max_cameras": 1, "retention_days": 7,
              "email_alerts": False, "realtime_alerts": False, "price_monthly": 0},
        headers=_auth(user),
    )
    assert res.status_code == 403


def test_listar_alertas_enviados(client, db, sa_user):
    """GET /api/alerts/ returns alerts list (empty when no alerts)."""
    res = client.get("/api/alerts/", headers=_auth(sa_user))
    assert res.status_code == 200
    assert isinstance(res.json(), list)
