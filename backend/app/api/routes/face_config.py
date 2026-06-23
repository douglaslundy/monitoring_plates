import uuid
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_super_admin
from app.models.face_engine_config import FaceEngineConfig, FaceEngineType
from app.schemas.face_engine_config import (
    FaceEngineConfigCreate,
    FaceEngineConfigRead,
    FaceEngineConfigUpdate,
    FaceEngineTestResult,
)

router = APIRouter(prefix="/face-config", tags=["face-config"])


@router.get("", response_model=List[FaceEngineConfigRead])
def list_configs(
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    return db.query(FaceEngineConfig).order_by(FaceEngineConfig.created_at).all()


@router.post("", response_model=FaceEngineConfigRead, status_code=201)
def create_config(
    payload: FaceEngineConfigCreate,
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    existing = (
        db.query(FaceEngineConfig)
        .filter(FaceEngineConfig.engine_type == payload.engine_type)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Configuração para {payload.engine_type} já existe. Use PATCH para atualizar.",
        )
    data = payload.model_dump()
    data["engine_type"] = data["engine_type"].value if hasattr(data["engine_type"], "value") else data["engine_type"]
    config = FaceEngineConfig(id=uuid.uuid4(), **data)
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@router.patch("/{config_id}", response_model=FaceEngineConfigRead)
def update_config(
    config_id: UUID,
    payload: FaceEngineConfigUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    config = db.query(FaceEngineConfig).filter(FaceEngineConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuração não encontrada")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(config, k, v)
    db.commit()
    db.refresh(config)
    return config


@router.delete("/{config_id}", status_code=204)
def delete_config(
    config_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    config = db.query(FaceEngineConfig).filter(FaceEngineConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuração não encontrada")
    db.delete(config)
    db.commit()


@router.post("/{config_id}/activate", response_model=FaceEngineConfigRead)
def toggle_activate(
    config_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    config = db.query(FaceEngineConfig).filter(FaceEngineConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuração não encontrada")
    config.is_active = not config.is_active
    db.commit()
    db.refresh(config)
    return config


@router.post("/{config_id}/test", response_model=FaceEngineTestResult)
def test_config(
    config_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    config = db.query(FaceEngineConfig).filter(FaceEngineConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuração não encontrada")

    if config.engine_type == FaceEngineType.opencv.value:
        return FaceEngineTestResult(
            success=True,
            engine_type=config.engine_type,
            message="Motor local (OpenCV) não requer credenciais externas. Configuração válida.",
        )

    try:
        if config.engine_type == FaceEngineType.rekognition.value:
            if not config.api_token or not config.api_secret:
                return FaceEngineTestResult(success=False, engine_type=config.engine_type, message="Access key e secret são obrigatórios.")
            import boto3

            client = boto3.client(
                "rekognition",
                aws_access_key_id=config.api_token,
                aws_secret_access_key=config.api_secret,
                region_name=config.region or "us-east-1",
            )
            client.list_collections(MaxResults=1)
            return FaceEngineTestResult(success=True, engine_type=config.engine_type, message="Credenciais AWS válidas.")

        if config.engine_type == FaceEngineType.luxand.value:
            if not config.api_token:
                return FaceEngineTestResult(success=False, engine_type=config.engine_type, message="Token Luxand é obrigatório.")
            import requests

            base = (config.api_url or "https://api.luxand.cloud").rstrip("/")
            resp = requests.get(f"{base}/v2/person", headers={"token": config.api_token}, timeout=10)
            ok = resp.status_code < 400
            return FaceEngineTestResult(success=ok, engine_type=config.engine_type, message="Credenciais Luxand válidas." if ok else f"Falha: HTTP {resp.status_code}")

        if config.engine_type == FaceEngineType.facepp.value:
            if not config.api_token or not config.api_secret:
                return FaceEngineTestResult(success=False, engine_type=config.engine_type, message="API key e secret são obrigatórios.")
            import requests

            base = (config.api_url or "https://api-us.faceplusplus.com").rstrip("/")
            resp = requests.post(
                f"{base}/facepp/v3/faceset/getfacesets",
                data={"api_key": config.api_token, "api_secret": config.api_secret},
                timeout=10,
            )
            ok = resp.status_code < 400
            return FaceEngineTestResult(success=ok, engine_type=config.engine_type, message="Credenciais Face++ válidas." if ok else f"Falha: HTTP {resp.status_code}")
    except Exception as e:
        return FaceEngineTestResult(success=False, engine_type=config.engine_type, message=f"Erro ao conectar: {str(e)}")

    return FaceEngineTestResult(success=False, engine_type=config.engine_type, message="Motor desconhecido.")


@router.post("/test-image")
async def test_image(
    file: UploadFile = File(...),
    camera_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    """Detecta e identifica rostos, retorna imagem anotada com bboxes e dispara alertas reais.

    Passa `camera_id` (UUID) para também disparar alerta de face desconhecida
    quando configurado nessa câmera.
    """
    from datetime import datetime, timezone
    from app.services.face_detection_service import face_engine
    from app.services.face_service import face_recognizer
    from app.services.detection_overlay_service import draw_labeled_boxes
    from app.models.person import Person
    from app.models.camera import Camera
    from app.models.face_detection import FaceDetection
    from app.models.face_camera_alert_config import FaceCameraAlertConfig

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")

    face_boxes = face_engine.detect(image_bytes)
    if not face_boxes:
        return {
            "found": False,
            "message": "Nenhum rosto detectado na imagem pelo motor local (YuNet).",
            "faces": [],
            "annotated_image": None,
            "alerts_fired": [],
        }

    # Câmeras com alerta de face desconhecida ativo
    # Se camera_id informado: usa só essa câmera; caso contrário: todas com unknown_face_active
    alert_cameras: list[Camera] = []
    if camera_id:
        try:
            cam = db.query(Camera).filter(Camera.id == uuid.UUID(camera_id)).first()
            if cam:
                alert_cameras = [cam]
        except Exception:
            pass
    else:
        cfg_rows = (
            db.query(FaceCameraAlertConfig)
            .filter(FaceCameraAlertConfig.unknown_face_active.is_(True))
            .all()
        )
        cam_ids = [row.camera_id for row in cfg_rows]
        if cam_ids:
            alert_cameras = db.query(Camera).filter(Camera.id.in_(cam_ids)).all()

    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M:%S")
    faces = []
    boxes_for_draw: list[dict] = []
    alerts_fired: list[str] = []

    for box in face_boxes:
        match = face_recognizer.identify_all(box.crop_bytes)
        person: Person | None = None
        person_info = None

        if match:
            person = db.query(Person).filter(Person.id == uuid.UUID(match.person_id)).first()
            if person:
                person_info = {
                    "id": str(person.id),
                    "name": person.name,
                    "alert_active": person.alert_active,
                    "has_email": bool(person.alert_email),
                    "has_whatsapp": bool(person.alert_whatsapp),
                }

        label = person.name if person else "Desconhecida"
        boxes_for_draw.append({
            "x": box.bbox_x, "y": box.bbox_y, "w": box.bbox_w, "h": box.bbox_h,
            "label": label,
            "highlight": bool(person and person.alert_active),
        })

        # Alerta para pessoa CONHECIDA com alerta ativo
        if person and person.alert_active:
            if person.alert_email:
                try:
                    from app.services.face_alert_service import _send_test_face_alert_email
                    _send_test_face_alert_email(person, now_str)
                    alerts_fired.append(f"email:{person.alert_email}")
                except Exception:
                    pass
            if person.alert_whatsapp:
                try:
                    from app.services.face_alert_service import _send_test_face_alert_whatsapp
                    _send_test_face_alert_whatsapp(person, image_bytes, now_str, db)
                    alerts_fired.append(f"whatsapp:{person.alert_whatsapp}")
                except Exception:
                    pass

        # Alerta de face DESCONHECIDA: dispara para todas as câmeras configuradas
        if person is None and alert_cameras:
            from app.services.face_alert_service import process_unknown_face_alert
            for cam in alert_cameras:
                try:
                    fd = FaceDetection(
                        camera_id=cam.id,
                        person_id=None,
                        confidence=None,
                        image_path=None,
                        bbox_x=box.bbox_x,
                        bbox_y=box.bbox_y,
                        bbox_w=box.bbox_w,
                        bbox_h=box.bbox_h,
                        track_id="test",
                        face_engine_used="opencv",
                    )
                    db.add(fd)
                    db.flush()
                    process_unknown_face_alert(str(fd.id), db)
                    alerts_fired.append(f"unknown_face:camera={cam.name}")
                except Exception:
                    pass

        faces.append({
            "bbox": {"x": box.bbox_x, "y": box.bbox_y, "w": box.bbox_w, "h": box.bbox_h},
            "confidence": box.confidence,
            "match": {
                "person_id": match.person_id if match else None,
                "match_confidence": match.confidence if match else None,
                "person": person_info,
            },
        })

    db.commit()
    recognized = [f for f in faces if f["match"]["person_id"]]
    annotated_image = draw_labeled_boxes(image_bytes, boxes_for_draw)

    return {
        "found": True,
        "message": f"{len(faces)} rosto(s) detectado(s), {len(recognized)} reconhecido(s).",
        "faces": faces,
        "annotated_image": annotated_image or None,
        "alerts_fired": alerts_fired,
    }
