from app.core.config import settings


def _vehicle_box_iou(current: dict[str, int], previous: dict[str, int]) -> float:
    current_x1 = current["bbox_x"]
    current_y1 = current["bbox_y"]
    current_x2 = current_x1 + current["bbox_w"]
    current_y2 = current_y1 + current["bbox_h"]

    previous_x1 = previous["bbox_x"]
    previous_y1 = previous["bbox_y"]
    previous_x2 = previous_x1 + previous["bbox_w"]
    previous_y2 = previous_y1 + previous["bbox_h"]

    inter_x1 = max(current_x1, previous_x1)
    inter_y1 = max(current_y1, previous_y1)
    inter_x2 = min(current_x2, previous_x2)
    inter_y2 = min(current_y2, previous_y2)

    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    intersection = inter_w * inter_h
    if intersection <= 0:
        return 0.0

    current_area = current["bbox_w"] * current["bbox_h"]
    previous_area = previous["bbox_w"] * previous["bbox_h"]
    union = current_area + previous_area - intersection
    if union <= 0:
        return 0.0
    return intersection / union


def _is_pilot_camera(camera_id: str) -> bool:
    return camera_id in settings.get_pilot_camera_ids()


def _queue_depth() -> int:
    try:
        import redis

        cache = redis.from_url(settings.REDIS_URL, decode_responses=True)
        for queue_name in ("frames", "celery"):
            try:
                depth = cache.llen(queue_name)
                if depth:
                    return int(depth)
            except Exception:
                continue
    except Exception:
        return 0
    return 0


def _should_sample_high_volume_frame(camera_id: str, preview_frames_last_minute: int) -> bool:
    if _is_pilot_camera(camera_id):
        return True
    if preview_frames_last_minute < settings.HIGH_VOLUME_PREVIEW_FPS_THRESHOLD:
        return True
    sample_every = max(1, settings.HIGH_VOLUME_SAMPLE_EVERY)
    try:
        import redis

        cache = redis.from_url(settings.REDIS_URL, decode_responses=True)
        counter_key = f"camera-frame:{camera_id}:sample-seq"
        counter = int(cache.incr(counter_key))
        cache.expire(counter_key, 300)
        return counter % sample_every == 0
    except Exception:
        return True


def warm_worker_models() -> None:
    try:
        from app.services.ocr_service import warm_ocr_models

        warm_ocr_models()
    except Exception:
        pass

