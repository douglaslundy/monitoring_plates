import uuid
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
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

    if config.engine_type == OcrEngineType.easyocr:
        return OcrEngineTestResult(
            success=True,
            engine_type=OcrEngineType.easyocr,
            message="EasyOCR não requer credenciais externas. Configuração válida.",
        )

    # Plate Recognizer — testa credenciais com uma chamada real
    if not config.api_token or not config.api_url:
        return OcrEngineTestResult(
            success=False,
            engine_type=OcrEngineType.plate_recognizer,
            message="API Token e URL são obrigatórios para o Plate Recognizer.",
        )

    import requests as req

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
