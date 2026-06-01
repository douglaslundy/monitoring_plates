import base64
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Header
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.camera import Camera
from app.models.occurrence import Occurrence
from app.services.camera_service import crop_half_frame
from app.services.storage_service import save_latest_frame

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/heartbeat")
def heartbeat(
    agent_token: str = Form(...),
    db: Session = Depends(get_db),
):
    camera = db.query(Camera).filter(Camera.agent_token == agent_token).first()
    if not camera:
        raise HTTPException(status_code=401, detail="Token inválido")
    camera.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "ok", "camera_id": str(camera.id)}


@router.post("/upload")
async def upload_frame(
    agent_token: str = Form(...),
    plate: str = Form(...),
    confidence: float = Form(...),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    camera = db.query(Camera).filter(Camera.agent_token == agent_token).first()
    if not camera or not camera.is_active:
        raise HTTPException(status_code=401, detail="Token inválido ou câmera inativa")

    image_path = ""
    if image:
        from app.services.storage_service import save_frame
        image_path = await save_frame(image, str(camera.id))

    occ = Occurrence(
        camera_id=camera.id,
        plate=plate.upper().strip(),
        confidence=confidence,
        image_path=image_path,
    )
    db.add(occ)
    camera.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(occ)

    from app.workers.frame_processor import check_alerts
    check_alerts.delay(str(occ.id))

    return {"occurrence_id": str(occ.id)}


@router.post("/frame")
async def receive_frame(
    frame: UploadFile = File(...),
    authorization: str = Header(...),
    db: Session = Depends(get_db),
):
    """Receive a raw JPEG frame from a local agent identified by Bearer token."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token inválido")
    agent_token = authorization[7:]

    camera = db.query(Camera).filter(Camera.agent_token == agent_token).first()
    if not camera or not camera.is_active:
        raise HTTPException(status_code=401, detail="Token inválido ou câmera inativa")

    frame_bytes = await frame.read()
    if camera.dual_lens and camera.lens_side in ("upper", "lower"):
        frame_bytes = crop_half_frame(frame_bytes, camera.lens_side)
    save_latest_frame(frame_bytes, str(camera.id))
    camera.last_seen_at = datetime.now(timezone.utc)
    db.commit()

    from app.workers.frame_processor import process_frame
    process_frame.delay(str(camera.id), base64.b64encode(frame_bytes).decode())

    return {"received": True, "camera_id": str(camera.id)}
