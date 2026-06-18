"""
Auth routes — [SEC-02] Fase 2: HttpOnly cookie JWT.
Login SET-COOKIE HttpOnly+Secure+SameSite. Logout borra cookie.
Bearer header sigue funcionando como fallback (API consumers).
"""
from datetime import datetime, timezone, timedelta
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status, Form
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..config import settings
from ..database import get_db, get_prod_db
from ..models.user import User, UserRole
from .jwt import (verify_password, create_access_token, create_refresh_token, decode_token,
                  hash_password, needs_rehash, get_current_user, require_admin,
                  require_super_admin, is_super_admin,
                  COOKIE_NAME, REFRESH_COOKIE_NAME)
from ..models.refresh_token import RefreshToken
from jose import JWTError

import logging
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)


def _user_2fa_flags(user) -> dict:
    enabled = bool(getattr(user, 'totp_enabled', False))
    return {
        'totp_enabled': enabled,
        'must_enroll_2fa': bool(settings.REQUIRE_2FA and not enabled),
        'is_super_admin': is_super_admin(user),
    }
router = APIRouter(prefix="/auth", tags=["auth"])

def _norm_tenant(t):
    return (t or "").strip().lower() or None


def _assert_can_manage_tenant(actor: User, target_tenant):
    """Un super-admin (global) gestiona cualquier tenant. Un admin de tenant
    solo puede gestionar usuarios de SU propio tenant (ni globales ni de otros)."""
    target = _norm_tenant(target_tenant)
    if is_super_admin(actor):
        return
    actor_tenant = _norm_tenant(actor.tenant)
    if target is None:
        raise HTTPException(status_code=403, detail="Solo el super-admin puede gestionar usuarios globales")
    if target != actor_tenant:
        raise HTTPException(status_code=403, detail="No puedes gestionar usuarios de otra institución")



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
    tenant: Optional[str] = None  # código de institución (subdominio); None = global
    send_welcome_email: bool = True


class UserUpdate(BaseModel):
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None
    nombre: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)
    permissions: Optional[list[str]] = None
    tenant: Optional[str] = None

class ChangeEmailRequest(BaseModel):
    new_email: EmailStr
    password: str = Field(..., min_length=8)
    code: Optional[str] = None  # código 2FA si el usuario lo tiene activo



class UserResponse(BaseModel):
    id: int
    email: str
    nombre: str
    role: str
    is_active: bool
    created_at: Optional[datetime]
    permissions: Optional[list[str]] = None
    tenant: Optional[str] = None
    has_pin: bool = False
    totp_enabled: bool = False
    must_enroll_2fa: bool = False
    is_super_admin: bool = False

    class Config:
        from_attributes = True


def _set_refresh_cookie(response, token: str):
    response.set_cookie(
        key=REFRESH_COOKIE_NAME, value=token, httponly=True,
        secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN, path="/", max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )


def _issue_refresh_token(db: Session, user_id: int, replaced_by: str = None) -> str:
    """Crea un registro RefreshToken y devuelve el JWT firmado."""
    jti = uuid.uuid4().hex
    expires = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db.add(RefreshToken(id=jti, user_id=user_id, expires_at=expires, revoked=False))
    db.commit()
    return create_refresh_token({"sub": str(user_id), "jti": jti})


def _revoke_all_user_tokens(db: Session, user_id: int):
    db.query(RefreshToken).filter(RefreshToken.user_id == user_id, RefreshToken.revoked == False).update({"revoked": True})
    db.commit()


@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), code: Optional[str] = Form(None), db: Session = Depends(get_db)):
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

    # [WF3] Segundo factor: si el usuario tiene 2FA activo, exigir código TOTP o de recuperación.
    if user.totp_enabled:
        if not code:
            raise HTTPException(status_code=401, detail="2FA_REQUIRED")
        if not _verify_2fa_code(user, code, db):
            raise HTTPException(status_code=401, detail="Código 2FA inválido")

    # [WF1B] Rehash transparente: si el hash es de un esquema viejo (bcrypt),
    # se regenera a argon2id con la contraseña que el usuario acaba de validar.
    if needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(form_data.password)

    user.last_login = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token({"sub": str(user.id)})
    refresh = _issue_refresh_token(db, user.id)  # [WF4]

    # [SEC-02] Respuesta con HttpOnly cookie + token en body (backward compat)
    response = JSONResponse(content={
        "access_token": token,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "nombre": user.nombre, "role": user.role, "permissions": user.permissions, "tenant": user.tenant, "has_pin": user.pin_hash is not None, **_user_2fa_flags(user)},
    })
    _set_refresh_cookie(response, refresh)  # [WF4]
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


