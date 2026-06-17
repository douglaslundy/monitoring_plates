from io import BytesIO
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from uuid import UUID

import pytest

from app.core.security import hash_password
from app.models.camera import Camera, ConnectionType
from app.models.client import Client
from app.models.plan import Plan
from app.models.user import User, UserRole


@pytest.fixture
def plan(db):
    p = Plan(
        name="Básico",
        max_cameras=3,
        retention_days=30,
        email_alerts=False,
        realtime_alerts=False,
        price_monthly=0,
        is_active=True,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture
def tenant_a(db, plan):
    c = Client(name="Cliente A", email="a@cliente.com", plan_id=plan.id, is_active=True)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture
def tenant_b(db, plan):
    c = Client(name="Cliente B", email="b@cliente.com", plan_id=plan.id, is_active=True)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture
def super_admin(db):
    u = User(
        email="admin@sistema.com",
        name="Admin",
        password_hash=hash_password("Admin@123"),
        role=UserRole.super_admin,
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def client_user_a(db, tenant_a):
    u = User(
        email="user@clientea.com",
        name="User A",
        password_hash=hash_password("Admin@123"),
        role=UserRole.client_user,
        client_id=tenant_a.id,
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def login(client, email: str, password: str = "Admin@123") -> str:
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Camera creation ────────────────────────────────────────────────────────────

def test_camera_agent_token_unico_gerado(client, db, super_admin, tenant_a):
    """Agent camera gets a unique 32-char hex token on creation."""
    token = login(client, "admin@sistema.com")
    res = client.post(
        "/api/cameras",
        json={
            "client_id": str(tenant_a.id),
            "name": "Cam Agent",
            "connection_type": "agent",
            "is_active": True,
        },
        headers=auth(token),
    )
    assert res.status_code == 201
    data = res.json()
    assert data["agent_token"] is not None
    assert len(data["agent_token"]) == 32
    assert "-" not in data["agent_token"]


def test_camera_rtsp_sem_agent_token(client, db, super_admin, tenant_a):
    """RTSP camera should have no agent token."""
    token = login(client, "admin@sistema.com")
    res = client.post(
        "/api/cameras",
        json={
            "client_id": str(tenant_a.id),
            "name": "Cam RTSP",
            "connection_type": "rtsp",
            "rtsp_url": "rtsp://192.168.1.1/stream",
            "is_active": True,
        },
        headers=auth(token),
    )
    assert res.status_code == 201
    assert res.json()["agent_token"] is None


def test_camera_pode_salvar_roi(client, db, super_admin, tenant_a):
    """Camera payload should persist ROI fields for the detector pipeline."""
    token = login(client, "admin@sistema.com")
    res = client.post(
        "/api/cameras",
        json={
            "client_id": str(tenant_a.id),
            "name": "Cam ROI",
            "connection_type": "rtsp",
            "rtsp_url": "rtsp://192.168.1.3/stream",
            "preview_refresh_seconds": 3.5,
            "roi_x": 0.1,
            "roi_y": 0.2,
            "roi_width": 0.4,
            "roi_height": 0.5,
            "is_active": True,
        },
        headers=auth(token),
    )
    assert res.status_code == 201
    data = res.json()
    assert data["preview_refresh_seconds"] == 3.5
    assert data["roi_x"] == 0.1
    assert data["roi_y"] == 0.2
    assert data["roi_width"] == 0.4
    assert data["roi_height"] == 0.5

    get_res = client.get(f"/api/cameras/{data['id']}", headers=auth(token))
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["preview_refresh_seconds"] == 3.5
    assert get_data["roi_x"] == 0.1
    assert get_data["roi_height"] == 0.5


def test_camera_pode_atualizar_preview_refresh_seconds(client, db, super_admin, tenant_a):
    """Camera update should persist the configured live refresh interval."""
    token = login(client, "admin@sistema.com")
    create_res = client.post(
        "/api/cameras",
        json={
            "client_id": str(tenant_a.id),
            "name": "Cam Refresh",
            "connection_type": "rtsp",
            "rtsp_url": "rtsp://192.168.1.4/stream",
            "preview_refresh_seconds": 2.5,
            "is_active": True,
        },
        headers=auth(token),
    )
    assert create_res.status_code == 201
    camera_id = create_res.json()["id"]

    update_res = client.put(
        f"/api/cameras/{camera_id}",
        json={"preview_refresh_seconds": 4.25},
        headers=auth(token),
    )
    assert update_res.status_code == 200
    assert update_res.json()["preview_refresh_seconds"] == 4.25

    get_res = client.get(f"/api/cameras/{camera_id}", headers=auth(token))
    assert get_res.status_code == 200
    assert get_res.json()["preview_refresh_seconds"] == 4.25


def test_dois_agentes_tokens_diferentes(client, db, super_admin, tenant_a):
    """Two agent cameras must have distinct tokens."""
    token = login(client, "admin@sistema.com")
    body = {"client_id": str(tenant_a.id), "name": "Cam", "connection_type": "agent", "is_active": True}
    r1 = client.post("/api/cameras", json=body, headers=auth(token))
    r2 = client.post("/api/cameras", json={**body, "name": "Cam 2"}, headers=auth(token))
    assert r1.json()["agent_token"] != r2.json()["agent_token"]


def test_client_user_pode_cadastrar_camera_no_proprio_cliente(client, db, tenant_a, client_user_a):
    """A client_user can create a camera for their own tenant."""
    user_token = login(client, "user@clientea.com")
    res = client.post(
        "/api/cameras",
        json={
            "client_id": str(tenant_a.id),
            "name": "Cam User",
            "connection_type": "rtsp",
            "rtsp_url": "rtsp://192.168.1.2/stream",
            "is_active": True,
        },
        headers=auth(user_token),
    )
    assert res.status_code == 201
    assert res.json()["client_id"] == str(tenant_a.id)


# ── /api/agent/frame ───────────────────────────────────────────────────────────

def test_agent_frame_token_correto(client, db, super_admin, tenant_a):
    """/api/agent/frame with valid Bearer token returns 200 and queues a task."""
    import sys
    import types

    # Stub frame_processor module so the lazy import inside the route works
    # without requiring Celery or Redis in the test environment.
    mock_task = MagicMock()
    mock_task.delay = MagicMock(return_value=None)
    stub_module = types.ModuleType("app.workers.frame_processor")
    stub_module.process_frame = mock_task  # type: ignore[attr-defined]

    admin_token = login(client, "admin@sistema.com")
    cam_res = client.post(
        "/api/cameras",
        json={"client_id": str(tenant_a.id), "name": "Cam", "connection_type": "agent", "is_active": True},
        headers=auth(admin_token),
    )
    agent_token = cam_res.json()["agent_token"]

    fake_jpeg = b"\xff\xd8\xff" + b"\x00" * 64
    with patch.dict(sys.modules, {"app.workers.frame_processor": stub_module}):
        res = client.post(
            "/api/agent/frame",
            files={"frame": ("frame.jpg", BytesIO(fake_jpeg), "image/jpeg")},
            headers={"Authorization": f"Bearer {agent_token}"},
        )
    assert res.status_code == 200
    data = res.json()
    assert data["received"] is True
    assert "camera_id" in data
    mock_task.delay.assert_called_once()


def test_agent_frame_token_errado(client, db):
    """/api/agent/frame with invalid token returns 401."""
    fake_jpeg = b"\xff\xd8\xff" + b"\x00" * 64
    res = client.post(
        "/api/agent/frame",
        files={"frame": ("frame.jpg", BytesIO(fake_jpeg), "image/jpeg")},
        headers={"Authorization": "Bearer token-invalido"},
    )
    assert res.status_code == 401


def test_agent_frame_sem_bearer(client, db):
    """/api/agent/frame without Bearer prefix returns 401."""
    fake_jpeg = b"\xff\xd8\xff" + b"\x00" * 64
    res = client.post(
        "/api/agent/frame",
        files={"frame": ("frame.jpg", BytesIO(fake_jpeg), "image/jpeg")},
        headers={"Authorization": "algumtoken"},
    )
    assert res.status_code == 401


# ── Multi-tenant isolation ─────────────────────────────────────────────────────

def test_cliente_nao_ve_cameras_de_outro_cliente(client, db, super_admin, tenant_a, tenant_b, client_user_a):
    """A client_user only sees cameras belonging to their own client."""
    admin_token = login(client, "admin@sistema.com")

    # Create one camera for each tenant
    client.post(
        "/api/cameras",
        json={"client_id": str(tenant_a.id), "name": "Cam A", "connection_type": "rtsp", "rtsp_url": "rtsp://a", "is_active": True},
        headers=auth(admin_token),
    )
    client.post(
        "/api/cameras",
        json={"client_id": str(tenant_b.id), "name": "Cam B", "connection_type": "rtsp", "rtsp_url": "rtsp://b", "is_active": True},
        headers=auth(admin_token),
    )

    user_token = login(client, "user@clientea.com")
    res = client.get("/api/cameras", headers=auth(user_token))
    assert res.status_code == 200
    cameras = res.json()
    assert len(cameras) == 1
    assert cameras[0]["client_id"] == str(tenant_a.id)
    assert cameras[0]["name"] == "Cam A"


def test_super_admin_ve_todas_cameras(client, db, super_admin, tenant_a, tenant_b):
    """Super admin sees cameras from all clients."""
    admin_token = login(client, "admin@sistema.com")
    client.post("/api/cameras", json={"client_id": str(tenant_a.id), "name": "Cam A", "connection_type": "rtsp", "rtsp_url": "rtsp://a", "is_active": True}, headers=auth(admin_token))
    client.post("/api/cameras", json={"client_id": str(tenant_b.id), "name": "Cam B", "connection_type": "rtsp", "rtsp_url": "rtsp://b", "is_active": True}, headers=auth(admin_token))

    res = client.get("/api/cameras", headers=auth(admin_token))
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_get_camera_por_id_inclui_is_online(client, db, super_admin, tenant_a):
    """GET /{id} returns camera with is_online field and last_occurrences."""
    admin_token = login(client, "admin@sistema.com")
    cam = client.post(
        "/api/cameras",
        json={"client_id": str(tenant_a.id), "name": "Cam", "connection_type": "rtsp", "rtsp_url": "rtsp://x", "is_active": True},
        headers=auth(admin_token),
    ).json()

    res = client.get(f"/api/cameras/{cam['id']}", headers=auth(admin_token))
    assert res.status_code == 200
    data = res.json()
    assert "is_online" in data
    assert "last_occurrences" in data
    assert isinstance(data["last_occurrences"], list)


def test_camera_test_salva_preview_recente(client, db, super_admin, tenant_a):
    """RTSP camera test should refresh the latest frame used by live preview."""
    from app.api.routes import cameras as cameras_route

    admin_token = login(client, "admin@sistema.com")
    cam = client.post(
        "/api/cameras",
        json={"client_id": str(tenant_a.id), "name": "Cam preview", "connection_type": "rtsp", "rtsp_url": "rtsp://x", "is_active": True},
        headers=auth(admin_token),
    ).json()

    fake_frame = b"\xff\xd8\xff" + b"\x00" * 64
    with patch.object(cameras_route, "capture_rtsp_frame", return_value=fake_frame), patch.object(cameras_route, "save_latest_frame") as mock_save:
        res = client.post(f"/api/cameras/{cam['id']}/test", headers=auth(admin_token))

    assert res.status_code == 200
    mock_save.assert_called_once()


def test_camera_last_frame_nao_mostra_frame_velho_quando_offline(client, db, super_admin, tenant_a):
    """An offline camera must not expose an old latest frame as if it were live."""
    from app.api.routes import cameras as cameras_route

    admin_token = login(client, "admin@sistema.com")
    cam = client.post(
        "/api/cameras",
        json={"client_id": str(tenant_a.id), "name": "Cam offline", "connection_type": "rtsp", "rtsp_url": "rtsp://x", "is_active": True},
        headers=auth(admin_token),
    ).json()

    camera = db.query(Camera).filter(Camera.id == UUID(cam["id"])).first()
    assert camera is not None
    camera.last_seen_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()

    with patch.object(cameras_route, "latest_frame_exists", return_value=True):
        res = client.get(f"/api/cameras/{cam['id']}/last-frame", headers=auth(admin_token))

    assert res.status_code == 200
    data = res.json()
    assert data["image_url"] is None


def test_camera_recente_com_last_seen_at_aparece_online(client, db, tenant_a):
    """A camera with a recent last_seen_at must be serialized as online."""
    cam = Camera(
        client_id=tenant_a.id,
        name="Cam recente",
        connection_type=ConnectionType.rtsp,
        rtsp_url="rtsp://example/stream",
        is_active=True,
        last_seen_at=datetime.now(timezone.utc) - timedelta(seconds=30),
    )
    db.add(cam)
    db.commit()
    db.refresh(cam)

    assert cam.is_online is True


def test_list_cameras_inclui_telemetria_preview(client, db, super_admin, tenant_a):
    """Camera list should expose preview telemetry for the live dashboard."""
    from app.api.routes import cameras as cameras_route
    from app.services.preview_telemetry_service import PreviewTelemetry
    from app.services.image_quality_service import ImageQuality
    from app.services.ocr_pipeline_metrics_service import OcrPipelineMetrics

    admin_token = login(client, "admin@sistema.com")
    client.post(
        "/api/cameras",
        json={
            "client_id": str(tenant_a.id),
            "name": "Cam telemetria",
            "connection_type": "rtsp",
            "rtsp_url": "rtsp://x",
            "is_active": True,
        },
        headers=auth(admin_token),
    )
    cam = db.query(Camera).filter(Camera.name == "Cam telemetria").first()
    assert cam is not None
    cam.last_seen_at = datetime.now(timezone.utc)
    db.commit()

    telemetry = PreviewTelemetry(
        preview_fps=2.5,
        preview_frames_last_minute=150,
        preview_last_frame_at=1234567.0,
        preview_latency_seconds=1.5,
        preview_status="streaming",
    )
    quality = ImageQuality(
        quality_score=81.0,
        quality_label="good",
        blur_score=23.5,
        brightness=54.0,
        contrast=19.0,
    )
    ocr_metrics = OcrPipelineMetrics(
        capture_attempts=4,
        capture_successes=4,
        capture_failures=0,
        ocr_attempts=4,
        ocr_successes=3,
        ocr_failures=1,
        ocr_false_positives=0,
        persistence_attempts=3,
        avg_capture_seconds=0.18,
        avg_ocr_seconds=0.42,
        avg_persistence_seconds=0.11,
        capture_success_rate=1.0,
        ocr_success_rate=0.75,
        ocr_false_positive_rate=0.0,
        last_attempt_at=datetime.now(timezone.utc).timestamp(),
    )

    with patch.object(cameras_route, "get_preview_telemetry", return_value=telemetry), patch.object(cameras_route, "get_image_quality", return_value=quality), patch.object(cameras_route, "get_ocr_pipeline_metrics", return_value=ocr_metrics):
        res = client.get("/api/cameras", headers=auth(admin_token))

    assert res.status_code == 200
    data = res.json()[0]
    assert data["preview_fps"] == 2.5
    assert data["preview_frames_last_minute"] == 150
    assert data["preview_latency_seconds"] == 1.5
    assert data["preview_status"] == "streaming"
    assert data["ocr_pipeline_status"] == "healthy"
    assert data["ocr_pipeline_health_score"] == 100.0
    assert data["ocr_attempts"] == 4
    assert data["detector_status"] == "healthy"
    assert data["detector_health_score"] == 100.0
    assert data["quality_score"] == 81.0
    assert data["quality_label"] == "good"
    assert data["blur_score"] == 23.5


# ── Camera deletion ─────────────────────────────────────────────────────────────

def test_excluir_camera_com_dependentes(client, db, super_admin, tenant_a):
    """Excluir câmera que já gerou ocorrências/eventos/alertas não deve falhar.

    As FKs não têm cascade no banco; a rota remove os dependentes antes.
    Reproduz o IntegrityError relatado ao excluir uma câmera.
    """
    from app.models.occurrence import Occurrence
    from app.models.vehicle_event import VehicleEvent
    from app.models.alert_sent import AlertSent, AlertChannel
    from app.models.monitored_plate import MonitoredPlate

    cam = Camera(
        client_id=tenant_a.id,
        name="Cam Del",
        connection_type=ConnectionType.rtsp,
        rtsp_url="rtsp://x/y",
        is_active=True,
    )
    db.add(cam)
    db.commit()
    db.refresh(cam)

    occ = Occurrence(
        camera_id=cam.id,
        plate="DEL1234",
        confidence=0.9,
        image_path="cameras/x/img.jpg",
    )
    db.add(occ)
    db.commit()
    db.refresh(occ)

    db.add(
        VehicleEvent(
            camera_id=cam.id,
            occurrence_id=occ.id,
            category="vehicle",
            vehicle_type="car",
            confidence=0.9,
            bbox_x=0,
            bbox_y=0,
            bbox_w=10,
            bbox_h=10,
        )
    )
    mp = MonitoredPlate(client_id=tenant_a.id, plate="DEL1234", is_active=True)
    db.add(mp)
    db.commit()
    db.add(
        AlertSent(
            occurrence_id=occ.id,
            monitored_plate_id=mp.id,
            channel=AlertChannel.websocket,
            status="sent",
        )
    )
    db.commit()

    cam_id = cam.id
    occ_id = occ.id
    token = login(client, "admin@sistema.com")
    res = client.delete(f"/api/cameras/{cam_id}", headers=auth(token))
    assert res.status_code == 204, res.text

    assert db.query(Camera).filter(Camera.id == cam_id).first() is None
    assert db.query(Occurrence).filter(Occurrence.camera_id == cam_id).count() == 0
    assert db.query(VehicleEvent).filter(VehicleEvent.camera_id == cam_id).count() == 0
    assert db.query(AlertSent).filter(AlertSent.occurrence_id == occ_id).count() == 0


def test_webrtc_dual_lens_usa_webrtc_recortado(client, db, super_admin, tenant_a):
    """Câmera dual-lens usa WebRTC com a fonte de recorte (lente configurada)."""
    from app.services import go2rtc_service

    cam = Camera(
        client_id=tenant_a.id,
        name="Cam Dual",
        connection_type=ConnectionType.rtsp,
        rtsp_url="rtsp://x/y",
        dual_lens=True,
        lens_side="upper",
        is_active=True,
    )
    db.add(cam)
    db.commit()
    db.refresh(cam)

    token = login(client, "admin@sistema.com")
    with patch.object(go2rtc_service, "register_stream", return_value=True) as reg:
        res = client.get(f"/api/cameras/{cam.id}/webrtc", headers=auth(token))
    assert res.status_code == 200
    body = res.json()
    assert body["enabled"] is True
    assert body["src"] == str(cam.id)
    assert f"src={cam.id}" in body["url"]
    # registrou passando a lente configurada (para refletir o recorte no live)
    assert reg.call_args.args[0] == str(cam.id)
    assert reg.call_args.args[3] == "upper"
