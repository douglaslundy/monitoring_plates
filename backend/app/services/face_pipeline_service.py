"""Bloco facial do pipeline (lógica testável, fora da task Celery).

`process_faces`: para cada detecção `person` cujo track está confirmado
(`counted`) e ainda sem `face_saved`, detecta o rosto no recorte da pessoa
(motor local só p/ achar/encaixotar), identifica via motor do plano, grava UM
`FaceDetection` por track e dispara alertas quando há pessoa casada.

`finalize_expired_faces`: quando o track expira, fecha a duração de rastreio
(`tracked_seconds`) do `FaceDetection` correspondente.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.models.face_detection import FaceDetection
from app.services.face_service import face_recognizer

logger = logging.getLogger(__name__)


def _detect_face_crop(person_crop_bytes: bytes) -> Optional[bytes]:
    """Acha o maior rosto dentro do recorte da pessoa e devolve o recorte JPEG do
    rosto (ou None se não houver rosto válido). Usa o motor LOCAL apenas para
    localizar/encaixotar — a identificação usa o motor do plano."""
    from app.services.face_detection_service import face_engine

    boxes = face_engine.detect(person_crop_bytes)
    if not boxes:
        return None
    return boxes[0].crop_bytes


def process_faces(
    db: Session,
    camera,
    detections: list,
    det_to_track: dict,
    display_image_fn: Callable[[], Optional[str]],
    now_ts: float,
) -> None:
    client_id = str(camera.client_id)
    plan = camera.client.plan if camera.client else None
    engine_type = face_recognizer.resolve_engine_type(client_id)

    expires_at = None
    if plan and plan.retention_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=plan.retention_days)

    persons_in_frame = sum(1 for d in detections if getattr(d, "category", None) == "person")
    logger.debug("pipeline facial camera=%s persons_in_frame=%d engine=%s", camera.id, persons_in_frame, engine_type)

    for idx, d in enumerate(detections):
        if getattr(d, "category", None) != "person":
            continue
        tr = det_to_track.get(idx)
        if tr is None:
            logger.debug("pipeline facial camera=%s idx=%d: track não encontrado", camera.id, idx)
            continue
        if not tr.get("counted"):
            logger.debug("pipeline facial camera=%s idx=%d track_id=%s: não confirmado ainda (counted=False)", camera.id, idx, tr.get("track_id"))
            continue
        if tr.get("face_saved"):
            continue

        crop = _detect_face_crop(d.crop_bytes)
        if crop is None:
            logger.debug(
                "pipeline facial camera=%s idx=%d track_id=%s: YuNet não detectou rosto no recorte da pessoa "
                "(bbox=%dx%d px) — verifique ângulo/distância da câmera",
                camera.id, idx, tr.get("track_id"), d.bbox_w, d.bbox_h,
            )
            continue

        logger.info("pipeline facial camera=%s track_id=%s: rosto detectado, identificando...", camera.id, tr.get("track_id"))
        match = face_recognizer.identify(client_id, crop)
        if match:
            logger.info("pipeline facial camera=%s track_id=%s: pessoa reconhecida person_id=%s conf=%.3f", camera.id, tr.get("track_id"), match.person_id, match.confidence)
        else:
            logger.info("pipeline facial camera=%s track_id=%s: rosto detectado mas NÃO reconhecido (sem cadastro ou confiança baixa)", camera.id, tr.get("track_id"))
        fd = FaceDetection(
            camera_id=camera.id,
            person_id=uuid.UUID(match.person_id) if match else None,
            confidence=match.confidence if match else None,
            image_path=display_image_fn(),
            bbox_x=int(d.bbox_x),
            bbox_y=int(d.bbox_y),
            bbox_w=int(d.bbox_w),
            bbox_h=int(d.bbox_h),
            track_id=tr.get("track_id"),
            expires_at=expires_at,
            face_engine_used=engine_type,
        )
        db.add(fd)
        db.flush()
        tr["face_saved"] = True
        tr["face_detection_id"] = str(fd.id)

        if match:
            try:
                from app.services.face_alert_service import process_face_alerts

                process_face_alerts(str(fd.id), db)
            except Exception:
                logger.warning("Falha ao processar alerta de face conhecida", exc_info=True)
        else:
            try:
                from app.services.face_alert_service import process_unknown_face_alert

                process_unknown_face_alert(str(fd.id), db)
            except Exception:
                logger.warning("Falha ao processar alerta de face desconhecida", exc_info=True)


def finalize_expired_faces(db: Session, expired: list[dict]) -> None:
    for e in expired:
        # Tenta pelo face_detection_id (caminho síncrono legado) e depois pelo
        # track_id (caminho assíncrono: face_processor pode ainda não ter rodado).
        fdid = e.get("face_detection_id")
        track_id = e.get("track_id")
        fd = None
        if fdid:
            fd = db.query(FaceDetection).filter(FaceDetection.id == uuid.UUID(str(fdid))).first()
        if fd is None and track_id:
            fd = (
                db.query(FaceDetection)
                .filter(FaceDetection.track_id == str(track_id))
                .order_by(FaceDetection.id.desc())
                .first()
            )
        if fd is None:
            continue
        try:
            duration = float(e["last_seen_at"]) - float(e["first_seen_at"])
        except (KeyError, TypeError, ValueError):
            continue
        if duration > 0:
            fd.tracked_seconds = duration
            db.flush()