@router.post("/refresh")
def refresh_token_endpoint(request: Request, refresh_token: Optional[str] = Form(None), db: Session = Depends(get_db)):
    """[WF4] Renueva el access token usando el refresh token (cookie o body).
    Aplica rotación (el refresh viejo se revoca) y detección de reuso
    (si llega un refresh ya revocado, se revoca toda la cadena del usuario)."""
    token = request.cookies.get(REFRESH_COOKIE_NAME) or refresh_token
    if not token:
        raise HTTPException(status_code=401, detail="No hay refresh token")
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Refresh inválido")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token no es de tipo refresh")
    jti = payload.get("jti")
    user_id = payload.get("sub")
    rec = db.query(RefreshToken).filter(RefreshToken.id == jti).first() if jti else None

    if rec is None or user_id is None:
        raise HTTPException(status_code=401, detail="Refresh inválido")
    # Detección de reuso: un refresh ya revocado que se vuelve a usar = posible robo.
    if rec.revoked:
        _revoke_all_user_tokens(db, rec.user_id)
        raise HTTPException(status_code=401, detail="Refresh reutilizado: sesión revocada")
    if rec.expires_at and rec.expires_at < datetime.now(timezone.utc).replace(tzinfo=rec.expires_at.tzinfo):
        raise HTTPException(status_code=401, detail="Refresh expirado")

    user = db.query(User).filter(User.id == int(user_id), User.is_active == True).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Usuario no válido")

    # Rotación: revocar el actual y emitir uno nuevo.
    new_refresh = _issue_refresh_token(db, user.id)
    new_jti = decode_token(new_refresh).get("jti")
    rec.revoked = True
    rec.replaced_by = new_jti
    db.commit()

    new_access = create_access_token({"sub": str(user.id)})
    response = JSONResponse(content={"access_token": new_access, "refresh_token": new_refresh, "token_type": "bearer"})
    response.set_cookie(
        key=COOKIE_NAME, value=new_access, httponly=True,
        secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN, path="/", max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    _set_refresh_cookie(response, new_refresh)
    return response


@router.post("/logout")
def logout(request: Request, refresh_token: Optional[str] = Form(None), db: Session = Depends(get_db)):
    """[SEC-02] Borra la HttpOnly cookie. [WF4] Revoca el refresh token activo."""
    # [WF4] Revocar refresh token si viene en cookie o body
    rt = request.cookies.get(REFRESH_COOKIE_NAME) or refresh_token
    if rt:
        try:
            jti = decode_token(rt).get("jti")
            rec = db.query(RefreshToken).filter(RefreshToken.id == jti).first() if jti else None
            if rec and not rec.revoked:
                rec.revoked = True
                db.commit()
        except JWTError:
            pass
    response = JSONResponse(content={"detail": "Sesión cerrada"})
    # Must match ALL attributes of the original set_cookie for browser to delete it
    _del_kwargs = dict(
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
    )
    # Delete cookie for shared subdomain domain (.yachaydeep.com)
    response.delete_cookie(key=COOKIE_NAME, path="/", domain=settings.COOKIE_DOMAIN, **_del_kwargs)
    # Also delete legacy cookie set without explicit domain (exact origin match)
    response.delete_cookie(key=COOKIE_NAME, path="/", **_del_kwargs)
    # [WF4] borrar cookie de refresh
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/", domain=settings.COOKIE_DOMAIN, **_del_kwargs)
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/", **_del_kwargs)
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
        tenant=current_user.tenant,
        has_pin=current_user.pin_hash is not None,
        **_user_2fa_flags(current_user),
    )


