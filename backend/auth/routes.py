from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

from ..database import get_db
from ..models.user import User, UserRole
from .jwt import verify_password, create_access_token, hash_password, get_current_user, require_admin

import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict


class UserCreate(BaseModel):
    email: EmailStr
    nombre: str
    password: str
    role: UserRole = UserRole.monitor


class UserUpdate(BaseModel):
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None
    nombre: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)


class UserResponse(BaseModel):
    id: int
    email: str
    nombre: str
    role: str
    is_active: bool
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username.lower()).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning(f"Login fallido para email: {form_data.username.lower()}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Usuario desactivado")

    user.last_login = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token({"sub": str(user.id)})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "nombre": user.nombre, "role": user.role},
    }


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/users", response_model=UserResponse, dependencies=[Depends(require_admin)])
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    user = User(
        email=payload.email.lower(),
        nombre=payload.nombre,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
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
    db.commit()
    db.refresh(user)
    return user
