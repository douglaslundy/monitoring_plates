import pytest

from app.models.plan import Plan
from app.models.client import Client
from app.models.person import Person
from app.models.person_face import PersonFace
from app.services.face_service import FaceRouter, FaceMatch


@pytest.fixture
def sample_client_with_opencv_plan(db):
    plan = Plan(
        name="Faces OpenCV",
        max_cameras=5,
        retention_days=30,
        price_monthly=0,
        face_recognition_enabled=True,
        face_engine="opencv",
    )
    db.add(plan)
    db.flush()
    c = Client(name="Cliente Faces", email="faces@test.com", plan_id=plan.id, is_active=True)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def test_identify_local_matches_enrolled(db, monkeypatch, sample_client_with_opencv_plan):
    router = FaceRouter()
    monkeypatch.setattr(router, "resolve_engine_type", lambda cid: "opencv")
    monkeypatch.setattr("app.services.face_service._local_engine.embed", lambda b: [1.0, 0.0, 0.0])

    p = Person(client_id=sample_client_with_opencv_plan.id, name="X", is_active=True)
    db.add(p)
    db.commit()
    db.refresh(p)
    db.add(PersonFace(person_id=p.id, engine_type="opencv", embedding=[1.0, 0.0, 0.0]))
    db.commit()

    match = router.identify(str(sample_client_with_opencv_plan.id), b"img")
    assert isinstance(match, FaceMatch)
    assert match.person_id == str(p.id)
    assert match.confidence > 0.99


def test_identify_no_match_returns_none(db, monkeypatch, sample_client_with_opencv_plan):
    router = FaceRouter()
    monkeypatch.setattr(router, "resolve_engine_type", lambda cid: "opencv")
    monkeypatch.setattr("app.services.face_service._local_engine.embed", lambda b: None)
    assert router.identify(str(sample_client_with_opencv_plan.id), b"img") is None


def test_enroll_local_returns_embedding(db, monkeypatch, sample_client_with_opencv_plan):
    router = FaceRouter()
    monkeypatch.setattr(router, "resolve_engine_type", lambda cid: "opencv")
    monkeypatch.setattr("app.services.face_service._local_engine.embed", lambda b: [0.5, 0.5])

    p = Person(client_id=sample_client_with_opencv_plan.id, name="Y", is_active=True)
    db.add(p)
    db.commit()
    db.refresh(p)

    result = router.enroll(str(sample_client_with_opencv_plan.id), str(p.id), b"img")
    assert result.engine_type == "opencv"
    assert result.embedding == [0.5, 0.5]
    assert result.external_ref is None
