from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.core.limiter import limiter
from app.core.security import verify_password, hash_password, create_access_token
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, TokenResponse, UserInToken, UserMe

router = APIRouter(prefix="/auth", tags=["auth"])


def _build_token_response(user: User) -> TokenResponse:
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserInToken(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role,
            client_id=user.client_id,
        ),
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Usuário inativo")
    return _build_token_response(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(current_user: User = Depends(get_current_user)) -> TokenResponse:
    return _build_token_response(current_user)


@router.get("/me", response_model=UserMe)
def me(current_user: User = Depends(get_current_user)) -> User:
    # SQLAlchemy lazy-loads .client and .client.plan while session is open
    return current_user


@router.post("/change-password", status_code=200)
def change_password(
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Senha atual incorreta")
    current_user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"message": "Senha alterada com sucesso"}
