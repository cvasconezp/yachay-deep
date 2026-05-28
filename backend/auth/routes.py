"""
Auth routes — [SEC-02] Fase 2: HttpOnly cookie JWT.
Login SET-COOKIE HttpOnly+Secure+SameSite. Logout borra cookie.
Bearer header sigue funcionando como fallback (API consumers).
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..config import settings
from ..database import get_db
from ..models.user import User, UserRole
from .jwt import verify_password, create_access_token, hash_password, get_current_user, require_admin, COOKIE_NAME

import logging
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict


class UserCreate(BaseModel):
    email: EmailStr
    nombre: str
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole = UserRole.monitor
    permissions: Optional[list[str]] = None  # tabs permitidos: ["dashboard","alertas",...]
    send_welcome_email: bool = True


class UserUpdate(BaseModel):
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None
    nombre: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)
    permissions: Optional[list[str]] = None


class UserResponse(BaseModel):
    id: int
    email: str
    nombre: str
    role: str
    is_active: bool
    created_at: Optional[datetime]
    permissions: Optional[list[str]] = None
    has_pin: bool = False

    class Config:
        from_attributes = True


@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """[SEC-02] Login con HttpOnly cookie + Bearer token (backward compat)."""
    user = db.query(User).filter(User.email == form_data.username.lower()).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        safe_email = form_data.username.lower().replace('\n', '').replace('\r', '')[:100]
        logger.warning("Login fallido para email: %s", safe_email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Usuario desactivado")

    user.last_login = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token({"sub": str(user.id)})

    # [SEC-02] Respuesta con HttpOnly cookie + token en body (backward compat)
    response = JSONResponse(content={
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "nombre": user.nombre, "role": user.role, "permissions": user.permissions, "has_pin": user.pin_hash is not None},
    })
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    return response


@router.post("/logout")
def logout():
    """[SEC-02] Borra la HttpOnly cookie."""
    response = JSONResponse(content={"detail": "Sesión cerrada"})
    response.delete_cookie(key=COOKIE_NAME, path="/", domain=settings.COOKIE_DOMAIN)
    return response


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    # Build response with computed has_pin field
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        nombre=current_user.nombre,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        permissions=current_user.permissions,
        has_pin=current_user.pin_hash is not None,
    )


@router.post("/users", response_model=UserResponse, dependencies=[Depends(require_admin)])
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    user = User(
        email=payload.email.lower(),
        nombre=payload.nombre,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        permissions=payload.permissions,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Enviar email de bienvenida
    if payload.send_welcome_email:
        try:
            from ..services.email import send_welcome_email
            send_welcome_email(
                to_email=user.email,
                nombre=user.nombre,
                role=user.role,
                password=payload.password,
                permissions=user.permissions,
            )
        except Exception as e:
            logger.warning(f"No se pudo enviar email de bienvenida: {e}")

    return user


@router.get("/users", response_model=list[UserResponse], dependencies=[Depends(require_admin)])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).all()


@router.patch("/users/{user_id}", response_model=UserResponse, dependencies=[Depends(require_admin)])
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    updates = payload.model_dump(exclude_unset=True)
    if "is_active" in updates:
        user.is_active = updates["is_active"]
    if "role" in updates:
        user.role = updates["role"]
    if "nombre" in updates:
        user.nombre = updates["nombre"]
    if "password" in updates:
        user.hashed_password = hash_password(updates["password"])
    if "permissions" in updates:
        user.permissions = updates["permissions"]
    db.commit()
    db.refresh(user)
    return user


# ── PIN de desbloqueo rápido ─────────────────────────────────────────────

class PinSetRequest(BaseModel):
    pin: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    password: str  # requiere contraseña actual para configurar PIN


class PinVerifyRequest(BaseModel):
    pin: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


@router.post("/set-pin")
def set_pin(
    payload: PinSetRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Configura o actualiza el PIN de desbloqueo. Requiere contraseña actual."""
    if not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Contraseña incorrecta")

    current_user.pin_hash = hash_password(payload.pin)
    db.commit()
    return {"detail": "PIN configurado correctamente"}


@router.post("/verify-pin")
@limiter.limit("5/minute")
def verify_pin(
    request: Request,
    payload: PinVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verifica el PIN para desbloqueo rápido. Rate limited a 5/min."""
    if not current_user.pin_hash:
        raise HTTPException(status_code=400, detail="PIN no configurado")

    if not verify_password(payload.pin, current_user.pin_hash):
        raise HTTPException(status_code=401, detail="PIN incorrecto")

    return {"detail": "PIN verificado", "valid": True}


@router.delete("/pin")
def remove_pin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Elimina el PIN configurado."""
    current_user.pin_hash = None
    db.commit()
    return {"detail": "PIN eliminado"}
