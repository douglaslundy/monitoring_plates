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


def _open_cache():
    """Abre um único cliente Redis (pool interno). Retorna None se indisponível."""
    try:
        import redis

        return redis.from_url(settings.REDIS_URL, decode_responses=True)
    except Exception:
        return None


def _queue_depth(cache=None) -> int:
    try:
        cache = cache or _open_cache()
        if cache is None:
            return 0
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


def _should_sample_high_volume_frame(camera_id: str, preview_frames_last_minute: int, cache=None) -> bool:
    if _is_pilot_camera(camera_id):
        return True
    if preview_frames_last_minute < settings.HIGH_VOLUME_PREVIEW_FPS_THRESHOLD:
        return True
    sample_every = max(1, settings.HIGH_VOLUME_SAMPLE_EVERY)
    try:
        cache = cache or _open_cache()
        if cache is None:
            return True
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
        # Só faz o warm (download/carregamento dos modelos, que pode demorar) se
        # explicitamente habilitado. Caso contrário os modelos carregam de forma
        # preguiçosa no 1º frame. Isso evita que processos que apenas ENFILEIRAM
        # (capture-runner) travem ~minutos baixando modelos que não usam.
        import os

        if os.getenv("OCR_WARMUP_ENABLED", "").strip().lower() in ("1", "true", "yes"):
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
        from app.services.object_tracker_service import (
            load_tracks,
            update_tracks,
            save_tracks,
        )
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
        # Um único cliente Redis por frame (pool interno), reusado abaixo —
        # antes abríamos uma conexão nova a cada subetapa.
        cache = _open_cache()
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
            if not _should_sample_high_volume_frame(str(camera.id), preview_telemetry.preview_frames_last_minute, cache):
                logger.debug(
                    "High-volume frame sampled camera=%s frames_last_minute=%s",
                    camera.id,
                    preview_telemetry.preview_frames_last_minute,
                )
                maybe_publish_camera_health_alert(camera)
                maybe_publish_worker_delay_alert(db)
                return

            try:
                if cache is not None:
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
            detections = vehicle_detector.detect(analysis_bytes)
            capture_seconds = perf_counter() - capture_started_at
            record_ocr_pipeline_metrics(
                str(camera.id),
                capture_seconds=capture_seconds,
                capture_success=True,
            )

            if not detections:
                maybe_publish_ocr_pipeline_alert(camera)
                maybe_publish_camera_health_alert(camera)
                maybe_publish_worker_delay_alert(db)
                return

            now_ts = datetime.now(timezone.utc).timestamp()
            # Rastreia TODOS os objetos (veículo/pessoa/animal): conta cada um uma
            # única vez por permanência no frame — inclusive parado (o track se
            # mantém por IoU+tempo, então não recontabiliza).
            tracker_dets = [
                {
                    "category": d.category,
                    "label": d.vehicle_type,
                    "confidence": d.confidence,
                    "bbox": {
                        "bbox_x": int(d.bbox_x),
                        "bbox_y": int(d.bbox_y),
                        "bbox_w": int(d.bbox_w),
                        "bbox_h": int(d.bbox_h),
                    },
                }
                for d in detections
            ]
            def _safe_dim(value) -> int:
                # Detecções reais trazem int; em testes (MagicMock) ou fallback
                # vem não-numérico/0 -> trata como desconhecido (inteiro no frame).
                return int(value) if isinstance(value, (int, float)) else 0

            frame_w = _safe_dim(detections[0].frame_w) if detections else 0
            frame_h = _safe_dim(detections[0].frame_h) if detections else 0
            track_state = load_tracks(str(camera.id))
            track_state, newly, det_to_track = update_tracks(
                track_state, tracker_dets, now_ts, frame_w, frame_h
            )

            # Imagem de exibição: salva o FRAME CHEIO (resolução nativa) no máximo
            # uma vez por frame — compartilhada entre todos os veículos.
            _display_cache: dict[str, str | None] = {}

            def _display_image() -> str | None:
                if "path" not in _display_cache:
                    from app.services.detection_overlay_service import draw_detections

                    drawn = draw_detections(analysis_bytes, detections)
                    _display_cache["path"] = save_bytes(drawn, camera_id)
                return _display_cache["path"]

            # OCR em TODOS os veículos do frame.
            # Regras de persistência:
            #   - Cria ocorrência na 1ª leitura válida do track.
            #   - Atualiza se placa DIFERENTE + confiança MAIOR que a gravada.
            #   - Pula OCR se track ≥98% conf + parado há ≥15 min (track maduro).
            _STATIONARY_SKIP_SECS = 15 * 60   # 15 minutos
            _STATIONARY_SKIP_CONF = 0.98

            occ = None
            persistence_seconds: float | None = None

            for v_idx, d in enumerate(detections):
                if d.category != "vehicle":
                    continue

                v_track = det_to_track.get(v_idx)

                # Mantém stationary_since: quando o track ficou parado pela 1ª vez.
                if v_track is not None:
                    if v_track.get("stationary", False):
                        if v_track.get("stationary_since") is None:
                            v_track["stationary_since"] = now
                    else:
                        v_track["stationary_since"] = None

                # Pula OCR: track de alta confiança parado há muito tempo.
                if (
                    v_track is not None
                    and float(v_track.get("plate_confidence") or 0.0) >= _STATIONARY_SKIP_CONF
                    and v_track.get("stationary", False)
                    and v_track.get("stationary_since") is not None
                    and (now - float(v_track["stationary_since"])) > _STATIONARY_SKIP_SECS
                ):
                    continue

                ocr_started_at = perf_counter()
                result = recognizer.recognize(d.crop_bytes, camera_id=camera_id)
                ocr_seconds = perf_counter() - ocr_started_at
                record_ocr_pipeline_metrics(
                    str(camera.id),
                    ocr_seconds=ocr_seconds,
                    ocr_success=result is not None,
                    false_positive=False,
                )

                if result is None:
                    continue

                plate = result["plate"]
                confidence = result["confidence"]
                vehicle_type = result.get("vehicle_type") or d.vehicle_type

                # Só persiste se o track estiver confirmado (hits suficientes).
                if v_track is None or not v_track.get("counted"):
                    continue

                existing_occ_id = v_track.get("occurrence_id")

                if existing_occ_id is None:
                    # Primeira placa deste track — dedup por janela temporal.
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
                    if dup is not None:
                        logger.debug("Dedup: plate=%s camera=%s ignored", plate, camera_id)
                        v_track["occurrence_id"] = str(dup.id)
                        v_track["plate"] = plate
                        v_track["plate_confidence"] = float(confidence)
                    else:
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
                            image_path=_display_image(),
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
                        v_track["occurrence_id"] = str(occ.id)
                        v_track["plate"] = plate
                        v_track["plate_confidence"] = float(confidence)
                else:
                    # Track já tem placa — atualiza só se placa diferente + conf maior.
                    prev_conf = float(v_track.get("plate_confidence") or 0.0)
                    if plate != v_track.get("plate") and confidence > prev_conf:
                        existing_occ = (
                            db.query(Occurrence)
                            .filter(Occurrence.id == uuid.UUID(existing_occ_id))
                            .first()
                        )
                        if existing_occ is not None:
                            persist_started_at = perf_counter()
                            existing_occ.plate = plate
                            existing_occ.confidence = confidence
                            existing_occ.vehicle_type = vehicle_type
                            existing_occ.vehicle_color = result.get("vehicle_color")
                            existing_occ.vehicle_make_model = result.get("vehicle_make_model")
                            existing_occ.region_code = result.get("region_code")
                            existing_occ.ocr_engine_used = result.get("engine")
                            existing_occ.image_path = _display_image()
                            persistence_seconds = perf_counter() - persist_started_at
                            v_track["plate"] = plate
                            v_track["plate_confidence"] = float(confidence)
                            occ = existing_occ

            maybe_publish_ocr_pipeline_alert(camera)

            # Agrupamento piloto+moto (T5): pessoa "em cima" da moto vira UMA
            # detecção (moto principal + pessoa como companion). person_det -> moto_det.
            from app.services.detection_grouping_service import group_riders

            rider_to_moto = group_riders(detections)
            moto_to_rider = {m: p for p, m in rider_to_moto.items()}

            # Evento de detecção: 1 por track. reason="new" → contagem única
            # (insere); reason="class_change" → re-save (atualiza o evento
            # existente do track, SEM contar de novo).
            for tr in newly:
                di = tr["det_index"]
                det = detections[di]

                # Piloto: não grava evento standalone — representado pela moto.
                if tr["category"] == "person" and di in rider_to_moto:
                    continue

                companion_category = companion_type = None
                if di in moto_to_rider:
                    rider = detections[moto_to_rider[di]]
                    companion_category = rider.category
                    companion_type = rider.vehicle_type

                link_occ = None
                if tr["category"] == "vehicle":
                    # Busca o track vivo desta detecção para pegar o occurrence_id
                    # gravado pelo loop OCR multi-veículo.
                    tr_live = det_to_track.get(di)
                    occ_id_str = (tr_live or tr).get("occurrence_id")
                    if occ_id_str:
                        try:
                            link_occ = uuid.UUID(occ_id_str)
                        except Exception:
                            pass

                if tr.get("reason") == "class_change":
                    existing = (
                        db.query(VehicleEvent)
                        .filter(
                            VehicleEvent.camera_id == camera.id,
                            VehicleEvent.track_id == tr["track_id"],
                        )
                        .order_by(VehicleEvent.detected_at.desc())
                        .first()
                    )
                    if existing is not None:
                        existing.category = tr["category"]
                        existing.vehicle_type = tr["label"]
                        existing.confidence = det.confidence
                        existing.bbox_x = det.bbox_x
                        existing.bbox_y = det.bbox_y
                        existing.bbox_w = det.bbox_w
                        existing.bbox_h = det.bbox_h
                        existing.image_path = _display_image()
                        if companion_category is not None:
                            existing.companion_category = companion_category
                            existing.companion_type = companion_type
                        if link_occ is not None:
                            existing.occurrence_id = link_occ
                        continue

                db.add(
                    VehicleEvent(
                        camera_id=camera.id,
                        occurrence_id=link_occ,
                        category=tr["category"],
                        vehicle_type=tr["label"],
                        track_id=tr["track_id"],
                        confidence=det.confidence,
                        bbox_x=det.bbox_x,
                        bbox_y=det.bbox_y,
                        bbox_w=det.bbox_w,
                        bbox_h=det.bbox_h,
                        image_path=_display_image(),
                        companion_category=companion_category,
                        companion_type=companion_type,
                    )
                )

            db.commit()
            # Persiste o estado dos tracks (hits/counted/placa/occurrence_id) para
            # o próximo frame não recontar nem recriar a placa do mesmo objeto.
            save_tracks(str(camera.id), track_state)
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

    # poll_rtsp_cameras (Celery beat de 1s que reabria a RTSP a cada tick) foi
    # removido — a captura agora é feita pelo capture-runner (conexão persistente
    # + motion gating em app/workers/capture_runner.py).

except ImportError:
    class _NoOpTask:
        def delay(self, *args, **kwargs):  # type: ignore[override]
            pass

    check_alerts = _NoOpTask()  # type: ignore[assignment]
    process_frame = _NoOpTask()  # type: ignore[assignment]
