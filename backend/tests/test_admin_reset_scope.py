"""Admin de tenant restablece 2FA y contraseña SOLO de su institución."""
import pyotp
from backend.models.user import User, UserRole
from backend.auth.jwt import hash_password, verify_password


def _mk(db, email, role=UserRole.admin, tenant=None, pwd="Clave1234!"):
    u = User(email=email, nombre="U", hashed_password=hash_password(pwd), role=role, is_active=True, tenant=tenant)
    db.add(u); db.commit(); db.refresh(u); return u


def _hdr(client, email, pwd="Clave1234!"):
    r = client.post("/auth/login", data={"username": email, "password": pwd}); assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_admin_tenant_resetea_2fa_de_su_tenant(client, db):
    _mk(db, "ups_admin@test.ec", UserRole.admin, tenant="ups")
    victima = _mk(db, "ups_user@test.ec", UserRole.monitor, tenant="ups")
    # activar 2FA de la víctima
    vh = _hdr(client, "ups_user@test.ec")
    secret = client.post("/auth/2fa/setup", headers=vh).json()["secret"]
    client.post("/auth/2fa/verify-setup", headers=vh, data={"code": pyotp.TOTP(secret).now()})
    # admin de ups resetea
    ah = _hdr(client, "ups_admin@test.ec")
    r = client.post(f"/auth/users/{victima.id}/reset-2fa", headers=ah)
    assert r.status_code == 200, r.text
    db.refresh(victima); assert victima.totp_enabled is False


def test_admin_tenant_no_resetea_otro_tenant(client, db):
    _mk(db, "ups_admin@test.ec", UserRole.admin, tenant="ups")
    otro = _mk(db, "demo_user@test.ec", UserRole.monitor, tenant="demo")
    ah = _hdr(client, "ups_admin@test.ec")
    assert client.post(f"/auth/users/{otro.id}/reset-2fa", headers=ah).status_code == 403
    assert client.post(f"/auth/users/{otro.id}/reset-password", headers=ah, json={"new_password": "NuevaClave1!"}).status_code == 403


def test_admin_tenant_resetea_password_de_su_tenant(client, db):
    _mk(db, "ups_admin@test.ec", UserRole.admin, tenant="ups")
    victima = _mk(db, "ups_user@test.ec", UserRole.monitor, tenant="ups", pwd="Vieja123!")
    ah = _hdr(client, "ups_admin@test.ec")
    r = client.post(f"/auth/users/{victima.id}/reset-password", headers=ah, json={"new_password": "NuevaClave1!"})
    assert r.status_code == 200, r.text
    db.refresh(victima); assert verify_password("NuevaClave1!", victima.hashed_password)
    # la víctima puede entrar con la nueva
    assert client.post("/auth/login", data={"username": "ups_user@test.ec", "password": "NuevaClave1!"}).status_code == 200


def test_super_admin_resetea_cualquiera(client, db):
    _mk(db, "super@test.ec", UserRole.admin, tenant=None)
    otro = _mk(db, "demo_user@test.ec", UserRole.monitor, tenant="demo")
    sh = _hdr(client, "super@test.ec")
    assert client.post(f"/auth/users/{otro.id}/reset-password", headers=sh, json={"new_password": "NuevaClave1!"}).status_code == 200
