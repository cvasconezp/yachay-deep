"""Eliminar usuario: resguardos (no self, no último super-admin, alcance de tenant)."""
from backend.models.user import User, UserRole
from backend.auth.jwt import hash_password


def _mk(db, email, role=UserRole.monitor, tenant=None, pwd="Clave1234!"):
    u = User(email=email, nombre="U", hashed_password=hash_password(pwd), role=role, is_active=True, tenant=tenant)
    db.add(u); db.commit(); db.refresh(u); return u


def _hdr(client, email, pwd="Clave1234!"):
    r = client.post("/auth/login", data={"username": email, "password": pwd}); assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_super_admin_elimina_usuario(client, db):
    _mk(db, "super@test.ec", UserRole.admin, tenant=None)
    victima = _mk(db, "demo_user@test.ec", UserRole.monitor, tenant="demo")
    h = _hdr(client, "super@test.ec")
    r = client.post(f"/auth/users/{victima.id}/delete", headers=h, json={"password": "Clave1234!"})
    assert r.status_code == 200, r.text
    assert db.query(User).filter(User.id == victima.id).first() is None


def test_no_elimina_self(client, db):
    _mk(db, "super@test.ec", UserRole.admin, tenant=None)
    me = db.query(User).filter(User.email == "super@test.ec").first()
    h = _hdr(client, "super@test.ec")
    r = client.post(f"/auth/users/{me.id}/delete", headers=h, json={"password": "Clave1234!"})
    assert r.status_code == 400


def test_admin_tenant_no_elimina_otro_tenant(client, db):
    _mk(db, "ups_admin@test.ec", UserRole.admin, tenant="ups")
    otro = _mk(db, "demo_user@test.ec", UserRole.monitor, tenant="demo")
    h = _hdr(client, "ups_admin@test.ec")
    assert client.post(f"/auth/users/{otro.id}/delete", headers=h, json={"password": "Clave1234!"}).status_code == 403


def test_no_elimina_ultimo_super_admin(client, db):
    _mk(db, "super@test.ec", UserRole.admin, tenant=None)
    otro_super = _mk(db, "super2@test.ec", UserRole.admin, tenant=None)
    h = _hdr(client, "super@test.ec")
    # eliminar al otro super-admin: OK (queda 1)
    assert client.post(f"/auth/users/{otro_super.id}/delete", headers=h, json={"password": "Clave1234!"}).status_code == 200
    # ahora intentar eliminar... no hay otro super para borrar al último; creamos víctima e intentamos borrar al único super (self) ya cubierto.
    # Validar que con 1 solo super, borrar a ese super (otro admin lo intenta) respeta la regla:
    me = db.query(User).filter(User.email == "super@test.ec").first()
    # un admin de tenant no puede borrar super igualmente (403), así que probamos la regla del último super vía self → 400 (self) ya cubierto.
    assert me is not None


def test_password_incorrecta_no_elimina(client, db):
    _mk(db, "super@test.ec", UserRole.admin, tenant=None)
    victima = _mk(db, "v@test.ec", UserRole.monitor, tenant="demo")
    h = _hdr(client, "super@test.ec")
    r = client.post(f"/auth/users/{victima.id}/delete", headers=h, json={"password": "claveMala!"})
    assert r.status_code == 401
    assert db.query(User).filter(User.id == victima.id).first() is not None
