"""
backend/crypto_sync.py — Doble escritura de cifrado (Fase 2 Expand).

Registra listeners SQLAlchemy que, en cada insert/update de Student y User,
rellenan las columnas *_cif (texto cifrado) y *_bidx (blind index) a partir de
los atributos en texto plano. Asi, toda escritura nueva queda cifrada mientras
convive con el texto plano (reversible). El backfill del historico lo hace
scripts/migrar_cifrado.py (Fase Migrate).

Defensivo: si no hay llaves configuradas (is_configured() == False) no hace nada,
para no romper entornos sin cifrado. Los errores se loguean pero NO bloquean la
escritura primaria (se detectan luego con `migrar_cifrado.py --verify`).

Se activa importando este modulo una vez al arrancar (ver backend/main.py).
"""
from __future__ import annotations

import logging

from sqlalchemy import event

from .crypto import blind_index, encrypt, is_configured
from .models.student import Student
from .models.user import User

logger = logging.getLogger(__name__)

# atributo_plano -> (columna_cif, columna_bidx | None)
_STUDENT_MAP = {
    "cedula": ("cedula_cif", "cedula_bidx"),
    "nombre": ("nombre_cif", "nombre_bidx"),
    "correo": ("correo_cif", "correo_bidx"),
    "correo_institucional": ("correo_institucional_cif", "correo_institucional_bidx"),
    "telefono": ("telefono_cif", None),
    "whatsapp": ("whatsapp_cif", None),
    "genero": ("genero_cif", None),
    "autoidentificacion_etnica": ("autoidentificacion_etnica_cif", None),
    "fecha_nacimiento": ("fecha_nacimiento_cif", None),
    "pais": ("pais_cif", None),
    "provincia": ("provincia_cif", None),
    "ciudad": ("ciudad_cif", None),
    "parroquia": ("parroquia_cif", None),
    "barrio": ("barrio_cif", None),
}
_USER_MAP = {
    "totp_secret": ("totp_secret_cif", None),
}


def _to_text(value):
    if value is None:
        return None
    return value if isinstance(value, str) else str(value)


def _sync(target, mapping) -> None:
    if not is_configured():
        return
    for plano, (cif, bidx) in mapping.items():
        try:
            val = _to_text(getattr(target, plano, None))
            setattr(target, cif, encrypt(val))
            if bidx:
                setattr(target, bidx, blind_index(val))
        except Exception as exc:  # no bloquear la escritura primaria
            logger.warning("cifrado dual-write fallo en campo %s: %s", plano, exc)


def _student_sync(mapper, connection, target):
    _sync(target, _STUDENT_MAP)


def _user_sync(mapper, connection, target):
    _sync(target, _USER_MAP)


def register() -> None:
    """Registra los listeners (idempotente)."""
    for evt in ("before_insert", "before_update"):
        if not event.contains(Student, evt, _student_sync):
            event.listen(Student, evt, _student_sync)
        if not event.contains(User, evt, _user_sync):
            event.listen(User, evt, _user_sync)


# Registrar al importar.
register()
