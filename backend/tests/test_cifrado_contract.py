"""[Cifrado en reposo — Contract 2.3a] Lectura transparente + búsqueda por blind index."""
from sqlalchemy import text

from backend import crypto
from backend.models.student import Student
from backend.models.user import User, UserRole
from backend.auth.jwt import hash_password
from backend.services.cifrado_backfill import backfill, verify
from .conftest import auth


def test_lectura_descifrada_y_columna_cifrada_en_bd(db):
    s = Student(cedula="1723456789", nombre="Ana Ñañez", genero="F",
                autoidentificacion_etnica="Kichwa", ciudad="Quito")
    db.add(s); db.commit(); db.refresh(s)
    # atributos leen en claro (descifrado transparente)
    assert s.cedula == "1723456789"
    assert s.autoidentificacion_etnica == "Kichwa"
    assert s.ciudad == "Quito"
    # blind index de cédula poblado por el listener
    assert s.cedula_bidx == crypto.blind_index("1723456789")
    # en la BD, la columna cedula_cif guarda TEXTO CIFRADO (no el plano)
    raw = db.execute(text("SELECT cedula_cif FROM students WHERE id=:i"), {"i": s.id}).scalar()
    assert raw and raw != "1723456789" and crypto.decrypt(raw) == "1723456789"
    # nombre permanece en claro (búsqueda parcial)
    raw_nombre = db.execute(text("SELECT nombre FROM students WHERE id=:i"), {"i": s.id}).scalar()
    assert raw_nombre == "Ana Ñañez"


def test_busqueda_exacta_por_cedula_bidx(client, admin_token, db):
    db.add(Student(cedula="1700000009", nombre="Buscar Uno", correo_institucional="b1@ups.edu.ec"))
    db.commit()
    # búsqueda por cédula exacta
    r = client.get("/students/search?q=1700000009", headers=auth(admin_token))
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(it["cedula"] == "1700000009" for it in items)
    # búsqueda parcial por nombre sigue funcionando (texto plano)
    r2 = client.get("/students/search?q=Buscar", headers=auth(admin_token))
    assert any(it["nombre"] == "Buscar Uno" for it in r2.json()["items"])


def test_user_totp_secret_cifrado(db):
    u = User(email="d@x.edu", nombre="D", hashed_password=hash_password("x"),
             role=UserRole.monitor, totp_secret="JBSWY3DPEHPK3PXP")
    db.add(u); db.commit(); db.refresh(u)
    assert u.totp_secret == "JBSWY3DPEHPK3PXP"  # lee en claro
    raw = db.execute(text("SELECT totp_secret_cif FROM users WHERE id=:i"), {"i": u.id}).scalar()
    assert raw and crypto.decrypt(raw) == "JBSWY3DPEHPK3PXP"


def test_backfill_y_verify(db):
    db.add(Student(cedula="1711111111", nombre="X"))
    db.commit()
    # tras la escritura, bidx ya está; backfill no debe encontrar pendientes
    rep = backfill(db, dry_run=True)
    assert rep["students"]["filas_pendientes"] == 0
    assert verify(db) == []


def test_endpoint_backfill(client, admin_token, db):
    db.add(Student(cedula="1722222222", nombre="Y")); db.commit()
    r = client.post("/admin/cifrado/backfill?mode=verify", headers=auth(admin_token))
    assert r.status_code == 200 and r.json()["ok"] is True
