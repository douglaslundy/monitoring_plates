import base64
from types import SimpleNamespace
from unittest.mock import patch


def test_process_face_salva_imagem_anotada_com_nome(db):
    from app.core.database import engine
    from sqlalchemy.orm import sessionmaker
    from app.models.plan import Plan
    from app.models.client import Client
    from app.models.camera import Camera, ConnectionType
    from app.models.person import Person
    from app.models.face_detection import FaceDetection
    from app.workers.face_processor import process_face

    plan = Plan(
        name="PF",
        max_cameras=1,
        retention_days=30,
        price_monthly=0,
        face_recognition_enabled=True,
        face_engine="opencv",
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    tenant = Client(name="Cliente PF", email="pf@test.com", plan_id=plan.id, is_active=True)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    cam = Camera(
        client_id=tenant.id,
        name="Cam PF",
        connection_type=ConnectionType.rtsp,
        rtsp_url="rtsp://x/pf",
        is_active=True,
    )
    db.add(cam)
    db.commit()
    db.refresh(cam)

    person = Person(client_id=tenant.id, name="Douglas", is_active=True, alert_active=True)
    db.add(person)
    db.commit()
    db.refresh(person)

    worker_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    fake_result = (
        SimpleNamespace(crop_bytes=b"face-bytes", bbox_w=40, bbox_h=50),
        [0.1, 0.2, 0.3],
    )
    fake_match = SimpleNamespace(person_id=str(person.id), confidence=0.91)
    annotated_b64 = base64.b64encode(b"annotated-bytes").decode()

    with patch("app.core.database.SessionLocal", worker_session), \
         patch("app.services.face_detection_service.get_local_engine") as mock_get_engine, \
         patch("app.services.face_service.face_recognizer.resolve_engine_type", return_value="opencv"), \
         patch("app.services.face_service.face_recognizer.identify_by_embedding", return_value=fake_match), \
         patch("app.services.storage_service.read_file_bytes", return_value=b"original-bytes"), \
         patch("app.services.detection_overlay_service.draw_labeled_boxes", return_value=annotated_b64) as mock_draw, \
         patch("app.services.storage_service.save_bytes", return_value="cameras/test/annotated.jpg"), \
         patch("app.services.face_alert_service.process_face_alerts"), \
         patch("redis.from_url") as mock_redis:
        mock_get_engine.return_value.detect_and_embed.return_value = fake_result
        mock_redis.return_value.setex.return_value = True
        process_face.run(
            camera_id=str(cam.id),
            client_id=str(tenant.id),
            track_id="track-1",
            person_crop_b64=base64.b64encode(b"person-crop").decode(),
            bbox={"x": 10, "y": 20, "w": 30, "h": 40},
            image_path="cameras/test/original.jpg",
            expires_at_str=None,
        )

    fd = db.query(FaceDetection).one()
    assert fd.person_id == person.id
    assert fd.image_path == "cameras/test/annotated.jpg"
    assert mock_draw.call_args.args[1][0]["label"] == "Douglas"
