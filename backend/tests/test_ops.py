from datetime import datetime, timezone

from app.core.security import hash_password
from app.models.camera import Camera, ConnectionType
from app.models.client import Client
from app.models.plan import Plan
from app.models.user import User, UserRole


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_ops_metrics_endpoint_retorna_resumo_operacional(client, db):
    plan = Plan(
        name="Ops",
        max_cameras=5,
        retention_days=30,
        email_alerts=False,
        realtime_alerts=False,
        price_monthly=0,
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    tenant = Client(name="Cliente Ops", email="ops@test.com", plan_id=plan.id, is_active=True)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    user = User(
        email="admin-ops@test.com",
        name="Admin Ops",
        password_hash=hash_password("Admin@123"),
        role=UserRole.super_admin,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    camera = Camera(
        client_id=tenant.id,
        name="Cam Ops",
        connection_type=ConnectionType.rtsp,
        rtsp_url="rtsp://example/stream",
        is_active=True,
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(camera)
    db.commit()

    login = client.post("/api/auth/login", json={"email": user.email, "password": "Admin@123"})
    assert login.status_code == 200, login.text

    res = client.get("/api/ops/metrics", headers=_auth(login.json()["access_token"]))
    assert res.status_code == 200
    data = res.json()
    assert data["total_cameras"] == 1
    assert "queue_depth" in data
    assert "operational_status" in data
    assert "ocr_pipeline_status" in data


class _FakeRedis:
    """Redis fake que registra as chaves apagadas (sem servidor real)."""

    def __init__(self) -> None:
        self.deleted: list[str] = []

    def delete(self, *keys: str) -> int:
        self.deleted.extend(keys)
        return len(keys)


def test_ops_metrics_reset_admin(client, camera_rtsp_a, admin_a):
    """client_admin reseta as métricas das câmeras do próprio cliente."""
    from unittest.mock import patch

    from tests.conftest import _auth_header

    fake = _FakeRedis()
    with patch("app.services.operational_metrics_service._redis_client", return_value=fake):
        res = client.post("/api/ops/metrics/reset", headers=_auth_header(admin_a))
    assert res.status_code == 200, res.text
    assert res.json()["cameras_reset"] == 1
    # Apagou as 4 chaves de telemetria da única câmera do cliente.
    assert any(f"camera-telemetry:{camera_rtsp_a.id}:ocr-pipeline" == k for k in fake.deleted)


def test_ops_metrics_reset_super_admin_todas(client, camera_rtsp_a, camera_b, super_admin_user):
    """super_admin reseta as métricas de todas as câmeras."""
    from unittest.mock import patch

    from tests.conftest import _auth_header

    with patch("app.services.operational_metrics_service._redis_client", return_value=_FakeRedis()):
        res = client.post("/api/ops/metrics/reset", headers=_auth_header(super_admin_user))
    assert res.status_code == 200, res.text
    assert res.json()["cameras_reset"] == 2


def test_ops_metrics_reset_client_user_proibido(client, camera_rtsp_a, user_a):
    """client_user não pode resetar métricas (apenas visualiza)."""
    from tests.conftest import _auth_header

    res = client.post("/api/ops/metrics/reset", headers=_auth_header(user_a))
    assert res.status_code == 403
