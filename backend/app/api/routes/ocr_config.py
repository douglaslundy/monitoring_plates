import uuid
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
import requests as req
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_super_admin
from app.models.ocr_engine_config import OcrEngineConfig, OcrEngineType
from app.schemas.ocr_engine_config import (
    OcrEngineConfigCreate,
    OcrEngineConfigRead,
    OcrEngineConfigUpdate,
    OcrEngineTestResult,
)

router = APIRouter(prefix="/ocr-config", tags=["ocr-config"])


@router.get("", response_model=List[OcrEngineConfigRead])
def list_configs(
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    return db.query(OcrEngineConfig).order_by(OcrEngineConfig.created_at).all()


@router.post("", response_model=OcrEngineConfigRead, status_code=201)
def create_config(
    payload: OcrEngineConfigCreate,
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    existing = (
        db.query(OcrEngineConfig)
        .filter(OcrEngineConfig.engine_type == payload.engine_type)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Configuração para {payload.engine_type} já existe. Use PATCH para atualizar.",
        )

    data = payload.model_dump()
    config = OcrEngineConfig(id=uuid.uuid4(), **data)
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@router.patch("/{config_id}", response_model=OcrEngineConfigRead)
def update_config(
    config_id: UUID,
    payload: OcrEngineConfigUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    config = db.query(OcrEngineConfig).filter(OcrEngineConfig.id == config_id).first()
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
    config = db.query(OcrEngineConfig).filter(OcrEngineConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuração não encontrada")
    db.delete(config)
    db.commit()


@router.post("/{config_id}/activate", response_model=OcrEngineConfigRead)
def toggle_activate(
    config_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    config = db.query(OcrEngineConfig).filter(OcrEngineConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuração não encontrada")

    config.is_active = not config.is_active
    # Ativação EXCLUSIVA: só um motor OCR ativo por vez. Ao ativar este, desativa
    # os demais — antes podiam ficar dois "ativos" (ex.: o local + o cadastrado),
    # parecendo um motor a mais além do que o usuário ativou.
    if config.is_active:
        db.query(OcrEngineConfig).filter(OcrEngineConfig.id != config.id).update(
            {OcrEngineConfig.is_active: False}, synchronize_session=False
        )
    db.commit()
    db.refresh(config)
    return config


@router.post("/{config_id}/test", response_model=OcrEngineTestResult)
async def test_config(
    config_id: UUID,
    sample_image: UploadFile = File(None),
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    config = db.query(OcrEngineConfig).filter(OcrEngineConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuração não encontrada")

    if config.engine_type in (OcrEngineType.fast_alpr, OcrEngineType.easyocr):
        return OcrEngineTestResult(
            success=True,
            engine_type=config.engine_type,
            message="Motor local (fast-alpr) não requer credenciais externas. Configuração válida.",
        )

    # Plate Recognizer — testa credenciais com uma chamada real
    if not config.api_token or not config.api_url:
        return OcrEngineTestResult(
            success=False,
            engine_type=OcrEngineType.plate_recognizer,
            message="API Token e URL são obrigatórios para o Plate Recognizer.",
        )

    try:
        if sample_image:
            image_bytes = await sample_image.read()
        else:
            # Imagem 1x1 pixel branca para testar autenticação
            image_bytes = (
                b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
                b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
                b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
                b"\x1f\x1e\x1d\x1a\x1c\x1c $.\' \",#\x1c\x1c(7),01444\x1f\'9=82<.342\x1e"
                b"\x1e\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4"
                b"\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4"
                b"\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00"
                b"\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07\"q\x142"
                b"\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18"
                b"\x19\x1a%&\'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85"
                b"\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3"
                b"\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba"
                b"\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8"
                b"\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4"
                b"\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfb"
                b"\xd4P\x00\x00\x00\x00\x1f\xff\xd9"
            )

        response = req.post(
            config.api_url.rstrip("/") + "/",
            headers={"Authorization": f"Token {config.api_token}"},
            files={"upload": ("test.jpg", image_bytes, "image/jpeg")},
            data={"regions": (config.regions or ["br"])},
            timeout=10,
        )

        if response.status_code == 403:
            return OcrEngineTestResult(
                success=False,
                engine_type=OcrEngineType.plate_recognizer,
                message="Token inválido ou créditos insuficientes (HTTP 403).",
            )

        if response.status_code in (200, 201):
            return OcrEngineTestResult(
                success=True,
                engine_type=OcrEngineType.plate_recognizer,
                message="Conexão estabelecida com sucesso. Credenciais válidas.",
                sample_response=response.json(),
            )

        return OcrEngineTestResult(
            success=False,
            engine_type=OcrEngineType.plate_recognizer,
            message=f"Resposta inesperada: HTTP {response.status_code}",
        )

    except Exception as e:
        return OcrEngineTestResult(
            success=False,
            engine_type=OcrEngineType.plate_recognizer,
            message=f"Erro ao conectar: {str(e)}",
        )


@router.post("/test-image")
async def test_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    """Executa OCR em uma imagem enviada pelo usuário (sem salvar no banco).
    Útil para diagnosticar se o motor está lendo placas corretamente."""
    from app.services.ocr_service import recognizer
    from app.services.vehicle_detection_service import vehicle_detector
    from app.models.monitored_plate import MonitoredPlate

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")

    # Detecta veículos no frame
    detections = vehicle_detector.detect(image_bytes)
    if not detections:
        return {"found": False, "message": "Nenhum veículo detectado na imagem.", "results": []}

    results = []
    for det in detections:
        if det.category != "vehicle":
            continue
        ocr_result = recognizer.recognize(det.crop_bytes, camera_id=None)
        if ocr_result is None:
            results.append({
                "category": det.category,
                "vehicle_type": det.vehicle_type,
                "confidence": det.confidence,
                "plate": None,
                "ocr_confidence": None,
                "alert": None,
            })
            continue

        plate = ocr_result.get("plate")
        # Verifica se a placa está monitorada (sem salvar alerta)
        alert_info = None
        if plate:
            monitored = (
                db.query(MonitoredPlate)
                .filter(MonitoredPlate.plate == plate, MonitoredPlate.is_active == True)  # noqa: E712
                .first()
            )
            if monitored:
                alert_info = {
                    "monitored": True,
                    "description": monitored.description,
                    "has_email": bool(monitored.alert_email),
                    "has_whatsapp": bool(monitored.alert_whatsapp),
                }

        results.append({
            "category": det.category,
            "vehicle_type": det.vehicle_type,
            "confidence": det.confidence,
            "plate": plate,
            "ocr_confidence": ocr_result.get("confidence"),
            "engine": ocr_result.get("engine"),
            "alert": alert_info,
        })

    return {
        "found": any(r["plate"] for r in results),
        "message": f"{len(results)} veículo(s) detectado(s).",
        "results": results,
    }
