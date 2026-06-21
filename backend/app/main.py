import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.limiter import limiter
from app.api.deps import get_db, get_current_user
from app.api.routes import auth, users, clients, cameras, occurrences, plates, alerts, plans, agent, ocr_config, vehicles, ops, detector, whatsapp_settings, persons, face_config, face_detections
from app.api.routes.ws import router as ws_router
from app.models.camera import Camera
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


async def _redis_subscriber() -> None:
    """Relay Redis pub/sub plate alerts to connected WebSocket clients."""
    from app.websocket.manager import manager

    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.REDIS_URL)
        pubsub = r.pubsub()
        await pubsub.psubscribe("ws:alerts:*")
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                channel: str = message["channel"].decode()
                client_id = channel.split(":")[-1]
                data = json.loads(message["data"])
                await manager.broadcast_to_client(client_id, data)
    except Exception:
        logger.warning("Redis subscriber stopped", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import os

    if not os.getenv("IS_TESTING"):
        from app.core.seed import run as seed

        seed()
        asyncio.create_task(_redis_subscriber())

        # Registra as câmeras RTSP no go2rtc para o live WebRTC (best-effort).
        try:
            from app.core.database import SessionLocal
            from app.services.go2rtc_service import sync_streams

            db = SessionLocal()
            try:
                sync_streams(db)
            finally:
                db.close()
        except Exception:
            logger.warning("Falha ao sincronizar streams no go2rtc", exc_info=True)
    yield


app = FastAPI(
    title="Monitoramento de Trânsito",
    description="API para sistema SaaS de monitoramento com reconhecimento de placas",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=True,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/images/{path:path}", tags=["images"])
def serve_image(
    path: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    parts = path.split("/")
    if len(parts) < 2 or parts[0] != "cameras":
        raise HTTPException(status_code=404, detail="Imagem não encontrada")

    try:
        camera_id = UUID(parts[1])
    except ValueError:
        raise HTTPException(status_code=404, detail="Imagem não encontrada")

    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    if current_user.role != UserRole.super_admin and camera.client_id != current_user.client_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    full_path = Path(settings.STORAGE_PATH) / path
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    return FileResponse(str(full_path), media_type="image/jpeg")


app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(clients.router, prefix="/api")
app.include_router(cameras.router, prefix="/api")
app.include_router(occurrences.router, prefix="/api")
app.include_router(plates.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(plans.router, prefix="/api")
app.include_router(agent.router, prefix="/api")
app.include_router(ocr_config.router, prefix="/api")
app.include_router(vehicles.router, prefix="/api")
app.include_router(ops.router, prefix="/api")
app.include_router(detector.router, prefix="/api")
app.include_router(whatsapp_settings.router, prefix="/api")
app.include_router(persons.router, prefix="/api")
app.include_router(face_config.router, prefix="/api")
app.include_router(face_detections.router, prefix="/api")
app.include_router(ws_router, prefix="/api")