@router.post("/users", response_model=UserResponse)
def create_user(payload: UserCreate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    # [RBAC] Un admin de tenant solo crea usuarios de su propia institución.
    target_tenant = payload.tenant
    if not is_super_admin(current_user):
        target_tenant = _norm_tenant(current_user.tenant)  # forzar a su tenant
    _assert_can_manage_tenant(current_user, target_tenant)
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    user = User(
        email=payload.email.lower(),
        nombre=payload.nombre,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        permissions=payload.permissions,
        tenant=target_tenant,
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


@router.get("/users", response_model=list[UserResponse])
def list_users(scope: Optional[str] = None, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """[RBAC] Vista por instancia:
    - super-admin en kapak (scope vacío): ve TODOS los usuarios (gestión global).
    - super-admin dentro de una instancia (scope=ups/demo): ve los de esa institución + los globales.
    - admin de tenant: solo los de su propia institución."""
    from sqlalchemy import or_
    q = db.query(User)
    if is_super_admin(current_user):
        sc = _norm_tenant(scope)
        if sc is not None:
            q = q.filter(or_(User.tenant == sc, User.tenant.is_(None), User.tenant == ""))
    else:
        q = q.filter(User.tenant == _norm_tenant(current_user.tenant))
    return q.all()


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: int, payload: UserUpdate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    # [RBAC] el actor debe poder gestionar el tenant ACTUAL del usuario objetivo...
    _assert_can_manage_tenant(current_user, user.tenant)
    updates = payload.model_dump(exclude_unset=True)
    # ...y si se intenta cambiar el tenant, también el destino debe estar permitido.
    if "tenant" in updates:
        _assert_can_manage_tenant(current_user, updates["tenant"])
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
    if "tenant" in updates:
        user.tenant = updates["tenant"]
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/reset-2fa")
def admin_reset_2fa(user_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """[WF3] Un admin resetea (desactiva) el 2FA de un usuario de SU institución
    (super-admin: cualquiera). El usuario podrá volver a enrolarse desde /seguridad."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    _assert_can_manage_tenant(current_user, user.tenant)
    user.totp_enabled = False
    user.totp_secret = None
    user.recovery_codes = None
    db.commit()
    return {"detail": f"2FA reseteado para {user.email}", "user_id": user.id, "email": user.email}


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)


@router.post("/users/{user_id}/reset-password")
def admin_reset_password(user_id: int, payload: ResetPasswordRequest, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Un admin restablece la contraseña de un usuario de SU institución
    (super-admin: cualquiera). Además se le desactivan futuros... (no toca 2FA)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    _assert_can_manage_tenant(current_user, user.tenant)
    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    logger.info("Admin %s reseteó contraseña de %s", current_user.email, user.email)
    return {"detail": f"Contraseña actualizada para {user.email}", "user_id": user.id, "email": user.email}


class DeleteUserRequest(BaseModel):
    password: str = Field(..., min_length=1)


@router.post("/users/{user_id}/delete")
def delete_user(user_id: int, payload: DeleteUserRequest, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Elimina un usuario de la institución del admin (super-admin: cualquiera).
    Requiere la contraseña del admin/super-admin logueado como confirmación.
    Resguardos: no puedes eliminarte; solo un super-admin elimina a otro super-admin
    y nunca al último super-admin. Limpia referencias (intervenciones, recomendaciones, tokens)."""
    if not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    _assert_can_manage_tenant(current_user, user.tenant)
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta")
    if is_super_admin(user):
        if not is_super_admin(current_user):
            raise HTTPException(status_code=403, detail="Solo un super-admin puede eliminar a otro super-admin")
        otros = db.query(User).filter(User.role == "admin", User.tenant.is_(None), User.id != user.id, User.is_active == True).count()
        if otros == 0:
            raise HTTPException(status_code=400, detail="No puedes eliminar al último super-admin")

    # Limpiar referencias para no violar integridad referencial
    from ..models.intervention import Intervention
    from ..models.recommendation_log import RecommendationLog
    from ..models.refresh_token import RefreshToken
    db.query(Intervention).filter(Intervention.monitor_id == user.id).update({"monitor_id": None})
    db.query(Intervention).filter(Intervention.asignado_a == user.id).update({"asignado_a": None})
    db.query(RecommendationLog).filter(RecommendationLog.ejecutada_por == user.id).update({"ejecutada_por": None})
    db.query(RefreshToken).filter(RefreshToken.user_id == user.id).delete()

    email = user.email
    db.delete(user)
    db.commit()
    logger.info("Admin %s eliminó al usuario %s", current_user.email, email)
    return {"detail": f"Usuario {email} eliminado", "email": email}


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
    db: Session = Depends(get_prod_db),
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
    db: Session = Depends(get_prod_db),
):
    """Elimina el PIN configurado."""
    current_user.pin_hash = None
    db.commit()
    return {"detail": "PIN eliminado"}


# ─────────────────────────── [WF3] 2FA (TOTP) ───────────────────────────
import io as _io
import base64 as _base64
import secrets as _secrets

try:
    import pyotp as _pyotp
    import qrcode as _qrcode
    _TWOFA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _TWOFA_AVAILABLE = False


def _verify_2fa_code(user: User, code: str, db: Session) -> bool:
    """Verifica un código TOTP de 6 dígitos o, en su defecto, un código de recuperación
    (de un solo uso). Si se usa uno de recuperación, se consume."""
    code = (code or "").strip().replace(" ", "")
    if not code:
        return False
    # 1) TOTP
    if user.totp_secret and _TWOFA_AVAILABLE:
        if _pyotp.TOTP(user.totp_secret).verify(code, valid_window=1):
            return True
    # 2) Código de recuperación (hash argon2; se consume el usado)
    if user.recovery_codes:
        restantes = list(user.recovery_codes)
        for h in restantes:
            if verify_password(code, h):
                restantes.remove(h)
                user.recovery_codes = restantes
                db.commit()
                return True
    return False


@router.get("/2fa/status")
def twofa_status(current_user: User = Depends(get_current_user)):
    """Estado de 2FA del usuario autenticado."""
    return {
        "enabled": bool(current_user.totp_enabled),
        "recovery_codes_remaining": len(current_user.recovery_codes or []),
    }


@router.post("/2fa/setup")
def twofa_setup(current_user: User = Depends(get_current_user), db: Session = Depends(get_prod_db)):
    """Genera un secreto TOTP y un QR para escanear. Aún NO habilita 2FA
    (se confirma en /2fa/verify-setup con un código del autenticador)."""
    if not _TWOFA_AVAILABLE:
        raise HTTPException(500, "pyotp/qrcode no instalados")
    if current_user.totp_enabled:
        raise HTTPException(400, "2FA ya está activo. Desactívalo antes de re-enrolar.")
    secret = _pyotp.random_base32()
    uri = _pyotp.totp.TOTP(secret).provisioning_uri(name=current_user.email, issuer_name="Yachay Deep")
    img = _qrcode.make(uri)
    buf = _io.BytesIO(); img.save(buf, format="PNG")
    qr_b64 = _base64.b64encode(buf.getvalue()).decode()
    current_user.totp_secret = secret  # guardado pero no habilitado hasta verificar
    db.commit()
    return {"qr": f"data:image/png;base64,{qr_b64}", "secret": secret, "otpauth_uri": uri}


@router.post("/2fa/verify-setup")
def twofa_verify_setup(code: str = Form(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_prod_db)):
    """Confirma el enrolamiento: valida un código del app, habilita 2FA y
    entrega los códigos de recuperación (se muestran UNA sola vez)."""
    if not _TWOFA_AVAILABLE:
        raise HTTPException(500, "pyotp/qrcode no instalados")
    if not current_user.totp_secret:
        raise HTTPException(400, "Primero llama a /2fa/setup")
    if not _pyotp.TOTP(current_user.totp_secret).verify(code.strip(), valid_window=1):
        raise HTTPException(400, "Código inválido")
    plain_codes = [_secrets.token_hex(4) for _ in range(8)]
    current_user.recovery_codes = [hash_password(c) for c in plain_codes]
    current_user.totp_enabled = True
    db.commit()
    return {"recovery_codes": plain_codes, "detail": "2FA activado"}


@router.post("/2fa/disable")
def twofa_disable(password: str = Form(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_prod_db)):
    """Desactiva 2FA. Requiere la contraseña actual como confirmación."""
    if not verify_password(password, current_user.hashed_password):
        raise HTTPException(401, "Contraseña incorrecta")
    current_user.totp_enabled = False
    current_user.totp_secret = None
    current_user.recovery_codes = None
    db.commit()
    return {"detail": "2FA desactivado"}


@router.post("/change-email")
def change_email(payload: ChangeEmailRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_prod_db)):
    """Cambia el correo del usuario autenticado con re-autenticación fuerte:
    contraseña + (si tiene 2FA) código TOTP o de recuperación. Sin confirmación por email."""
    if not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    if current_user.totp_enabled:
        if not payload.code or not _verify_2fa_code(current_user, payload.code, db):
            raise HTTPException(status_code=401, detail="Código 2FA inválido o requerido")
    new_email = payload.new_email.lower().strip()
    if new_email == current_user.email:
        raise HTTPException(status_code=400, detail="El correo nuevo es igual al actual")
    if db.query(User).filter(User.email == new_email, User.id != current_user.id).first():
        raise HTTPException(status_code=400, detail="Ese correo ya está en uso")
    old = current_user.email
    current_user.email = new_email
    db.commit()
    logger.info("Cambio de correo: %s -> %s (user_id=%s)", old, new_email, current_user.id)
    return {"detail": "Correo actualizado", "email": new_email}
