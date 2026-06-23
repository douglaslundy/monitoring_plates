import uuid
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
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
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    """Executa detecção e identificação facial em imagem enviada (sem salvar no banco).
    Útil para verificar se o motor de faces está funcionando corretamente."""
    from app.services.face_detection_service import face_engine
    from app.services.face_service import face_recognizer
    from app.models.person import Person

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")

    # Detecta rostos na imagem
    face_boxes = face_engine.detect(image_bytes)
    if not face_boxes:
        return {
            "found": False,
            "message": "Nenhum rosto detectado na imagem pelo motor local (YuNet).",
            "faces": [],
        }

    faces = []
    for box in face_boxes:
        # Tenta identificar (usa motor do sistema — fallback p/ local)
        match = face_recognizer.identify("__test__", box.crop_bytes)
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

        faces.append({
            "bbox": {
                "x": box.bbox_x, "y": box.bbox_y,
                "w": box.bbox_w, "h": box.bbox_h,
            },
            "confidence": box.confidence,
            "match": {
                "person_id": match.person_id if match else None,
                "match_confidence": match.confidence if match else None,
                "person": person_info,
            } if match else {"person_id": None, "match_confidence": None, "person": None},
        })

    recognized = [f for f in faces if f["match"]["person_id"]]
    return {
        "found": True,
        "message": f"{len(faces)} rosto(s) detectado(s), {len(recognized)} reconhecido(s).",
        "faces": faces,
    }
