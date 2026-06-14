import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings


def save_bytes(image_bytes: bytes, camera_id: str) -> str:
    """Synchronous save for Celery workers. Returns relative path."""
    if settings.STORAGE_TYPE == "s3":
        return _save_bytes_s3(image_bytes, camera_id)
    return _save_bytes_local(image_bytes, camera_id)


def _save_bytes_local(image_bytes: bytes, camera_id: str) -> str:
    now = datetime.now(timezone.utc)
    relative = f"cameras/{camera_id}/{now.year}/{now.month:02d}/{now.day:02d}"
    full_dir = Path(settings.STORAGE_PATH) / relative
    full_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.jpg"
    (full_dir / filename).write_bytes(image_bytes)
    return str(Path(relative) / filename)


def _save_bytes_s3(image_bytes: bytes, camera_id: str) -> str:
    import boto3

    s3 = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT or None,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )
    now = datetime.now(timezone.utc)
    key = f"cameras/{camera_id}/{now.strftime('%Y/%m/%d')}/{uuid.uuid4().hex}.jpg"
    s3.put_object(
        Bucket=settings.S3_BUCKET,
        Key=key,
        Body=image_bytes,
        ContentType="image/jpeg",
    )
    return key


def get_url(path: str) -> str:
    if settings.STORAGE_TYPE == "s3":
        base = settings.S3_ENDPOINT.rstrip("/") if settings.S3_ENDPOINT else ""
        return f"{base}/{settings.S3_BUCKET}/{path}"
    return f"/api/images/{path}"


def save_latest_frame(image_bytes: bytes, camera_id: str) -> str:
    """Store/overwrite latest agent frame for quick live preview."""
    if settings.STORAGE_TYPE == "s3":
        return _save_latest_frame_s3(image_bytes, camera_id)
    return _save_latest_frame_local(image_bytes, camera_id)


def _save_latest_frame_local(image_bytes: bytes, camera_id: str) -> str:
    relative = f"cameras/{camera_id}/latest.jpg"
    full = Path(settings.STORAGE_PATH) / relative
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(image_bytes)
    return relative


def _save_latest_frame_s3(image_bytes: bytes, camera_id: str) -> str:
    import boto3

    s3 = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT or None,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )
    key = f"cameras/{camera_id}/latest.jpg"
    s3.put_object(
        Bucket=settings.S3_BUCKET,
        Key=key,
        Body=image_bytes,
        ContentType="image/jpeg",
        CacheControl="no-cache, no-store, must-revalidate",
    )
    return key


def latest_frame_exists(camera_id: str) -> bool:
    if settings.STORAGE_TYPE == "s3":
        return True
    full = Path(settings.STORAGE_PATH) / f"cameras/{camera_id}/latest.jpg"
    return full.exists()


def read_file_bytes(path: str) -> bytes | None:
    if settings.STORAGE_TYPE == "s3":
        import boto3

        s3 = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT or None,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
        )
        try:
            obj = s3.get_object(Bucket=settings.S3_BUCKET, Key=path)
        except Exception:
            return None
        return obj["Body"].read()

    full = Path(settings.STORAGE_PATH) / path
    if not full.exists():
        return None
    return full.read_bytes()


def delete_file(path: str) -> None:
    if settings.STORAGE_TYPE == "local":
        full = Path(settings.STORAGE_PATH) / path
        if full.exists():
            full.unlink()


# ── Async versions for UploadFile-based agent endpoints ──────────────────────

async def save_frame(image: UploadFile, camera_id: str) -> str:
    contents = await image.read()
    return save_bytes(contents, camera_id)
