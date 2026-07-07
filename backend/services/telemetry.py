"""
Helper de telemetría de uso (chore/estandar-casa, punto 7). Pseudonimizado, LOPDP-safe.

Uso:
    from ..services.telemetry import track
    track(db, "ficha360_view", user_id=current_user.id, role=current_user.role,
          tenant=current_user.tenant, props={"carrera": carrera})   # props sin PII

Best-effort: nunca hace fallar el request principal.
"""
from __future__ import annotations

import hashlib
import hmac
import logging

from sqlalchemy.orm import Session

from ..config import settings
from ..models.usage_event import UsageEvent, EVENTOS

logger = logging.getLogger(__name__)

_PII_KEYS = {"email", "correo", "cedula", "nombre", "telefono", "whatsapp", "direccion"}


def _actor_hash(user_id) -> str:
    """HMAC-SHA256 del user_id. Pseudónimo estable, no reversible a PII."""
    key = getattr(settings, "TELEMETRY_KEY", None) or settings.SECRET_KEY
    return hmac.new(key.encode(), str(user_id).encode(), hashlib.sha256).hexdigest()


def _strip_pii(props: dict | None) -> dict | None:
    if not props:
        return props
    return {k: v for k, v in props.items() if k.lower() not in _PII_KEYS}


def track(db: Session, event: str, *, user_id=None, role=None, tenant=None, props: dict | None = None) -> None:
    """Registra un evento de uso. No lanza si algo falla (telemetría best-effort)."""
    if event not in EVENTOS:
        logger.warning("telemetry: evento no permitido %r", event)
        return
    try:
        role_str = getattr(role, "value", None) or (str(role) if role is not None else None)
        db.add(UsageEvent(
            event=event,
            actor_hash=_actor_hash(user_id) if user_id is not None else "anon",
            role=role_str[:20] if role_str else None,
            tenant=tenant,
            props=_strip_pii(props),
        ))
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        logger.exception("telemetry: no se pudo registrar %s", event)
