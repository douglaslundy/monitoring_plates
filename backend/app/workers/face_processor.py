"""Worker Celery para pipeline facial assíncrono.

Desacopla detecção/reconhecimento de faces do worker de frames, evitando que
YuNet + SFace (CPU-intensivos) bloqueiem o throughput da fila `frames`.

O worker de frames apenas enfileira tarefas aqui com apply_async(queue='faces');
este worker consome a fila `faces` de forma independente.
"""
from __future__ import annotations

import base64
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    from celery import Celery

    _celery_app = Celery(
        "face_processor", broker=settings.REDIS_URL, backend=settings.REDIS_URL
    )
    _celery_app.conf.task_routes = {"app.workers.face_processor.*": {"queue": "faces"}}

    @_celery_app.task(name="app.workers.face_processor.process_face")
    def process_face(
        camera_id: str,
        client_id: Optional[str],
        track_id: Optional[str],
        person_crop_b64: str,
        bbox: dict,
        image_path: Optional[str],
        expires_at_str: Optional[str],
    ) -> None:
        """Detecta e identifica o rosto de uma pessoa, grava FaceDetection e dispara alertas."""
        from app.services.face_detection_service import get_local_engine
        from app.services.face_service import face_recognizer, LOCAL_ENGINE_TYPES

        person_crop = base64.b64decode(person_crop_b64)

        engine_type = face_recognizer.resolve_engine_type(client_id)
        # Usa o motor configurado para detectar e gerar embedding
        eng = get_local_engine(engine_type) if engine_type in LOCAL_ENGINE_TYPES else get_local_engine("opencv")
        result = eng.detect_and_embed(person_crop)
        if result is None:
            logger.info(
                "face async camera=%s track=%s: motor=%s não encontrou rosto "
                "(pessoa %dx%d px) — ângulo/distância/iluminação inadequados",
                camera_id, track_id, engine_type, bbox.get("w", 0), bbox.get("h", 0),
            )
            return

        face_box, embedding = result

        # Identificação: motores locais usam embedding pré-computado;
        # motores de nuvem enviam a imagem do recorte.
        match: Optional[object] = None
        if engine_type in LOCAL_ENGINE_TYPES and embedding:
            match = face_recognizer.identify_by_embedding(client_id, embedding, engine_type)
        else:
            match = face_recognizer.identify(client_id or "", face_box.crop_bytes)

        if match:
            logger.info(
                "face async camera=%s track=%s: RECONHECIDO person_id=%s conf=%.3f engine=%s",
                camera_id, track_id, match.person_id, match.confidence, engine_type,
            )
        else:
            logger.info(
                "face async camera=%s track=%s: rosto %dx%d px detectado, NÃO reconhecido "
                "(cadastro ausente ou similaridade abaixo do limiar %.2f) engine=%s",
                camera_id, track_id, face_box.bbox_w, face_box.bbox_h,
                settings.FACE_MATCH_THRESHOLD, engine_type,
            )

        expires_at = None
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
            except ValueError:
                pass

        from app.core.database import SessionLocal
        from app.models.face_detection import FaceDetection

        # Sinaliza para o frame_processor que este track já teve rosto detectado,
        # evitando re-enfileirar nas próximas tentativas de retry.
        try:
            import redis as _rmod
            _rc = _rmod.from_url(settings.REDIS_URL, decode_responses=True)
            _rc.setex(f"face_ok:{camera_id}:{track_id}", 7200, "1")
        except Exception:
            pass

        db = SessionLocal()
        try:
            fd = FaceDetection(
                camera_id=uuid.UUID(camera_id),
                person_id=uuid.UUID(match.person_id) if match else None,
                confidence=match.confidence if match else None,
                image_path=image_path,
                bbox_x=bbox.get("x", 0),
                bbox_y=bbox.get("y", 0),
                bbox_w=bbox.get("w", 0),
                bbox_h=bbox.get("h", 0),
                track_id=track_id,
                expires_at=expires_at,
                face_engine_used=engine_type,
            )
            db.add(fd)
            db.commit()
            db.refresh(fd)

            if match:
                try:
                    from app.services.face_alert_service import process_face_alerts
                    process_face_alerts(str(fd.id), db)
                except Exception:
                    logger.warning("Alerta face conhecida falhou", exc_info=True)
            else:
                try:
                    from app.services.face_alert_service import process_unknown_face_alert
                    process_unknown_face_alert(str(fd.id), db)
                except Exception:
                    logger.warning("Alerta face desconhecida falhou", exc_info=True)
        finally:
            db.close()

except ImportError:
    logger.warning("celery não disponível — face_processor em modo degradado")

    def process_face(*_args, **_kwargs) -> None:  # type: ignore[misc]
        pass
