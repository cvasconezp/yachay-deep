"""
[Cifrado en reposo — Contract 2.3a] Mantenimiento del blind index.

Tras el remapeo a EncryptedString, el ORM cifra/descifra de forma transparente.
Lo único que queda por mantener a mano es `cedula_bidx` (búsqueda exacta por
cédula). Este servicio:
  - backfill(): rellena cedula_bidx faltante/incorrecto.
  - verify():   comprueba que cada fila descifra y que cedula_bidx coincide.
Se dispara desde el panel Admin (POST /admin/cifrado/backfill).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..crypto import blind_index
from ..models.student import Student


def backfill(db: Session, dry_run: bool = True) -> dict:
    revisados = pendientes = 0
    for s in db.query(Student).all():
        revisados += 1
        expected = blind_index(s.cedula)  # s.cedula ya viene descifrado
        if s.cedula_bidx != expected:
            pendientes += 1
            if not dry_run:
                s.cedula_bidx = expected
    if not dry_run:
        db.commit()
    return {"students": {"revisados": revisados, "filas_pendientes": pendientes}}


def verify(db: Session) -> list[str]:
    errores: list[str] = []
    for s in db.query(Student).all():
        try:
            ced = s.cedula  # fuerza descifrado
        except Exception as exc:  # noqa: BLE001
            errores.append(f"students#{s.id}.cedula: no descifra ({exc})")
            continue
        if ced and s.cedula_bidx != blind_index(ced):
            errores.append(f"students#{s.id}.cedula_bidx: no coincide")
    return errores
