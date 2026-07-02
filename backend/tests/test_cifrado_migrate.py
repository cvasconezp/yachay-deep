"""[Cifrado en reposo — Fase 2 Migrate] Backfill del histórico + endpoint admin."""
from sqlalchemy import text

from backend import crypto
from backend.models.student import Student
from backend.models.user import User, UserRole
from backend.auth.jwt import hash_password
from backend.services.cifrado_backfill import backfill, verify
from .conftest import auth


def _legacy_student(db):
    """Crea un estudiante y simula que es 'legacy' (previo a Expand):
    con texto plano pero columnas cifradas en NULL."""
    s = Student(cedula="1700000001", nombre="Legacy Uno", correo="legacy@x.edu",
                genero="M", autoidentificacion_etnica="Mestizo")
    db.add(s)
    db.commit()
    db.execute(text(
        "UPDATE students SET cedula_cif=NULL, cedula_bidx=NULL, nombre_cif=NULL, "
        "nombre_bidx=NULL, correo_cif=NULL, correo_bidx=NULL, genero_cif=NULL, "
        "autoidentificacion_etnica_cif=NULL WHERE id=:id"), {"id": s.id})
    db.commit()
    db.expire_all()
    return s.id


def test_backfill_dry_run_no_escribe(db):
    sid = _legacy_student(db)
    rep = backfill(db, dry_run=True)
    assert rep["students"]["filas_pendientes"] >= 1
    db.expire_all()
    s = db.get(Student, sid)
    assert s.cedula_cif is None  # dry-run no escribió


def test_backfill_apply_y_verify(db):
    sid = _legacy_student(db)
    rep = backfill(db, dry_run=False)
    assert rep["students"]["campos_cifrados"] >= 4
    db.expire_all()
    s = db.get(Student, sid)
    assert crypto.decrypt(s.cedula_cif) == "1700000001"
    assert s.cedula_bidx == crypto.blind_index("1700000001")
    assert crypto.decrypt(s.autoidentificacion_etnica_cif) == "Mestizo"
    # verify limpio
    assert verify(db) == []


def test_backfill_idempotente(db):
    _legacy_student(db)
    backfill(db, dry_run=False)
    # segunda pasada: nada pendiente
    rep = backfill(db, dry_run=False)
    assert rep["students"]["campos_cifrados"] == 0


def test_endpoint_backfill_modos(client, admin_token, db):
    _legacy_student(db)
    # dry-run
    r = client.post("/admin/cifrado/backfill?mode=dry-run", headers=auth(admin_token))
    assert r.status_code == 200 and r.json()["mode"] == "dry-run"
    # apply
    r = client.post("/admin/cifrado/backfill?mode=apply", headers=auth(admin_token))
    assert r.status_code == 200 and r.json()["mode"] == "apply"
    # verify OK
    r = client.post("/admin/cifrado/backfill?mode=verify", headers=auth(admin_token))
    assert r.status_code == 200 and r.json()["ok"] is True


def test_endpoint_backfill_requiere_admin(client):
    assert client.post("/admin/cifrado/backfill").status_code == 401
