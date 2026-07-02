"""
JWT utilities para Yachay Deep.

[SEC-02] Fase 2: Soporta token desde HttpOnly cookie ('yd_token')
         ademas del header Authorization: Bearer (backward compat).
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_prod_db
from ..models.user import User

# [WF1B] argon2id por defecto; bcrypt aceptado para verificar hashes antiguos.
# deprecated="auto" marca los esquemas viejos para rehash transparente en login.
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
    argon2__time_cost=3,
    argon2__memory_cost=65536,  # 64 MB
    argon2__parallelism=4,
)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

COOKIE_NAME = "yd_token"
REFRESH_COOKIE_NAME = "yd_refresh"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def needs_rehash(hashed: str) -> bool:
    """True si el hash usa un esquema obsoleto (ej. bcrypt) y debe regenerarse."""
    return pwd_context.needs_update(hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """[WF4] Refresh token JWT. Debe incluir 'jti' en data para poder revocarlo."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    """Decodifica y valida firma/exp. Lanza JWTError si es inválido."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def _extract_token(request: Request, bearer_token: Optional[str]) -> Optional[str]:
    """
    [SEC-02] Extrae token JWT con prioridad:
      1. HttpOnly cookie 'yd_token' (mas seguro, inmune a XSS)
      2. Header Authorization: Bearer (backward compat para API consumers)
    """
    cookie_token = request.cookies.get(COOKIE_NAME)
    if cookie_token:
        return cookie_token
    if bearer_token:
        return bearer_token
    return None


def get_current_user(
    request: Request,
    bearer_token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_prod_db),  # always production — JWT IDs are from production
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autenticado",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = _extract_token(request, bearer_token)
    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") == "refresh":
            # un refresh token no sirve para autenticar peticiones
            raise credentials_exception
        sub = payload.get("sub")
        if sub is None:
            raise credentials_exception
        user_id: int = int(sub)
    except (JWTError, ValueError, TypeError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if user is None:
        raise credentials_exception

    # [WF3] Enrolamiento 2FA obligatorio: si REQUIRE_2FA está activo y el usuario
    # no tiene 2FA, solo se le permiten las rutas de enrolamiento/sesión. El resto
    # devuelve 403 2FA_ENROLLMENT_REQUIRED para forzar la configuración primero.
    if settings.REQUIRE_2FA and not getattr(user, "totp_enabled", False):
        path = request.url.path
        _allowed = ("/auth/2fa", "/auth/me", "/auth/logout")
        if not any(path.startswith(p) for p in _allowed):
            raise HTTPException(status_code=403, detail="2FA_ENROLLMENT_REQUIRED")

    # [SEC-03] Bloqueo por PIN enforced en servidor: si la sesión está bloqueada,
    # solo se permiten las rutas de desbloqueo/sesión; el resto responde 423.
    if getattr(user, "pin_locked", False):
        _p = request.url.path
        _pin_allowed = ("/auth/verify-pin", "/auth/lock", "/auth/me", "/auth/logout")
        if not any(_p.startswith(a) for a in _pin_allowed):
            raise HTTPException(status_code=423, detail="PIN_LOCKED")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Se requieren permisos de administrador")
    # [WF3] Enforcement opcional: si REQUIRE_ADMIN_2FA está activo, el admin debe tener 2FA.
    # Los endpoints de enrolamiento (/auth/2fa/*) usan get_current_user, no require_admin,
    # así que un admin sin 2FA todavía puede entrar a activarlo.
    if settings.REQUIRE_ADMIN_2FA and not getattr(current_user, "totp_enabled", False):
        raise HTTPException(status_code=403, detail="2FA_ENROLLMENT_REQUIRED")
    return current_user


def is_super_admin(user: User) -> bool:
    """Super admin = admin con tenant global (NULL). Único que puede resetear 2FA ajeno."""
    return user.role == "admin" and getattr(user, "tenant", None) in (None, "")


def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if not is_super_admin(current_user):
        raise HTTPException(status_code=403, detail="Se requiere super administrador (admin global)")
    return current_user
