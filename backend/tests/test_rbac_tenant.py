"""RBAC multi-tenant: admin de tenant limitado a su institución; super-admin global."""
from backend.models.user import User, UserRole
from backend.auth.jwt import hash_password


def _mk(db, email, role=UserRole.admin, tenant=None, pwd="Clave1234!"):
    u = User(email=email, nombre="U", hashed_password=hash_password(pwd), role=role, is_active=True, tenant=tenant)
    db.add(u); db.commit(); db.refresh(u); return u


def _hdr(client, email, pwd="Clave1234!"):
    r = client.post("/auth/login", data={"username": email, "password": pwd}); assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_admin_tenant_no_crea_global(client, db):
    _mk(db, "ups_admin@test.ec", UserRole.admin, tenant="ups")
    h = _hdr(client, "ups_admin@test.ec")
    # intenta crear global → se fuerza a su tenant (no global)
    r = client.post("/auth/users", headers=h, json={"email": "n1@test.ec", "nombre": "N", "password": "Clave1234!", "role": "monitor", "tenant": None})
    assert r.status_code == 200, r.text
    assert r.json()["tenant"] == "ups"  # forzado a su institución


def test_admin_tenant_no_crea_otro_tenant(client, db):
    _mk(db, "ups_admin@test.ec", UserRole.admin, tenant="ups")
    h = _hdr(client, "ups_admin@test.ec")
    # pide tenant 'demo' → igual se fuerza a 'ups'
    r = client.post("/auth/users", headers=h, json={"email": "n2@test.ec", "nombre": "N", "password": "Clave1234!", "role": "monitor", "tenant": "demo"})
    assert r.status_code == 200, r.text
    assert r.json()["tenant"] == "ups"


def test_super_admin_si_crea_global_y_otros(client, db):
    _mk(db, "super@test.ec", UserRole.admin, tenant=None)
    h = _hdr(client, "super@test.ec")
    r = client.post("/auth/users", headers=h, json={"email": "g@test.ec", "nombre": "G", "password": "Clave1234!", "role": "admin", "tenant": None})
    assert r.status_code == 200 and r.json()["tenant"] is None
    r = client.post("/auth/users", headers=h, json={"email": "d@test.ec", "nombre": "D", "password": "Clave1234!", "role": "monitor", "tenant": "demo"})
    assert r.status_code == 200 and r.json()["tenant"] == "demo"


def test_list_users_filtra_por_tenant(client, db):
    _mk(db, "super@test.ec", UserRole.admin, tenant=None)
    _mk(db, "ups_admin@test.ec", UserRole.admin, tenant="ups")
    _mk(db, "ups_mon@test.ec", UserRole.monitor, tenant="ups")
    _mk(db, "demo_mon@test.ec", UserRole.monitor, tenant="demo")
    # admin de ups solo ve usuarios de ups
    h = _hdr(client, "ups_admin@test.ec")
    r = client.get("/auth/users", headers=h)
    tenants = {u["tenant"] for u in r.json()}
    assert tenants == {"ups"}
    # super-admin ve todos
    hs = _hdr(client, "super@test.ec")
    rs = client.get("/auth/users", headers=hs)
    assert len({u["tenant"] for u in rs.json()}) >= 3  # None, ups, demo


def test_admin_tenant_no_edita_usuario_de_otro_tenant(client, db):
    _mk(db, "ups_admin@test.ec", UserRole.admin, tenant="ups")
    victima = _mk(db, "demo_user@test.ec", UserRole.monitor, tenant="demo")
    h = _hdr(client, "ups_admin@test.ec")
    r = client.patch(f"/auth/users/{victima.id}", headers=h, json={"is_active": False})
    assert r.status_code == 403