try:
    from celery import Celery

    celery_app = Celery(
        "frame_processor", broker=settings.REDIS_URL, backend=settings.REDIS_URL
    )
    celery_app.conf.task_routes = {"app.workers.frame_processor.*": {"queue": "frames"}}

    @celery_app.on_after_configure.connect
    def _warm_up_worker_models(*_args, **_kwargs) -> None:
        warm_worker_models()

    @celery_app.task(name="app.workers.frame_processor.process_frame")
    def process_frame(camera_id: str, frame_b64: str) -> None:
        import base64
        import json
        import hashlib
        import logging
        import uuid
        from time import perf_counter
        from datetime import datetime, timezone, timedelta

        from app.core.database import SessionLocal
        from app.models.camera import Camera
        from app.models.occurrence import Occurrence
        from app.services.ocr_service import recognizer
        from app.services.vehicle_detection_service import vehicle_detector
        from app.services.storage_service import save_bytes
        from app.services.alert_service import process_alerts
        from app.models.vehicle_event import VehicleEvent
        from app.services.camera_service import crop_roi_frame
        from app.services.preview_telemetry_service import record_preview_frame
        from app.services.image_quality_service import record_image_quality
        from app.services.ocr_pipeline_metrics_service import record_ocr_pipeline_metrics
        from app.services.ocr_pipeline_alert_service import maybe_publish_ocr_pipeline_alert
        from app.services.camera_health_alert_service import maybe_publish_camera_health_alert
        from app.services.worker_delay_alert_service import maybe_publish_worker_delay_alert
        from app.services.preview_telemetry_service import get_preview_telemetry

        logger = logging.getLogger(__name__)
        frame_bytes = base64.b64decode(frame_b64)

        db = SessionLocal()
        try:
            camera = db.query(Camera).filter(Camera.id == uuid.UUID(camera_id)).first()
            if not camera or not camera.is_active:
                return

            analysis_bytes = frame_bytes
            roi_values = (camera.roi_x, camera.roi_y, camera.roi_width, camera.roi_height)
            if all(value is not None for value in roi_values):
                analysis_bytes = crop_roi_frame(
                    analysis_bytes,
                    float(camera.roi_x),
                    float(camera.roi_y),
                    float(camera.roi_width),
                    float(camera.roi_height),
                )

            record_preview_frame(str(camera.id))
            record_image_quality(str(camera.id), analysis_bytes)
            preview_telemetry = get_preview_telemetry(str(camera.id), camera.is_online)
            if not _should_sample_high_volume_frame(str(camera.id), preview_telemetry.preview_frames_last_minute):
                logger.debug(
                    "High-volume frame sampled camera=%s frames_last_minute=%s",
                    camera.id,
                    preview_telemetry.preview_frames_last_minute,
                )
                maybe_publish_camera_health_alert(camera)
                maybe_publish_worker_delay_alert(db)
                return

            try:
                import redis

                cache = redis.from_url(settings.REDIS_URL, decode_responses=True)
                frame_digest = hashlib.sha256(analysis_bytes).hexdigest()
                cache_key = f"camera-frame:{camera.id}:last-digest"
                previous_digest = cache.get(cache_key)
                if previous_digest == frame_digest:
                    logger.debug("Repeated frame skipped camera=%s digest=%s", camera.id, frame_digest[:12])
                    return
                cache.set(cache_key, frame_digest, ex=max(3, settings.AGENT_FRAME_INTERVAL * 3))
            except Exception as exc:
                logger.debug("Frame repeat cache unavailable: %s", exc)

            capture_started_at = perf_counter()
            vehicle = vehicle_detector.best_detection(analysis_bytes)
            capture_seconds = perf_counter() - capture_started_at
            record_ocr_pipeline_metrics(
                str(camera.id),
                capture_seconds=capture_seconds,
                capture_success=True,
            )

            if vehicle is None:
                maybe_publish_ocr_pipeline_alert(camera)
                maybe_publish_camera_health_alert(camera)
                maybe_publish_worker_delay_alert(db)
                return

            event_image_path = save_bytes(vehicle.crop_bytes, camera_id)

            ocr_started_at = perf_counter()
            result = recognizer.recognize(vehicle.crop_bytes, camera_id=camera_id)
            ocr_seconds = perf_counter() - ocr_started_at
            record_ocr_pipeline_metrics(
                str(camera.id),
                ocr_seconds=ocr_seconds,
                ocr_success=result is not None,
                false_positive=False,
            )
            maybe_publish_ocr_pipeline_alert(camera)

            plate = result["plate"] if result is not None else None
            confidence = result["confidence"] if result is not None else 0.0
            vehicle_type = result.get("vehicle_type") if result is not None else None
            if vehicle_type is None and vehicle is not None:
                vehicle_type = vehicle.vehicle_type

            # Deduplication for vehicle counts: avoid counting the same vehicle signature repeatedly.
            vehicle_event: VehicleEvent | None = None
            if vehicle is not None:
                try:
                    import redis

                    cache = redis.from_url(settings.REDIS_URL, decode_responses=True)
                    current_box = {
                        "bbox_x": int(vehicle.bbox_x),
                        "bbox_y": int(vehicle.bbox_y),
                        "bbox_w": int(vehicle.bbox_w),
                        "bbox_h": int(vehicle.bbox_h),
                    }
                    track_key = f"vehicle-track:{camera.id}"
                    now_ts = datetime.now(timezone.utc).timestamp()
                    acquired = True
                    raw_track = cache.get(track_key)
                    if raw_track:
                        try:
                            track = json.loads(raw_track)
                        except Exception:
                            track = {}

                        previous_box = track.get("bbox")
                        previous_type = track.get("vehicle_type")
                        previous_seen_at = float(track.get("last_seen_at", 0.0) or 0.0)
                        if (
                            previous_box
                            and previous_type == vehicle.vehicle_type
                            and now_ts - previous_seen_at <= settings.VEHICLE_EVENT_DEDUP_SECONDS
                            and _vehicle_box_iou(current_box, previous_box) >= 0.35
                        ):
                            acquired = False

                    track_payload = {
                        "vehicle_type": vehicle.vehicle_type,
                        "bbox": current_box,
                        "last_seen_at": now_ts,
                    }
                    cache.set(
                        track_key,
                        json.dumps(track_payload),
                        ex=max(settings.VEHICLE_EVENT_DEDUP_SECONDS * 2, 120),
                    )
                except Exception as exc:
                    logger.debug("Vehicle dedup cache unavailable: %s", exc)
                    acquired = True

                if acquired:
                    vehicle_event = VehicleEvent(
                        camera_id=camera.id,
                        occurrence_id=None,
                        vehicle_type=vehicle.vehicle_type,
                        confidence=vehicle.confidence,
                        bbox_x=vehicle.bbox_x,
                        bbox_y=vehicle.bbox_y,
                        bbox_w=vehicle.bbox_w,
                        bbox_h=vehicle.bbox_h,
                        image_path=event_image_path,
                    )
                    db.add(vehicle_event)
                    db.flush()

            # Deduplication: ignore same plate from same camera in last N seconds
            occ = None
            persistence_seconds: float | None = None
            if result is not None and plate is not None:
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
                else:
                    # expires_at from plan retention
                    client = camera.client
                    plan = client.plan
                    expires_at = None
                    if plan and plan.retention_days:
                        expires_at = datetime.now(timezone.utc) + timedelta(days=plan.retention_days)

                    persist_started_at = perf_counter()

                    occ = Occurrence(
                        camera_id=camera.id,
                        plate=plate,
                        confidence=confidence,
                        image_path=event_image_path,
                        expires_at=expires_at,
                        vehicle_type=vehicle_type,
                        vehicle_color=result.get("vehicle_color"),
                        vehicle_make_model=result.get("vehicle_make_model"),
                        region_code=result.get("region_code"),
                        ocr_engine_used=result.get("engine"),
                    )
                    db.add(occ)
                    db.flush()

                    process_alerts(str(occ.id), db)
                    persistence_seconds = perf_counter() - persist_started_at

            if vehicle_event is not None:
                vehicle_event.occurrence_id = occ.id if occ is not None else None

            db.commit()
            if persistence_seconds is not None:
                record_ocr_pipeline_metrics(
                    str(camera.id),
                    persistence_seconds=persistence_seconds,
                )
                maybe_publish_ocr_pipeline_alert(camera)
            maybe_publish_camera_health_alert(camera)
            maybe_publish_worker_delay_alert(db)
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
        from time import perf_counter
        from datetime import datetime, timezone

        from app.core.database import SessionLocal
        from app.models.camera import Camera, ConnectionType
        from app.services.camera_service import capture_rtsp_frame, crop_half_frame
        from app.services.storage_service import save_latest_frame
        from app.services.preview_telemetry_service import record_preview_frame
        from app.services.preview_telemetry_service import get_preview_telemetry
        from app.services.ocr_pipeline_metrics_service import record_ocr_pipeline_metrics
        from app.services.ocr_pipeline_alert_service import maybe_publish_ocr_pipeline_alert
        from app.services.worker_delay_alert_service import maybe_publish_worker_delay_alert

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
            queue_depth = _queue_depth()
            for camera in cameras:
                try:
                    if queue_depth >= settings.WORKER_DELAY_QUEUE_THRESHOLD and not _is_pilot_camera(str(camera.id)):
                        logger.debug(
                            "Skipping RTSP capture due backlog camera=%s queue_depth=%s",
                            camera.id,
                            queue_depth,
                        )
                        maybe_publish_worker_delay_alert(db)
                        continue
                    capture_started_at = perf_counter()
                    frame_bytes = capture_rtsp_frame(camera.rtsp_url)
                    capture_seconds = perf_counter() - capture_started_at
                    record_ocr_pipeline_metrics(
                        str(camera.id),
                        capture_seconds=capture_seconds,
                        capture_success=frame_bytes is not None,
                    )
                    maybe_publish_ocr_pipeline_alert(camera)
                    if frame_bytes is None:
                        continue
                    if camera.dual_lens and camera.lens_side in ("upper", "lower"):
                        frame_bytes = crop_half_frame(frame_bytes, camera.lens_side)
                    save_latest_frame(frame_bytes, str(camera.id))
                    record_preview_frame(str(camera.id))
                    preview_telemetry = get_preview_telemetry(str(camera.id), True)
                    camera.last_seen_at = datetime.now(timezone.utc)
                    db.commit()
                    queue_depth = _queue_depth()
                    if queue_depth >= settings.WORKER_DELAY_QUEUE_THRESHOLD and not _is_pilot_camera(str(camera.id)):
                        logger.debug(
                            "Skipping RTSP enqueue due backlog camera=%s queue_depth=%s",
                            camera.id,
                            queue_depth,
                        )
                        maybe_publish_worker_delay_alert(db)
                        continue
                    if not _should_sample_high_volume_frame(
                        str(camera.id),
                        preview_telemetry.preview_frames_last_minute,
                    ):
                        logger.debug(
                            "RTSP frame sampled camera=%s frames_last_minute=%s queue_depth=%s",
                            camera.id,
                            preview_telemetry.preview_frames_last_minute,
                            queue_depth,
                        )
                        maybe_publish_worker_delay_alert(db)
                        continue
                    frame_b64 = base64.b64encode(frame_bytes).decode()
                    process_frame.delay(str(camera.id), frame_b64)
                    queue_depth = _queue_depth()
                except Exception as exc:
                    logger.warning("RTSP poll failed camera=%s: %s", camera.id, exc)
            maybe_publish_worker_delay_alert(db)
        finally:
            db.close()

except ImportError:
    class _NoOpTask:
        def delay(self, *args, **kwargs):  # type: ignore[override]
            pass

    check_alerts = _NoOpTask()  # type: ignore[assignment]
    process_frame = _NoOpTask()  # type: ignore[assignment]
