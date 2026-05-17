from app.core.config import settings

try:
    from celery import Celery

    celery_app = Celery(
        "frame_processor", broker=settings.REDIS_URL, backend=settings.REDIS_URL
    )
    celery_app.conf.task_routes = {"app.workers.frame_processor.*": {"queue": "frames"}}

    @celery_app.task(name="app.workers.frame_processor.process_frame")
    def process_frame(camera_id: str, frame_b64: str) -> None:
        import base64
        import logging
        import uuid
        from datetime import datetime, timezone, timedelta

        from app.core.database import SessionLocal
        from app.models.camera import Camera
        from app.models.occurrence import Occurrence
        from app.services.ocr_service import recognizer
        from app.services.storage_service import save_bytes
        from app.services.alert_service import process_alerts

        logger = logging.getLogger(__name__)
        frame_bytes = base64.b64decode(frame_b64)

        result = recognizer.recognize(frame_bytes)
        if result is None:
            return

        plate = result["plate"]
        confidence = result["confidence"]

        db = SessionLocal()
        try:
            camera = db.query(Camera).filter(Camera.id == uuid.UUID(camera_id)).first()
            if not camera or not camera.is_active:
                return

            # Deduplication: ignore same plate from same camera in last N seconds
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.AGENT_DEDUP_SECONDS)
            dup = (
                db.query(Occurrence)
                .filter(
                    Occurrence.camera_id == camera.id,
                    Occurrence.plate == plate,
                    Occurrence.detected_at >= cutoff,
                )
                .first()
            )
            if dup:
                logger.debug("Dedup: plate=%s camera=%s ignored", plate, camera_id)
                return

            # expires_at from plan retention
            client = camera.client
            plan = client.plan
            expires_at = None
            if plan and plan.retention_days:
                expires_at = datetime.now(timezone.utc) + timedelta(days=plan.retention_days)

            image_path = save_bytes(frame_bytes, camera_id)

            occ = Occurrence(
                camera_id=camera.id,
                plate=plate,
                confidence=confidence,
                image_path=image_path,
                expires_at=expires_at,
            )
            db.add(occ)
            db.commit()
            db.refresh(occ)

            process_alerts(str(occ.id), db)
        finally:
            db.close()

    @celery_app.task(name="app.workers.frame_processor.check_alerts")
    def check_alerts(occurrence_id: str) -> None:
        from app.core.database import SessionLocal
        from app.services.alert_service import process_alerts

        db = SessionLocal()
        try:
            process_alerts(occurrence_id, db)
        finally:
            db.close()

except ImportError:
    class _NoOpTask:
        def delay(self, *args, **kwargs):  # type: ignore[override]
            pass

    check_alerts = _NoOpTask()  # type: ignore[assignment]
    process_frame = _NoOpTask()  # type: ignore[assignment]
