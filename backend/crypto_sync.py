"""
backend/crypto_sync.py — Mantenimiento del blind index (Fase 2 Contract 2.3a).

Desde 2.3a los campos cifrados (cedula, genero, etnia, domicilio, totp_secret)
usan el tipo EncryptedString: el cifrado/descifrado es transparente en el ORM.
Lo único que hay que mantener a mano es el BLIND INDEX de los campos buscables
por igualdad — hoy solo `cedula` (búsqueda exacta) -> cedula_bidx.

Defensivo: si no hay llaves configuradas, no hace nada.
Se activa importando este módulo al arrancar (backend/main.py).
"""
from __future__ import annotations

import logging

from sqlalchemy import event

from .crypto import blind_index, is_configured
from .models.student import Student

logger = logging.getLogger(__name__)


def _student_bidx(mapper, connection, target):
    if not is_configured():
        return
    try:
        target.cedula_bidx = blind_index(target.cedula)
    except Exception as exc:  # no bloquear la escritura primaria
        logger.warning("blind index de cedula falló: %s", exc)


def register() -> None:
    for evt in ("before_insert", "before_update"):
        if not event.contains(Student, evt, _student_bidx):
            event.listen(Student, evt, _student_bidx)


register()
