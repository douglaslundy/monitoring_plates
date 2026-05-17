import asyncio
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import decode_token
from app.models.user import User, UserRole
from app.websocket.manager import manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str,
    token: str = Query(...),
):
    db: Session = SessionLocal()
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=1008)
            return

        user = db.query(User).filter(User.id == UUID(user_id)).first()
        if not user or not user.is_active:
            await websocket.close(code=1008)
            return

        # Non-admins can only listen to their own client channel
        if user.role != UserRole.super_admin:
            if str(user.client_id) != client_id:
                await websocket.close(code=1008)
                return
    except (JWTError, ValueError):
        await websocket.close(code=1008)
        return
    finally:
        db.close()

    await manager.connect(client_id, websocket)
    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        manager.disconnect(client_id, websocket)
