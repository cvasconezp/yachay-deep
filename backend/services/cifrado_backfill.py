"""
[Cifrado en reposo — Fase 2 Migrate] Backfill del histórico.

Rellena las columnas *_cif / *_bidx de los registros que existían antes de
activar la doble escritura (Expand). Idempotente: solo toca filas donde la
columna cifrada está NULL y el texto plano no. No borra ni modifica el texto
plano (eso ocurre en Contract).

Reutiliza los mapas de campos de crypto_sync para no duplicar la definición.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..crypto import blind_index, decrypt, encrypt
from ..crypto_sync import _STUDENT_MAP, _USER_MAP
from ..models.student import Student
from ..models.user import User

_TARGETS = [("students", Student, _STUDENT_MAP), ("users", User, _USER_MAP)]


def _txt(v):
    return None if v is None else (v if isinstance(v, str) else str(v))


def backfill(db: Session, dry_run: bool = True) -> dict:
    """Cifra las filas pendientes. Devuelve conteos por tabla."""
    report = {}
    for key, Model, mapping in _TARGETS:
        revisados = actualizados = campos = 0
        for row in db.query(Model).all():
            revisados += 1
            row_changed = False
            for plano, (cif, bidx) in mapping.items():
                if getattr(row, cif, None) is not None:
                    continue  # ya cifrado
                val = _txt(getattr(row, plano, None))
                if val is None:
                    continue
                campos += 1
                row_changed = True
                if not dry_run:
                    setattr(row, cif, encrypt(val))
                    if bidx:
                        setattr(row, bidx, blind_index(val))
            if row_changed:
                actualizados += 1
        if not dry_run:
            db.commit()
        report[key] = {"revisados": revisados, "filas_pendientes": actualizados, "campos_cifrados": campos}
    return report


def verify(db: Session) -> list[str]:
    """Descifra cada *_cif y lo compara con el texto plano; recomputa cada bidx."""
    errores: list[str] = []
    for key, Model, mapping in _TARGETS:
        for row in db.query(Model).all():
            for plano, (cif, bidx) in mapping.items():
                val = _txt(getattr(row, plano, None))
                cifv = getattr(row, cif, None)
                if val is None:
                    if cifv is not None and decrypt(cifv) not in (None, ""):
                        errores.append(f"{key}#{row.id}.{plano}: plano NULL pero _cif tiene dato")
                    continue
                if cifv is None:
                    errores.append(f"{key}#{row.id}.{plano}: sin cifrar (_cif NULL)")
                elif decrypt(cifv) != val:
                    errores.append(f"{key}#{row.id}.{plano}: descifrado != plano")
                if bidx and getattr(row, bidx, None) != blind_index(val):
                    errores.append(f"{key}#{row.id}.{bidx}: blind index no coincide")
    return errores
