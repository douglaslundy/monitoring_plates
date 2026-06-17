from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery("retention_cleaner", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

# A captura RTSP deixou de ser um poll de 1s (que reabria a conexão a cada tick)
# e passou a ser feita pelo capture-runner (conexão persistente + motion gating).
celery_app.conf.beat_schedule = {
    "clean-old-occurrences": {
        "task": "app.workers.retention_cleaner.clean_old_occurrences",
        "schedule": crontab(hour=2, minute=0),
    },
}


@celery_app.task(name="app.workers.retention_cleaner.clean_old_occurrences")
def clean_old_occurrences() -> None:
    """Limpa ocorrências (placas) E detecções (vehicle_events) vencidas.

    A retenção segue o plano do cliente da câmera:
    - Ocorrências: `expires_at` (definido na criação pelo plano) < agora.
    - Detecções: `detected_at` mais antigo que `retention_days` do plano.
    Planos sem `retention_days` (ilimitado) não expiram. O arquivo de imagem só
    é apagado quando NENHUMA linha remanescente o referencia (ocorrência e evento
    podem compartilhar o mesmo frame salvo).
    """
    from datetime import datetime, timedelta, timezone

    from app.core.database import SessionLocal
    from app.models.camera import Camera
    from app.models.client import Client
    from app.models.occurrence import Occurrence
    from app.models.plan import Plan
    from app.models.vehicle_event import VehicleEvent
    from app.services.storage_service import delete_file

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # 1. Ocorrências (placas) vencidas.
        expired_occ = (
            db.query(Occurrence)
            .filter(Occurrence.expires_at.isnot(None), Occurrence.expires_at < now)
            .all()
        )

        # 2. Detecções vencidas — retenção pelo plano do cliente de cada câmera.
        retention_by_camera = (
            db.query(Camera.id, Plan.retention_days)
            .join(Client, Camera.client_id == Client.id)
            .join(Plan, Client.plan_id == Plan.id)
            .all()
        )
        expired_events: list = []
        for cam_id, retention_days in retention_by_camera:
            if not retention_days:  # None/0 = ilimitado
                continue
            cutoff = now - timedelta(days=int(retention_days))
            expired_events.extend(
                db.query(VehicleEvent)
                .filter(VehicleEvent.camera_id == cam_id, VehicleEvent.detected_at < cutoff)
                .all()
            )

        image_paths: set[str] = set()
        for row in (*expired_occ, *expired_events):
            if row.image_path:
                image_paths.add(row.image_path)
            db.delete(row)
        db.flush()

        # 3. Apaga o arquivo só se nenhuma linha remanescente ainda o referencia.
        for path in image_paths:
            still_used = (
                db.query(Occurrence.id).filter(Occurrence.image_path == path).first()
                or db.query(VehicleEvent.id).filter(VehicleEvent.image_path == path).first()
            )
            if not still_used:
                delete_file(path)

        if expired_occ or expired_events:
            print(f"[retention] occurrences={len(expired_occ)} events={len(expired_events)}")
        db.commit()
    finally:
        db.close()
