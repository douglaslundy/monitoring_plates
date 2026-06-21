"""
Etapa 6 — Testes de busca de ocorrências, alertas e exportação CSV.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from app.core.security import hash_password, create_access_token
from app.models.plan import Plan
from app.models.client import Client
from app.models.camera import Camera, ConnectionType
from app.models.user import User, UserRole
from app.models.occurrence import Occurrence
from app.models.monitored_plate import MonitoredPlate
from app.models.alert_sent import AlertSent, AlertChannel


# ── Shared fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def setup_tenant(db):
    """Creates Plan → Client → Camera → two users (admin + regular)."""
    plan = Plan(
        name="Profissional",
        max_cameras=10,
        retention_days=90,
        email_alerts=True,
        realtime_alerts=True,
        price_monthly=99,
    )
    db.add(plan)
    db.flush()

    tenant = Client(name="Cliente Alfa", email="alfa@test.com", plan_id=plan.id)
    db.add(tenant)
    db.flush()

    camera = Camera(
        client_id=tenant.id,
        name="Câmera Principal",
        location="Entrada",
        connection_type=ConnectionType.agent,
        agent_token="tok-alfa-01",
    )
    db.add(camera)
    db.flush()

    admin = User(
        name="Admin Alfa",
        email="admin@alfa.com",
        password_hash=hash_password("Admin@123"),
        role=UserRole.client_admin,
        client_id=tenant.id,
        is_active=True,
    )
    regular = User(
        name="User Alfa",
        email="user@alfa.com",
        password_hash=hash_password("Admin@123"),
        role=UserRole.client_user,
        client_id=tenant.id,
        is_active=True,
    )
    db.add_all([admin, regular])
    db.commit()
    db.refresh(camera)
    return plan, tenant, camera, admin, regular


@pytest.fixture
def setup_two_tenants(db):
    """Two separate tenants, each with one camera and one user."""
    plan = Plan(
        name="Basico",
        max_cameras=3,
        retention_days=30,
        email_alerts=False,
        realtime_alerts=False,
        price_monthly=0,
    )
    db.add(plan)
    db.flush()

    tenant_a = Client(name="Cliente A", email="a@test.com", plan_id=plan.id)
    tenant_b = Client(name="Cliente B", email="b@test.com", plan_id=plan.id)
    db.add_all([tenant_a, tenant_b])
    db.flush()

    cam_a = Camera(client_id=tenant_a.id, name="Cam A", connection_type=ConnectionType.agent)
    cam_b = Camera(client_id=tenant_b.id, name="Cam B", connection_type=ConnectionType.agent)
    db.add_all([cam_a, cam_b])
    db.flush()

    user_a = User(
        name="User A",
        email="ua@test.com",
        password_hash=hash_password("Admin@123"),
        role=UserRole.client_user,
        client_id=tenant_a.id,
        is_active=True,
    )
    user_b = User(
        name="User B",
        email="ub@test.com",
        password_hash=hash_password("Admin@123"),
        role=UserRole.client_user,
        client_id=tenant_b.id,
        is_active=True,
    )
    db.add_all([user_a, user_b])
    db.commit()
    db.refresh(cam_a)
    db.refresh(cam_b)
    return plan, tenant_a, cam_a, user_a, tenant_b, cam_b, user_b


def _tok(user: User) -> str:
    return create_access_token({"sub": str(user.id), "role": user.role})


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _occ(db, camera: Camera, plate: str, confidence: float = 0.95) -> Occurrence:
    occ = Occurrence(
        camera_id=camera.id,
        plate=plate,
        confidence=confidence,
        image_path="cameras/x/img.jpg",
        detected_at=datetime.now(timezone.utc),
    )
    db.add(occ)
    db.commit()
    db.refresh(occ)
    return occ


# ── Busca parcial ──────────────────────────────────────────────────────────────


def test_busca_parcial_retorna_matches(client, db, setup_tenant):
    plan, tenant, camera, admin, _ = setup_tenant
    _occ(db, camera, "ABC1234")
    _occ(db, camera, "ABC5678")
    _occ(db, camera, "XYZ9W87")

    res = client.post(
        "/api/occurrences/search",
        json={"plate": "ABC"},
        headers=_auth(_tok(admin)),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    plates = {item["plate"] for item in data["items"]}
    assert plates == {"ABC1234", "ABC5678"}


def test_busca_placa_completa(client, db, setup_tenant):
    plan, tenant, camera, admin, _ = setup_tenant
    _occ(db, camera, "ABC1234")
    _occ(db, camera, "ABC5678")

    res = client.post(
        "/api/occurrences/search",
        json={"plate": "ABC1234"},
        headers=_auth(_tok(admin)),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["plate"] == "ABC1234"


def test_busca_sem_filtro_retorna_tudo(client, db, setup_tenant):
    plan, tenant, camera, admin, _ = setup_tenant
    for p in ["ABC1234", "XYZ9W87", "DEF5678"]:
        _occ(db, camera, p)

    res = client.post(
        "/api/occurrences/search",
        json={"plate": ""},
        headers=_auth(_tok(admin)),
    )
    assert res.status_code == 200
    assert res.json()["total"] == 3


# ── Isolamento multi-tenant ────────────────────────────────────────────────────


def test_cliente_so_ve_proprias_ocorrencias(client, db, setup_two_tenants):
    _, tenant_a, cam_a, user_a, _, cam_b, user_b = setup_two_tenants
    _occ(db, cam_a, "AAA1111")
    _occ(db, cam_b, "BBB2222")

    res_a = client.post(
        "/api/occurrences/search",
        json={"plate": ""},
        headers=_auth(_tok(user_a)),
    )
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a["total"] == 1
    assert data_a["items"][0]["plate"] == "AAA1111"

    res_b = client.post(
        "/api/occurrences/search",
        json={"plate": ""},
        headers=_auth(_tok(user_b)),
    )
    assert res_b.json()["total"] == 1
    assert res_b.json()["items"][0]["plate"] == "BBB2222"


def test_super_admin_ve_todas_ocorrencias(client, db, setup_two_tenants):
    _, tenant_a, cam_a, _, _, cam_b, _ = setup_two_tenants
    _occ(db, cam_a, "AAA1111")
    _occ(db, cam_b, "BBB2222")

    super_admin = User(
        name="SA",
        email="sa@sistema.com",
        password_hash=hash_password("Admin@123"),
        role=UserRole.super_admin,
        is_active=True,
    )
    db.add(super_admin)
    db.commit()
    db.refresh(super_admin)

    res = client.post(
        "/api/occurrences/search",
        json={"plate": ""},
        headers=_auth(_tok(super_admin)),
    )
    assert res.json()["total"] == 2


# ── Alerta ao detectar placa monitorada ───────────────────────────────────────


def test_alerta_gerado_placa_monitorada(db, setup_tenant):
    plan, tenant, camera, admin, _ = setup_tenant

    mp = MonitoredPlate(
        client_id=tenant.id,
        plate="ABC1234",
        description="Suspeito",
        alert_email="alerta@test.com",
        is_active=True,
    )
    db.add(mp)
    db.flush()

    occ = _occ(db, camera, "ABC1234")

    # Patch the name as it appears in alert_service's namespace (not email_service)
    with (
        patch("app.services.alert_service.send_plate_alert", return_value=True),
        patch("app.services.alert_service._publish_ws_alert"),
    ):
        from app.services.alert_service import process_alerts
        process_alerts(str(occ.id), db)

    alert = (
        db.query(AlertSent)
        .filter(AlertSent.occurrence_id == occ.id, AlertSent.channel == AlertChannel.email)
        .first()
    )
    assert alert is not None
    assert alert.channel == AlertChannel.email
    assert alert.status == "sent"


def test_alerta_nao_duplicado(db, setup_tenant):
    """Two calls to process_alerts não duplicam AlertSent por canal (e-mail e
    websocket, pois o plano tem email_alerts e realtime_alerts ativos)."""
    plan, tenant, camera, admin, _ = setup_tenant

    mp = MonitoredPlate(
        client_id=tenant.id,
        plate="ABC1234",
        alert_email="alerta@test.com",
        is_active=True,
    )
    db.add(mp)
    db.flush()

    occ = _occ(db, camera, "ABC1234")

    with (
        patch("app.services.alert_service.send_plate_alert", return_value=True),
        patch("app.services.alert_service._publish_ws_alert"),
    ):
        from app.services.alert_service import process_alerts
        process_alerts(str(occ.id), db)
        process_alerts(str(occ.id), db)

    from app.models.alert_sent import AlertChannel

    email_count = (
        db.query(AlertSent)
        .filter(AlertSent.occurrence_id == occ.id, AlertSent.channel == AlertChannel.email)
        .count()
    )
    ws_count = (
        db.query(AlertSent)
        .filter(AlertSent.occurrence_id == occ.id, AlertSent.channel == AlertChannel.websocket)
        .count()
    )
    assert email_count == 1
    assert ws_count == 1


def test_alerta_placa_inativa_nao_dispara(db, setup_tenant):
    plan, tenant, camera, _, _ = setup_tenant

    mp = MonitoredPlate(
        client_id=tenant.id,
        plate="ABC1234",
        alert_email="alerta@test.com",
        is_active=False,  # inactive — should not trigger alerts
    )
    db.add(mp)
    db.flush()

    occ = _occ(db, camera, "ABC1234")

    with (
        patch("app.services.alert_service.send_plate_alert", return_value=True) as mock_send,
        patch("app.services.alert_service._publish_ws_alert"),
    ):
        from app.services.alert_service import process_alerts
        process_alerts(str(occ.id), db)

    assert mock_send.call_count == 0


# ── Exportação CSV ─────────────────────────────────────────────────────────────


def test_csv_export_com_filtro(client, db, setup_tenant):
    plan, tenant, camera, admin, _ = setup_tenant
    _occ(db, camera, "ABC1234")
    _occ(db, camera, "ABC5678")
    _occ(db, camera, "XYZ9W87")

    res = client.get(
        "/api/occurrences/export?plate=ABC",
        headers=_auth(_tok(admin)),
    )
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]

    import csv, io
    reader = csv.DictReader(io.StringIO(res.text))
    rows = list(reader)
    assert len(rows) == 2
    plates_in_csv = {row["Placa"] for row in rows}
    assert plates_in_csv == {"ABC1234", "ABC5678"}


def test_csv_export_sem_filtro_retorna_tudo(client, db, setup_tenant):
    plan, tenant, camera, admin, _ = setup_tenant
    for p in ["P1", "P2", "P3"]:
        _occ(db, camera, p)

    res = client.get("/api/occurrences/export", headers=_auth(_tok(admin)))
    assert res.status_code == 200

    import csv, io
    rows = list(csv.DictReader(io.StringIO(res.text)))
    assert len(rows) == 3


# ── Stats ──────────────────────────────────────────────────────────────────────


def test_stats_hoje(client, db, setup_tenant):
    plan, tenant, camera, admin, _ = setup_tenant
    _occ(db, camera, "ABC1234")
    _occ(db, camera, "ABC5678")

    res = client.get("/api/occurrences/stats", headers=_auth(_tok(admin)))
    assert res.status_code == 200
    data = res.json()
    assert data["total_today"] == 2
    assert data["total_week"] == 2
    assert len(data["by_hour"]) == 24
    assert "top_cameras" in data
    assert "top_plates" in data


# ── Placas monitoradas CRUD ────────────────────────────────────────────────────


def test_criar_placa_monitorada(client, db, setup_tenant):
    plan, tenant, camera, admin, _ = setup_tenant
    res = client.post(
        "/api/monitored-plates/",
        json={
            "client_id": str(tenant.id),
            "plate": "ABC1234",
            "description": "Teste",
            "alert_email": "alerta@test.com",
            "is_active": True,
        },
        headers=_auth(_tok(admin)),
    )
    assert res.status_code == 201
    assert res.json()["plate"] == "ABC1234"


def test_criar_placa_sem_client_id_usa_usuario(client, db, setup_tenant):
    """O frontend não envia client_id; deve vir do usuário logado (sem 422)."""
    plan, tenant, camera, admin, _ = setup_tenant
    res = client.post(
        "/api/monitored-plates/",
        json={"plate": "QWE4567", "description": None, "alert_email": None},
        headers=_auth(_tok(admin)),
    )
    assert res.status_code == 201, res.text
    assert res.json()["client_id"] == str(tenant.id)
    assert res.json()["plate"] == "QWE4567"


def test_toggle_placa_monitorada(client, db, setup_tenant):
    plan, tenant, camera, admin, _ = setup_tenant
    mp = MonitoredPlate(
        client_id=tenant.id,
        plate="XYZ9W87",
        is_active=True,
    )
    db.add(mp)
    db.commit()
    db.refresh(mp)

    res = client.patch(
        f"/api/monitored-plates/{mp.id}",
        json={"is_active": False},
        headers=_auth(_tok(admin)),
    )
    assert res.status_code == 200
    assert res.json()["is_active"] is False


def test_listar_placas_isolamento(client, db, setup_two_tenants):
    _, tenant_a, cam_a, user_a, _, cam_b, user_b = setup_two_tenants

    mp_a = MonitoredPlate(client_id=tenant_a.id, plate="AAAA11", is_active=True)
    mp_b = MonitoredPlate(client_id=cam_b.client_id, plate="BBBB22", is_active=True)
    db.add_all([mp_a, mp_b])
    db.commit()

    res = client.get("/api/monitored-plates/", headers=_auth(_tok(user_a)))
    assert res.status_code == 200
    plates = [p["plate"] for p in res.json()]
    assert "AAAA11" in plates
    assert "BBBB22" not in plates
