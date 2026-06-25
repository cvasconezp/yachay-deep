"""WF3 — un admin puede resetear (desactivar) el 2FA de otro usuario."""
import pyotp
from backend.models.user import User, UserRole
from backend.auth.jwt import hash_password


def _mk(db, email, role=UserRole.admin, pwd="Clave123!"):
    u = User(email=email, nombre="U", hashed_password=hash_password(pwd), role=role, is_active=True)
    db.add(u); db.commit(); db.refresh(u)
    return u


def _hdr(client, email, pwd="Clave123!", code=None):
    data = {"username": email, "password": pwd}
    if code: data["code"] = code
    r = client.post("/auth/login", data=data)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_admin_resetea_2fa_de_usuario(client, db):
    admin = _mk(db, "admin@test.ec", UserRole.admin)
    victima = _mk(db, "user@test.ec", UserRole.monitor)
    # la víctima activa 2FA
    vh = _hdr(client, "user@test.ec")
    secret = client.post("/auth/2fa/setup", headers=vh).json()["secret"]
    client.post("/auth/2fa/verify-setup", headers=vh, data={"code": pyotp.TOTP(secret).now()})
    assert client.get("/auth/2fa/status", headers=vh).json()["enabled"] is True

    # el admin resetea su 2FA
    ah = _hdr(client, "admin@test.ec")
    r = client.post(f"/auth/users/{victima.id}/reset-2fa", headers=ah)
    assert r.status_code == 200, r.text

    # ahora la víctima entra solo con contraseña (sin código)
    assert client.post("/auth/login", data={"username": "user@test.ec", "password": "Clave123!"}).status_code == 200
    db.refresh(victima)
    assert victima.totp_enabled is False and victima.totp_secret is None


def test_no_admin_no_puede_resetear(client, db):
    _mk(db, "mon@test.ec", UserRole.monitor)
    target = _mk(db, "otro@test.ec", UserRole.monitor)
    mh = _hdr(client, "mon@test.ec")
    r = client.post(f"/auth/users/{target.id}/reset-2fa", headers=mh)
    assert r.status_code == 403
