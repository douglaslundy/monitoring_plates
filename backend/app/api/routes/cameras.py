import base64
import asyncio
from datetime import datetime, timezone, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_db, get_current_user
from app.models.camera import Camera
from app.models.client import Client
from app.models.occurrence import Occurrence
from app.models.user import User, UserRole
from app.schemas.camera import CameraCreate, CameraRead, CameraUpdate, CameraDetail, OccurrenceSmall
from app.services.camera_service import generate_agent_token, capture_rtsp_frame, crop_half_frame
from app.services.storage_service import get_url, latest_frame_exists, read_file_bytes, save_latest_frame
from app.services.detector_health_service import build_detector_health
from app.services.ocr_pipeline_health_service import build_ocr_pipeline_health
from app.services.ocr_pipeline_metrics_service import get_ocr_pipeline_metrics
from app.services.preview_telemetry_service import get_preview_telemetry, record_preview_frame
from app.services.image_quality_service import get_image_quality, record_image_quality
from app.services.camera_health_alert_service import maybe_publish_camera_health_alert

router = APIRouter(prefix="/cameras", tags=["cameras"])


def _multipart_frame(image_bytes: bytes) -> bytes:
    return (
        b"--frame\r\n"
        b"Content-Type: image/jpeg\r\n"
        + f"Content-Length: {len(image_bytes)}\r\n\r\n".encode()
        + image_bytes
        + b"\r\n"
    )


def _get_camera_or_403(camera_id: UUID, current_user: User, db: Session) -> Camera:
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Câmera não encontrada")
    if current_user.role != UserRole.super_admin and camera.client_id != current_user.client_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    return camera


def _serialize_camera(camera: Camera) -> dict:
    telemetry = get_preview_telemetry(str(camera.id), camera.is_online)
    quality = get_image_quality(str(camera.id))
    ocr_metrics = get_ocr_pipeline_metrics(str(camera.id))
    ocr_health = build_ocr_pipeline_health(ocr_metrics)
    camera_online = camera.is_online or telemetry.preview_status != "offline"
    detector_health = build_detector_health(camera_online, telemetry, quality)
    payload = CameraRead.model_validate(camera).model_dump()
    payload["is_online"] = camera_online
    payload.update(telemetry.as_dict())
    payload.update(ocr_health.as_dict())
    payload.update(quality.as_dict())
    payload.update(detector_health.as_dict())
    if telemetry.preview_last_frame_at is not None:
        payload["preview_last_frame_at"] = datetime.fromtimestamp(
            telemetry.preview_last_frame_at, tz=timezone.utc
        )
    if ocr_health.last_attempt_at is not None:
        payload["last_attempt_at"] = datetime.fromtimestamp(
            ocr_health.last_attempt_at, tz=timezone.utc
        )
    return payload


