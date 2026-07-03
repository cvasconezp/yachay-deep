"""[Cifrado en reposo — Contract 2.3b] Endpoint drop-plaintext."""
from sqlalchemy import text
from .conftest import auth


def _add_plaintext_col(db):
    # Simula prod: añade una columna de texto plano huérfana 'cedula' a students.
    db.execute(text("ALTER TABLE students ADD COLUMN cedula VARCHAR"))
    db.commit()


def test_dry_run_lista_columnas(client, admin_token, db):
    _add_plaintext_col(db)
    r = client.post("/admin/cifrado/drop-plaintext?mode=dry-run", headers=auth(admin_token))
    assert r.status_code == 200
    assert "cedula" in r.json()["se_borrarian"]["students"]


def test_apply_sin_confirm_falla(client, admin_token, db):
    _add_plaintext_col(db)
    r = client.post("/admin/cifrado/drop-plaintext?mode=apply", headers=auth(admin_token))
    assert r.status_code == 400  # requiere confirm=BORRAR


def test_apply_con_confirm_borra(client, admin_token, db):
    _add_plaintext_col(db)
    r = client.post("/admin/cifrado/drop-plaintext?mode=apply&confirm=BORRAR", headers=auth(admin_token))
    assert r.status_code == 200
    assert "cedula" in r.json()["borradas"]["students"]
    # la columna ya no existe
    r2 = client.post("/admin/cifrado/drop-plaintext?mode=dry-run", headers=auth(admin_token))
    assert "cedula" not in r2.json()["se_borrarian"]["students"]


def test_requiere_admin(client):
    assert client.post("/admin/cifrado/drop-plaintext").status_code == 401
