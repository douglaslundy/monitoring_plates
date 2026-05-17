"""
Etapa 8 — Testes de alertas: e-mail e WebSocket.

Verifica que alertas são disparados (ou não) de acordo com o plano.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from app.models.alert_sent import AlertSent, AlertChannel
from app.models.camera import Camera, ConnectionType
from app.models.client import Client
from app.models.monitored_plate import MonitoredPlate
from app.models.occurrence import Occurrence
from app.models.plan import Plan
from app.models.user import User, UserRole
from app.core.security import hash_password


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_tenant(db, email_alerts: bool, realtime_alerts: bool):
    """Create a plan/client/camera/user set."""
    plan = Plan(
        name="Plano Teste",
        max_cameras=5,
        retention_days=30,
        email_alerts=email_alerts,
        realtime_alerts=realtime_alerts,
        price_monthly=0,
    )
    db.add(plan)
    db.flush()

    tenant = Client(name=f"Cliente {email_alerts}", email=f"{email_alerts}@test.com", plan_id=plan.id)
    db.add(tenant)
    db.flush()

    camera = Camera(
        client_id=tenant.id,
        name="Câmera",
        connection_type=ConnectionType.agent,
        agent_token="tok-alerta-01",
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return plan, tenant, camera


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


def _monitored(db, tenant, plate: str, email: str = "alerta@test.com") -> MonitoredPlate:
    mp = MonitoredPlate(
        client_id=tenant.id,
        plate=plate,
        description="Teste",
        alert_email=email,
        is_active=True,
    )
    db.add(mp)
    db.flush()
    return mp


# ── E-mail conforme plano ─────────────────────────────────────────────────────

def test_email_enviado_quando_plano_tem_email_alerts(db):
    """E-mail is sent when plan.email_alerts=True and plate is monitored."""
    plan, tenant, camera = _make_tenant(db, email_alerts=True, realtime_alerts=False)
    _monitored(db, tenant, "ABC1234")
    occ = _occ(db, camera, "ABC1234")

    with (
        patch("app.services.alert_service.send_plate_alert", return_value=True) as mock_send,
        patch("app.services.alert_service._publish_ws_alert"),
    ):
        from app.services.alert_service import process_alerts
        process_alerts(str(occ.id), db)

    assert mock_send.call_count == 1
    alert = db.query(AlertSent).filter(AlertSent.occurrence_id == occ.id).first()
    assert alert is not None
    assert alert.channel == AlertChannel.email
    assert alert.status == "sent"


def test_email_nao_enviado_quando_plano_sem_email_alerts(db):
    """E-mail is NOT sent when plan.email_alerts=False."""
    plan, tenant, camera = _make_tenant(db, email_alerts=False, realtime_alerts=False)
    _monitored(db, tenant, "ABC1234")
    occ = _occ(db, camera, "ABC1234")

    with (
        patch("app.services.alert_service.send_plate_alert", return_value=True) as mock_send,
        patch("app.services.alert_service._publish_ws_alert"),
    ):
        from app.services.alert_service import process_alerts
        process_alerts(str(occ.id), db)

    assert mock_send.call_count == 0
    count = db.query(AlertSent).filter(AlertSent.occurrence_id == occ.id).count()
    assert count == 0


# ── WebSocket conforme plano ──────────────────────────────────────────────────

def test_ws_publicado_quando_plano_tem_realtime_alerts(db):
    """WebSocket alert is published when plan.realtime_alerts=True."""
    plan, tenant, camera = _make_tenant(db, email_alerts=False, realtime_alerts=True)
    _monitored(db, tenant, "XYZ9W87")
    occ = _occ(db, camera, "XYZ9W87")

    with (
        patch("app.services.alert_service.send_plate_alert"),
        patch("app.services.alert_service._publish_ws_alert") as mock_ws,
    ):
        from app.services.alert_service import process_alerts
        process_alerts(str(occ.id), db)

    assert mock_ws.call_count == 1


def test_ws_nao_publicado_quando_plano_sem_realtime_alerts(db):
    """WebSocket alert is NOT published when plan.realtime_alerts=False."""
    plan, tenant, camera = _make_tenant(db, email_alerts=False, realtime_alerts=False)
    _monitored(db, tenant, "XYZ9W87")
    occ = _occ(db, camera, "XYZ9W87")

    with (
        patch("app.services.alert_service.send_plate_alert"),
        patch("app.services.alert_service._publish_ws_alert") as mock_ws,
    ):
        from app.services.alert_service import process_alerts
        process_alerts(str(occ.id), db)

    assert mock_ws.call_count == 0


# ── Sem placa monitorada ──────────────────────────────────────────────────────

def test_sem_placa_monitorada_nenhum_alerta(db):
    """No monitored plate → no email, no WebSocket, no AlertSent record."""
    plan, tenant, camera = _make_tenant(db, email_alerts=True, realtime_alerts=True)
    occ = _occ(db, camera, "AAA1111")  # plate not monitored

    with (
        patch("app.services.alert_service.send_plate_alert") as mock_send,
        patch("app.services.alert_service._publish_ws_alert") as mock_ws,
    ):
        from app.services.alert_service import process_alerts
        process_alerts(str(occ.id), db)

    assert mock_send.call_count == 0
    assert mock_ws.call_count == 0
    assert db.query(AlertSent).count() == 0


# ── Sem duplicata ─────────────────────────────────────────────────────────────

def test_alerta_email_nao_duplicado(db):
    """Two calls to process_alerts for same occurrence create exactly one AlertSent."""
    plan, tenant, camera = _make_tenant(db, email_alerts=True, realtime_alerts=False)
    _monitored(db, tenant, "ABC1234")
    occ = _occ(db, camera, "ABC1234")

    with (
        patch("app.services.alert_service.send_plate_alert", return_value=True),
        patch("app.services.alert_service._publish_ws_alert"),
    ):
        from app.services.alert_service import process_alerts
        process_alerts(str(occ.id), db)
        process_alerts(str(occ.id), db)

    count = db.query(AlertSent).filter(AlertSent.occurrence_id == occ.id).count()
    assert count == 1


# ── Email alert_email ausente ─────────────────────────────────────────────────

def test_email_nao_enviado_sem_alert_email_no_monitored_plate(db):
    """Monitored plate without alert_email → no email even if plan has email_alerts."""
    plan, tenant, camera = _make_tenant(db, email_alerts=True, realtime_alerts=False)

    mp = MonitoredPlate(
        client_id=tenant.id,
        plate="ABC1234",
        alert_email=None,
        is_active=True,
    )
    db.add(mp)
    db.flush()

    occ = _occ(db, camera, "ABC1234")

    with (
        patch("app.services.alert_service.send_plate_alert") as mock_send,
        patch("app.services.alert_service._publish_ws_alert"),
    ):
        from app.services.alert_service import process_alerts
        process_alerts(str(occ.id), db)

    assert mock_send.call_count == 0
