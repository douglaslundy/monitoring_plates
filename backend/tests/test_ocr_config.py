"""Tests for OcrEngineConfig CRUD and OCR routing logic."""
import uuid
from unittest.mock import patch, MagicMock

import pytest

from tests.conftest import _auth_header
from app.models.ocr_engine_config import OcrEngineConfig, OcrEngineType, OcrEngineMode


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def easyocr_config(db):
    cfg = OcrEngineConfig(
        id=uuid.uuid4(),
        engine_type=OcrEngineType.easyocr,
        mode=OcrEngineMode.cloud,
        is_active=True,
        regions=["br"],
        enable_mmc=False,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


@pytest.fixture
def pr_config(db):
    cfg = OcrEngineConfig(
        id=uuid.uuid4(),
        engine_type=OcrEngineType.plate_recognizer,
        mode=OcrEngineMode.cloud,
        is_active=False,
        api_token="test-token-123",
        api_url="https://api.platerecognizer.com/v1/plate-reader/",
        regions=["br"],
        enable_mmc=False,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


# ── Access control ────────────────────────────────────────────────────────────

def test_list_configs_requires_super_admin(client, admin_a, user_a):
    r = client.get("/api/ocr-config", headers=_auth_header(admin_a))
    assert r.status_code == 403

    r = client.get("/api/ocr-config", headers=_auth_header(user_a))
    assert r.status_code == 403


def test_list_configs_super_admin_ok(client, super_admin_user, easyocr_config):
    r = client.get("/api/ocr-config", headers=_auth_header(super_admin_user))
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["engine_type"] == "easyocr"


def test_create_config_requires_super_admin(client, admin_a):
    r = client.post(
        "/api/ocr-config",
        headers=_auth_header(admin_a),
        json={"engine_type": "plate_recognizer", "mode": "cloud"},
    )
    assert r.status_code == 403


# ── CRUD ──────────────────────────────────────────────────────────────────────

def test_create_plate_recognizer_config(client, super_admin_user):
    payload = {
        "engine_type": "plate_recognizer",
        "mode": "cloud",
        "api_token": "my-secret-token",
        "api_url": "https://api.platerecognizer.com/v1/plate-reader/",
        "regions": ["br", "br-sp"],
        "enable_mmc": True,
        "is_active": False,
    }
    r = client.post("/api/ocr-config", headers=_auth_header(super_admin_user), json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["engine_type"] == "plate_recognizer"
    assert data["enable_mmc"] is True
    assert data["api_token"] == "***configured***"


def test_create_duplicate_engine_returns_409(client, super_admin_user, easyocr_config):
    r = client.post(
        "/api/ocr-config",
        headers=_auth_header(super_admin_user),
        json={"engine_type": "easyocr", "mode": "cloud"},
    )
    assert r.status_code == 409


def test_update_config(client, super_admin_user, pr_config):
    r = client.patch(
        f"/api/ocr-config/{pr_config.id}",
        headers=_auth_header(super_admin_user),
        json={"enable_mmc": True, "regions": ["br-rj"]},
    )
    assert r.status_code == 200
    assert r.json()["enable_mmc"] is True
    assert r.json()["regions"] == ["br-rj"]


def test_delete_config(client, super_admin_user, pr_config):
    r = client.delete(
        f"/api/ocr-config/{pr_config.id}",
        headers=_auth_header(super_admin_user),
    )
    assert r.status_code == 204

    r = client.get("/api/ocr-config", headers=_auth_header(super_admin_user))
    assert len(r.json()) == 0


def test_toggle_activate(client, super_admin_user, easyocr_config):
    assert easyocr_config.is_active is True

    r = client.post(
        f"/api/ocr-config/{easyocr_config.id}/activate",
        headers=_auth_header(super_admin_user),
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    r = client.post(
        f"/api/ocr-config/{easyocr_config.id}/activate",
        headers=_auth_header(super_admin_user),
    )
    assert r.json()["is_active"] is True


# ── Test connection ───────────────────────────────────────────────────────────

def test_test_easyocr_always_succeeds(client, super_admin_user, easyocr_config):
    r = client.post(
        f"/api/ocr-config/{easyocr_config.id}/test",
        headers=_auth_header(super_admin_user),
    )
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_test_plate_recognizer_missing_token(client, super_admin_user, db):
    cfg = OcrEngineConfig(
        id=uuid.uuid4(),
        engine_type=OcrEngineType.plate_recognizer,
        mode=OcrEngineMode.cloud,
        is_active=False,
        api_token=None,
        api_url="https://api.platerecognizer.com/v1/plate-reader/",
        regions=["br"],
    )
    db.add(cfg)
    db.commit()

    r = client.post(
        f"/api/ocr-config/{cfg.id}/test",
        headers=_auth_header(super_admin_user),
    )
    assert r.status_code == 200
    assert r.json()["success"] is False
    assert "Token" in r.json()["message"]


def test_test_plate_recognizer_invalid_token(client, super_admin_user, pr_config):
    mock_response = MagicMock()
    mock_response.status_code = 403

    with patch("app.api.routes.ocr_config.req.post", return_value=mock_response):
        r = client.post(
            f"/api/ocr-config/{pr_config.id}/test",
            headers=_auth_header(super_admin_user),
        )
    assert r.status_code == 200
    assert r.json()["success"] is False
    assert "403" in r.json()["message"]


def test_test_plate_recognizer_valid_token(client, super_admin_user, pr_config):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"results": []}

    with patch("app.api.routes.ocr_config.req.post", return_value=mock_response):
        r = client.post(
            f"/api/ocr-config/{pr_config.id}/test",
            headers=_auth_header(super_admin_user),
        )
    assert r.status_code == 200
    assert r.json()["success"] is True


# ── OCR Router ────────────────────────────────────────────────────────────────

def test_ocr_router_falls_back_to_easyocr_on_pr_failure():
    from app.services.ocr_service import OcrRouter, EasyOcrEngine, PlateRecognizerEngine

    router = OcrRouter()
    image = b"\xff\xd8\xff\xe0"  # invalid jpeg — both engines return None

    with patch.object(PlateRecognizerEngine, "recognize", side_effect=Exception("network error")):
        with patch.object(EasyOcrEngine, "recognize", return_value=None) as mock_easy:
            with patch.object(router, "_resolve_engine") as mock_resolve:
                mock_resolve.return_value = PlateRecognizerEngine(
                    api_token="tok", api_url="http://x", regions=["br"], enable_mmc=False
                )
                result = router.recognize(image, camera_id=None)
                mock_easy.assert_called_once()
                assert result is None


def test_ocr_router_returns_plate_recognizer_result():
    from app.services.ocr_service import OcrRouter, PlateRecognizerEngine

    expected = {
        "plate": "ABC1234",
        "confidence": 0.95,
        "engine": "plate_recognizer",
        "vehicle_type": "car",
        "vehicle_color": "white",
        "vehicle_make_model": None,
        "region_code": "br-sp",
        "candidates": [],
    }
    router = OcrRouter()

    with patch.object(PlateRecognizerEngine, "recognize", return_value=expected):
        with patch.object(router, "_resolve_engine") as mock_resolve:
            mock_resolve.return_value = PlateRecognizerEngine(
                api_token="tok", api_url="http://x", regions=["br"], enable_mmc=False
            )
            result = router.recognize(b"fake", camera_id=None)
            assert result == expected


# ── Occurrence extra fields ───────────────────────────────────────────────────

def test_occurrence_stores_vehicle_fields(db, camera_agent_a):
    from app.models.occurrence import Occurrence

    occ = Occurrence(
        camera_id=camera_agent_a.id,
        plate="ABC1234",
        confidence=0.95,
        image_path="cameras/test/frame.jpg",
        vehicle_type="car",
        vehicle_color="white",
        vehicle_make_model="Toyota Corolla",
        region_code="br-sp",
        ocr_engine_used="plate_recognizer",
    )
    db.add(occ)
    db.commit()
    db.refresh(occ)

    assert occ.vehicle_type == "car"
    assert occ.vehicle_color == "white"
    assert occ.vehicle_make_model == "Toyota Corolla"
    assert occ.region_code == "br-sp"
    assert occ.ocr_engine_used == "plate_recognizer"


def test_occurrence_vehicle_fields_nullable(db, camera_agent_a):
    from app.models.occurrence import Occurrence

    occ = Occurrence(
        camera_id=camera_agent_a.id,
        plate="XYZ9876",
        confidence=0.80,
        image_path="cameras/test/frame2.jpg",
    )
    db.add(occ)
    db.commit()
    db.refresh(occ)

    assert occ.vehicle_type is None
    assert occ.ocr_engine_used is None
