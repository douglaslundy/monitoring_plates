"""
Alert tests for email, websocket and WhatsApp alert delivery.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from app.core.security import create_access_token, hash_password
from app.models.alert_sent import AlertChannel, AlertSent
from app.models.camera import Camera, ConnectionType
from app.models.client import Client
from app.models.monitored_plate import MonitoredPlate
from app.models.occurrence import Occurrence
from app.models.plan import Plan
from app.models.user import User, UserRole


def _make_tenant(db, email_alerts: bool, realtime_alerts: bool):
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
        name="Camera",
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


def _monitored(db, tenant, plate: str, email: str | None = "alerta@test.com", whatsapp: str | None = None):
    mp = MonitoredPlate(
        client_id=tenant.id,
        plate=plate,
        description="Teste",
        alert_email=email,
        alert_whatsapp=whatsapp,
        is_active=True,
    )
    db.add(mp)
    db.flush()
    return mp


def test_email_enviado_quando_plano_tem_email_alerts(db):
    _plan, tenant, camera = _make_tenant(db, email_alerts=True, realtime_alerts=False)
    _monitored(db, tenant, "ABC1234")
    occ = _occ(db, camera, "ABC1234")

    with (
        patch("app.services.alert_service.send_plate_alert", return_value=True) as mock_send,
        patch("app.services.alert_service._publish_ws_alert"),
        patch("app.services.whatsapp_service.send_whatsapp_alert"),
    ):
        from app.services.alert_service import process_alerts

        process_alerts(str(occ.id), db)

    assert mock_send.call_count == 1
    alert = db.query(AlertSent).filter(AlertSent.occurrence_id == occ.id).first()
    assert alert is not None
    assert alert.channel == AlertChannel.email
    assert alert.status == "sent"
    assert alert.message is not None
    assert "Placa ABC1234 detectada" in alert.message


def test_email_nao_enviado_quando_plano_sem_email_alerts(db):
    _plan, tenant, camera = _make_tenant(db, email_alerts=False, realtime_alerts=False)
    _monitored(db, tenant, "ABC1234")
    occ = _occ(db, camera, "ABC1234")

    with (
        patch("app.services.alert_service.send_plate_alert", return_value=True) as mock_send,
        patch("app.services.alert_service._publish_ws_alert"),
        patch("app.services.whatsapp_service.send_whatsapp_alert"),
    ):
        from app.services.alert_service import process_alerts

        process_alerts(str(occ.id), db)

    assert mock_send.call_count == 0
    count = db.query(AlertSent).filter(AlertSent.occurrence_id == occ.id).count()
    assert count == 0


def test_ws_publicado_quando_plano_tem_realtime_alerts(db):
    _plan, tenant, camera = _make_tenant(db, email_alerts=False, realtime_alerts=True)
    _monitored(db, tenant, "XYZ9W87")
    occ = _occ(db, camera, "XYZ9W87")

    with (
        patch("app.services.alert_service.send_plate_alert"),
        patch("app.services.alert_service._publish_ws_alert") as mock_ws,
        patch("app.services.whatsapp_service.send_whatsapp_alert"),
    ):
        from app.services.alert_service import process_alerts

        process_alerts(str(occ.id), db)

    assert mock_ws.call_count == 1


def test_ws_grava_alert_sent_quando_realtime(db):
    """Match de placa monitorada em plano realtime (sem e-mail/WhatsApp) DEVE
    gravar um AlertSent(channel=websocket) para aparecer em 'Alertas disparados'."""
    _plan, tenant, camera = _make_tenant(db, email_alerts=False, realtime_alerts=True)
    _monitored(db, tenant, "ABC1234", email=None, whatsapp=None)
    occ = _occ(db, camera, "ABC1234")

    with (
        patch("app.services.alert_service.send_plate_alert"),
        patch("app.services.alert_service._publish_ws_alert"),
        patch("app.services.whatsapp_service.send_whatsapp_alert"),
    ):
        from app.services.alert_service import process_alerts

        process_alerts(str(occ.id), db)

    alert = (
        db.query(AlertSent)
        .filter(AlertSent.occurrence_id == occ.id, AlertSent.channel == AlertChannel.websocket)
        .first()
    )
    assert alert is not None
    assert alert.status == "sent"
    assert alert.message is not None
    assert "Placa ABC1234 detectada" in alert.message


def test_ws_alert_sent_nao_duplicado(db):
    _plan, tenant, camera = _make_tenant(db, email_alerts=False, realtime_alerts=True)
    _monitored(db, tenant, "ABC1234", email=None, whatsapp=None)
    occ = _occ(db, camera, "ABC1234")

    with (
        patch("app.services.alert_service.send_plate_alert"),
        patch("app.services.alert_service._publish_ws_alert"),
        patch("app.services.whatsapp_service.send_whatsapp_alert"),
    ):
        from app.services.alert_service import process_alerts

        process_alerts(str(occ.id), db)
        process_alerts(str(occ.id), db)

    count = (
        db.query(AlertSent)
        .filter(AlertSent.occurrence_id == occ.id, AlertSent.channel == AlertChannel.websocket)
        .count()
    )
    assert count == 1


def test_ws_nao_grava_alert_sent_sem_realtime(db):
    _plan, tenant, camera = _make_tenant(db, email_alerts=False, realtime_alerts=False)
    _monitored(db, tenant, "ABC1234", email=None, whatsapp=None)
    occ = _occ(db, camera, "ABC1234")

    with (
        patch("app.services.alert_service.send_plate_alert"),
        patch("app.services.alert_service._publish_ws_alert"),
        patch("app.services.whatsapp_service.send_whatsapp_alert"),
    ):
        from app.services.alert_service import process_alerts

        process_alerts(str(occ.id), db)

    count = (
        db.query(AlertSent)
        .filter(AlertSent.occurrence_id == occ.id, AlertSent.channel == AlertChannel.websocket)
        .count()
    )
    assert count == 0


def test_ws_nao_publicado_quando_plano_sem_realtime_alerts(db):
    _plan, tenant, camera = _make_tenant(db, email_alerts=False, realtime_alerts=False)
    _monitored(db, tenant, "XYZ9W87")
    occ = _occ(db, camera, "XYZ9W87")

    with (
        patch("app.services.alert_service.send_plate_alert"),
        patch("app.services.alert_service._publish_ws_alert") as mock_ws,
        patch("app.services.whatsapp_service.send_whatsapp_alert"),
    ):
        from app.services.alert_service import process_alerts

        process_alerts(str(occ.id), db)

    assert mock_ws.call_count == 0


def test_whatsapp_enviado_quando_alerta_whatsapp_configurado(db):
    _plan, tenant, camera = _make_tenant(db, email_alerts=False, realtime_alerts=False)
    _monitored(db, tenant, "ABC1234", email=None, whatsapp="+5511999998888")
    occ = _occ(db, camera, "ABC1234")

    with (
        patch("app.services.whatsapp_service.send_whatsapp_alert", return_value=True) as mock_send,
        patch("app.services.alert_service._publish_ws_alert"),
        patch("app.services.alert_service.send_plate_alert"),
    ):
        from app.services.alert_service import process_alerts

        process_alerts(str(occ.id), db)

    assert mock_send.call_count == 1
    kwargs = mock_send.call_args.kwargs
    assert kwargs["to"] == "+5511999998888"
    assert kwargs["plate"] == "ABC1234"
    assert kwargs["confidence"] == 0.95
    assert kwargs["image_bytes"] is None or isinstance(kwargs["image_bytes"], (bytes, bytearray))
    alert = (
        db.query(AlertSent)
        .filter(AlertSent.occurrence_id == occ.id, AlertSent.channel == AlertChannel.whatsapp)
        .first()
    )
    assert alert is not None
    assert alert.status == "sent"
    assert alert.message is not None
    assert "Placa ABC1234 detectada" in alert.message


def test_whatsapp_nao_enviado_sem_alert_whatsapp(db):
    _plan, tenant, camera = _make_tenant(db, email_alerts=False, realtime_alerts=False)
    _monitored(db, tenant, "ABC1234", email=None, whatsapp=None)
    occ = _occ(db, camera, "ABC1234")

    with (
        patch("app.services.whatsapp_service.send_whatsapp_alert") as mock_send,
        patch("app.services.alert_service._publish_ws_alert"),
        patch("app.services.alert_service.send_plate_alert"),
    ):
        from app.services.alert_service import process_alerts

        process_alerts(str(occ.id), db)

    assert mock_send.call_count == 0
    assert (
        db.query(AlertSent)
        .filter(AlertSent.occurrence_id == occ.id, AlertSent.channel == AlertChannel.whatsapp)
        .count()
        == 0
    )


def test_sem_placa_monitorada_nenhum_alerta(db):
    _plan, _tenant, camera = _make_tenant(db, email_alerts=True, realtime_alerts=True)
    occ = _occ(db, camera, "AAA1111")

    with (
        patch("app.services.alert_service.send_plate_alert") as mock_send,
        patch("app.services.alert_service._publish_ws_alert") as mock_ws,
        patch("app.services.whatsapp_service.send_whatsapp_alert") as mock_whatsapp,
    ):
        from app.services.alert_service import process_alerts

        process_alerts(str(occ.id), db)

    assert mock_send.call_count == 0
    assert mock_ws.call_count == 0
    assert mock_whatsapp.call_count == 0
    assert db.query(AlertSent).count() == 0


def test_alerta_email_nao_duplicado(db):
    _plan, tenant, camera = _make_tenant(db, email_alerts=True, realtime_alerts=False)
    _monitored(db, tenant, "ABC1234")
    occ = _occ(db, camera, "ABC1234")

    with (
        patch("app.services.alert_service.send_plate_alert", return_value=True),
        patch("app.services.alert_service._publish_ws_alert"),
        patch("app.services.whatsapp_service.send_whatsapp_alert"),
    ):
        from app.services.alert_service import process_alerts

        process_alerts(str(occ.id), db)
        process_alerts(str(occ.id), db)

    count = db.query(AlertSent).filter(AlertSent.occurrence_id == occ.id).count()
    assert count == 1


def test_email_nao_enviado_sem_alert_email_no_monitored_plate(db):
    _plan, tenant, camera = _make_tenant(db, email_alerts=True, realtime_alerts=False)

    _monitored(db, tenant, "ABC1234", email=None, whatsapp=None)
    occ = _occ(db, camera, "ABC1234")

    with (
        patch("app.services.alert_service.send_plate_alert") as mock_send,
        patch("app.services.alert_service._publish_ws_alert"),
        patch("app.services.whatsapp_service.send_whatsapp_alert"),
    ):
        from app.services.alert_service import process_alerts

        process_alerts(str(occ.id), db)

    assert mock_send.call_count == 0


def test_placa_global_admin_dispara_mesmo_sem_plano(db):
    """Placa global do admin (client_id=None) dispara e-mail SEMPRE (independe do
    plano da câmera) e grava o AlertSent(websocket), mas NÃO publica no canal do
    cliente (não vaza a placa do admin)."""
    _plan, _tenant, camera = _make_tenant(db, email_alerts=False, realtime_alerts=False)
    mp = MonitoredPlate(
        client_id=None,  # global
        plate="GLB1234",
        alert_email="admin@test.com",
        is_active=True,
    )
    db.add(mp)
    db.flush()
    occ = _occ(db, camera, "GLB1234")

    with (
        patch("app.services.alert_service.send_plate_alert", return_value=True) as mock_send,
        patch("app.services.alert_service._publish_ws_alert") as mock_ws,
        patch("app.services.whatsapp_service.send_whatsapp_alert"),
    ):
        from app.services.alert_service import process_alerts

        process_alerts(str(occ.id), db)

    assert mock_send.call_count == 1  # e-mail disparou mesmo com plano sem email_alerts
    assert mock_ws.call_count == 0  # não publica no canal do cliente
    ws = (
        db.query(AlertSent)
        .filter(AlertSent.occurrence_id == occ.id, AlertSent.channel == AlertChannel.websocket)
        .first()
    )
    assert ws is not None  # aparece em "Alertas disparados" do admin


def test_alert_logs_endpoint_filters_and_returns_message(client, db, super_admin_user):
    _plan, tenant, camera = _make_tenant(db, email_alerts=True, realtime_alerts=False)
    _monitored(db, tenant, "ABC1234")
    occ = _occ(db, camera, "ABC1234")

    with (
        patch("app.services.alert_service.send_plate_alert", return_value=True),
        patch("app.services.alert_service._publish_ws_alert"),
        patch("app.services.whatsapp_service.send_whatsapp_alert"),
    ):
        from app.services.alert_service import process_alerts

        process_alerts(str(occ.id), db)

    token = create_access_token({"sub": str(super_admin_user.id), "role": super_admin_user.role})
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/alerts/sent?channel=email&message=ABC1234", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["plate"] == "ABC1234"
    assert data[0]["camera_name"] == "Camera"
    assert data[0]["message"] is not None