@router.get("", response_model=List[CameraRead])
def list_cameras(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.super_admin:
        cameras = db.query(Camera).all()
    else:
        cameras = db.query(Camera).filter(Camera.client_id == current_user.client_id).all()
    return [_serialize_camera(camera) for camera in cameras]


@router.post("", response_model=CameraRead, status_code=201)
def create_camera(
    payload: CameraCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.super_admin:
        effective_client_id = payload.client_id
        if not effective_client_id:
            raise HTTPException(status_code=400, detail="client_id é obrigatório para super_admin")
    else:
        effective_client_id = current_user.client_id
        if not effective_client_id:
            active_clients = db.query(Client).filter(Client.is_active == True).all()  # noqa: E712
            if len(active_clients) == 1:
                effective_client_id = active_clients[0].id
                current_user.client_id = effective_client_id
                db.commit()
                db.refresh(current_user)
            else:
                raise HTTPException(status_code=400, detail="Usuário sem cliente vinculado")
        if payload.client_id and payload.client_id != current_user.client_id:
            raise HTTPException(status_code=403, detail="Acesso negado")

        tenant = db.query(Client).filter(Client.id == effective_client_id).first()
        if tenant and tenant.plan and tenant.plan.max_cameras is not None:
            count = db.query(Camera).filter(
                Camera.client_id == effective_client_id,
                Camera.is_active == True,  # noqa: E712
            ).count()
            if count >= tenant.plan.max_cameras:
                raise HTTPException(
                    status_code=400,
                    detail=f"Limite de câmeras do plano atingido ({tenant.plan.max_cameras})",
                )

    token = generate_agent_token() if payload.connection_type == "agent" else None
    camera_data = payload.model_dump(exclude_none=True)
    camera_data["client_id"] = effective_client_id
    camera = Camera(**camera_data, agent_token=token)
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


@router.get("/{camera_id}", response_model=CameraDetail)
def get_camera(
    camera_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    camera = _get_camera_or_403(camera_id, current_user, db)
    occurrences = (
        db.query(Occurrence)
        .filter(Occurrence.camera_id == camera_id)
        .order_by(Occurrence.detected_at.desc())
        .limit(5)
        .all()
    )
    camera_data = _serialize_camera(camera)
    occ_list = [OccurrenceSmall.model_validate(o).model_dump() for o in occurrences]
    return CameraDetail(**camera_data, last_occurrences=occ_list)


@router.put("/{camera_id}", response_model=CameraRead)
@router.patch("/{camera_id}", response_model=CameraRead)
def update_camera(
    camera_id: UUID,
    payload: CameraUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    camera = _get_camera_or_403(camera_id, current_user, db)
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(camera, k, v)
    db.commit()
    db.refresh(camera)
    return camera


@router.delete("/{camera_id}", status_code=204)
def delete_camera(
    camera_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    camera = _get_camera_or_403(camera_id, current_user, db)
    db.delete(camera)
    db.commit()


@router.post("/{camera_id}/test")
def test_camera_connection(
    camera_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    camera = _get_camera_or_403(camera_id, current_user, db)
    if camera.connection_type != "rtsp" or not camera.rtsp_url:
        raise HTTPException(status_code=400, detail="Teste disponível apenas para câmeras RTSP")
    frame = capture_rtsp_frame(camera.rtsp_url)
    if frame is None:
        raise HTTPException(status_code=503, detail="Não foi possível conectar à câmera RTSP")
    if camera.dual_lens and camera.lens_side in ("upper", "lower"):
        frame = crop_half_frame(frame, camera.lens_side)
    save_latest_frame(frame, str(camera.id))
    record_preview_frame(str(camera.id))
    record_image_quality(str(camera.id), frame)
    camera.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    maybe_publish_camera_health_alert(camera)
    return {
        "frame_base64": base64.b64encode(frame).decode(),
        "content_type": "image/jpeg",
    }


@router.get("/{camera_id}/token")
def get_camera_token(
    camera_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    camera = _get_camera_or_403(camera_id, current_user, db)
    return {"agent_token": camera.agent_token, "camera_id": str(camera_id)}


@router.get("/{camera_id}/last-frame")
def get_camera_last_frame(
    camera_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_camera_or_403(camera_id, current_user, db)
    latest_path = f"cameras/{camera_id}/latest.jpg"
    if latest_frame_exists(str(camera_id)):
        return {
            "image_url": f"{get_url(latest_path)}?t={int(datetime.now(timezone.utc).timestamp())}",
            "detected_at": None,
            "plate": None,
        }

    occ = (
        db.query(Occurrence)
        .filter(Occurrence.camera_id == camera_id, Occurrence.image_path.isnot(None))
        .order_by(Occurrence.detected_at.desc())
        .first()
    )
    if not occ or not occ.image_path:
        return {"image_url": None, "detected_at": None, "plate": None}
    return {
        "image_url": get_url(occ.image_path),
        "detected_at": occ.detected_at,
        "plate": occ.plate,
    }


@router.get("/{camera_id}/stream")
async def stream_camera(
    camera_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    camera = _get_camera_or_403(camera_id, current_user, db)
    boundary_headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "X-Accel-Buffering": "no",
    }

    async def frame_generator():
        latest_path = f"cameras/{camera_id}/latest.jpg"
        last_status_update = datetime.min.replace(tzinfo=timezone.utc)
        while True:
            image_bytes: bytes | None = None
            image_bytes = read_file_bytes(latest_path)
            if image_bytes is None and camera.connection_type == "rtsp":
                try:
                    image_bytes = await asyncio.to_thread(capture_rtsp_frame, camera.rtsp_url)
                    if image_bytes and camera.dual_lens and camera.lens_side in ("upper", "lower"):
                        image_bytes = await asyncio.to_thread(crop_half_frame, image_bytes, camera.lens_side)
                except Exception:
                    image_bytes = None

            if image_bytes:
                now = datetime.now(timezone.utc)
                if camera.connection_type == "rtsp" and now - last_status_update >= timedelta(seconds=30):
                    camera.last_seen_at = now
                    db.commit()
                    last_status_update = now
                record_preview_frame(str(camera.id))
                record_image_quality(str(camera.id), image_bytes)
                maybe_publish_camera_health_alert(camera)
                yield _multipart_frame(image_bytes)
            await asyncio.sleep(0.35)

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers=boundary_headers,
    )
