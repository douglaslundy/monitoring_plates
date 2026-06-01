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

        result = recognizer.recognize(frame_bytes, camera_id=camera_id)
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
                vehicle_type=result.get("vehicle_type"),
                vehicle_color=result.get("vehicle_color"),
                vehicle_make_model=result.get("vehicle_make_model"),
                region_code=result.get("region_code"),
                ocr_engine_used=result.get("engine"),
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

    @celery_app.task(name="app.workers.frame_processor.poll_rtsp_cameras")
    def poll_rtsp_cameras() -> None:
        import base64
        import logging
        from datetime import datetime, timezone

        from app.core.database import SessionLocal
        from app.models.camera import Camera, ConnectionType
        from app.services.camera_service import capture_rtsp_frame, crop_half_frame

        logger = logging.getLogger(__name__)
        db = SessionLocal()
        try:
            cameras = (
                db.query(Camera)
                .filter(
                    Camera.connection_type == ConnectionType.rtsp,
                    Camera.is_active == True,  # noqa: E712
                    Camera.rtsp_url.isnot(None),
                )
                .all()
            )
            for camera in cameras:
                try:
                    frame_bytes = capture_rtsp_frame(camera.rtsp_url)
                    if frame_bytes is None:
                        continue
                    if camera.dual_lens and camera.lens_side in ("upper", "lower"):
                        frame_bytes = crop_half_frame(frame_bytes, camera.lens_side)
                    camera.last_seen_at = datetime.now(timezone.utc)
                    db.commit()
                    frame_b64 = base64.b64encode(frame_bytes).decode()
                    process_frame.delay(str(camera.id), frame_b64)
                except Exception as exc:
                    logger.warning("RTSP poll failed camera=%s: %s", camera.id, exc)
        finally:
            db.close()

except ImportError:
    class _NoOpTask:
        def delay(self, *args, **kwargs):  # type: ignore[override]
            pass

    check_alerts = _NoOpTask()  # type: ignore[assignment]
    process_frame = _NoOpTask()  # type: ignore[assignment]
