from celery import Celery
from celery.schedules import crontab
from datetime import timedelta
from app.core.config import settings

celery_app = Celery("retention_cleaner", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery_app.conf.beat_schedule = {
    "clean-old-occurrences": {
        "task": "app.workers.retention_cleaner.clean_old_occurrences",
        "schedule": crontab(hour=2, minute=0),
    },
    "poll-rtsp-cameras": {
        "task": "app.workers.frame_processor.poll_rtsp_cameras",
        "schedule": timedelta(seconds=1),
        "options": {"queue": "frames"},
    },
}


@celery_app.task(name="app.workers.retention_cleaner.clean_old_occurrences")
def clean_old_occurrences() -> None:
    from datetime import datetime, timezone

    from app.core.database import SessionLocal
    from app.models.occurrence import Occurrence
    from app.services.storage_service import delete_file

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        expired = (
            db.query(Occurrence)
            .filter(
                Occurrence.expires_at.isnot(None),
                Occurrence.expires_at < now,
            )
            .all()
        )
        for occ in expired:
            if occ.image_path:
                delete_file(occ.image_path)
            db.delete(occ)

        if expired:
            print(f"[retention] deleted={len(expired)}")
        db.commit()
    finally:
        db.close()
