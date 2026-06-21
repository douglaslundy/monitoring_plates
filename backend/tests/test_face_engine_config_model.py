from app.models.face_engine_config import FaceEngineConfig, FaceEngineType


def test_create_face_engine_config(db):
    cfg = FaceEngineConfig(
        engine_type=FaceEngineType.rekognition.value,
        is_active=True,
        api_token="AKIA...",
        api_secret="secret",
        region="us-east-1",
        threshold=0.85,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    assert cfg.is_active is True
    assert cfg.threshold == 0.85
