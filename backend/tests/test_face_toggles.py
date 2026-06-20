"""Tests for OCR/Face toggle columns on Plan and Camera models."""
from app.models.plan import Plan
from app.models.camera import Camera, ConnectionType


def test_plan_has_face_columns(db, basic_plan):
    """Plan should have ocr_enabled, face_recognition_enabled and face_engine columns with correct defaults."""
    assert basic_plan.ocr_enabled is True
    assert basic_plan.face_recognition_enabled is False
    assert basic_plan.face_engine == "system_default"


def test_plan_face_recognition_can_be_enabled(db):
    """Plan can be created with face_recognition_enabled=True and a specific face_engine."""
    plan = Plan(
        name="FaceTest",
        price_monthly=10,
        face_recognition_enabled=True,
        face_engine="system_default",
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    assert plan.ocr_enabled is True
    assert plan.face_recognition_enabled is True
    assert plan.face_engine == "system_default"


def test_camera_has_face_toggles(db, client_a):
    """Camera should have enable_ocr and enable_face columns with correct defaults."""
    cam = Camera(
        client_id=client_a.id,
        name="C1",
        connection_type=ConnectionType.rtsp,
    )
    db.add(cam)
    db.commit()
    db.refresh(cam)
    assert cam.enable_ocr is True
    assert cam.enable_face is False


def test_camera_enable_face_can_be_set(db, client_a):
    """Camera can be created with enable_face=True."""
    cam = Camera(
        client_id=client_a.id,
        name="C2",
        connection_type=ConnectionType.rtsp,
        enable_face=True,
    )
    db.add(cam)
    db.commit()
    db.refresh(cam)
    assert cam.enable_ocr is True
    assert cam.enable_face is True
