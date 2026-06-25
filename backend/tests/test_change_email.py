"""Cambio de correo con re-autenticación (password + 2FA si aplica)."""
import pyotp
from backend.models.user import User, UserRole
from backend.auth.jwt import hash_password


def _mk(db, email="orig@test.ec", pwd="Clave1234!"):
    u = User(email=email, nombre="U", hashed_password=hash_password(pwd), role=UserRole.admin, is_active=True)
    db.add(u); db.commit(); db.refresh(u); return u


def _hdr(client, email, pwd="Clave1234!", code=None):
    data = {"username": email, "password": pwd}
    if code: data["code"] = code
    r = client.post("/auth/login", data=data); assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_cambia_correo_con_password(client, db):
    _mk(db)
    h = _hdr(client, "orig@test.ec")
    r = client.post("/auth/change-email", headers=h, json={"new_email": "nuevo@test.ec", "password": "Clave1234!"})
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "nuevo@test.ec"
    # ya puede loguear con el nuevo correo
    assert client.post("/auth/login", data={"username": "nuevo@test.ec", "password": "Clave1234!"}).status_code == 200


def test_password_incorrecta_rechaza(client, db):
    _mk(db)
    h = _hdr(client, "orig@test.ec")
    r = client.post("/auth/change-email", headers=h, json={"new_email": "x@test.ec", "password": "malamala1"})
    assert r.status_code == 401


def test_correo_en_uso_rechaza(client, db):
    _mk(db, "orig@test.ec")
    _mk(db, "ocupado@test.ec")
    h = _hdr(client, "orig@test.ec")
    r = client.post("/auth/change-email", headers=h, json={"new_email": "ocupado@test.ec", "password": "Clave1234!"})
    assert r.status_code == 400


def test_con_2fa_exige_codigo(client, db):
    u = _mk(db, "con2fa@test.ec")
    h = _hdr(client, "con2fa@test.ec")
    secret = client.post("/auth/2fa/setup", headers=h).json()["secret"]
    client.post("/auth/2fa/verify-setup", headers=h, data={"code": pyotp.TOTP(secret).now()})
    # sin código → 401
    r = client.post("/auth/change-email", headers=h, json={"new_email": "z@test.ec", "password": "Clave1234!"})
    assert r.status_code == 401
    # con código → OK
    r = client.post("/auth/change-email", headers=h,
                    json={"new_email": "z@test.ec", "password": "Clave1234!", "code": pyotp.TOTP(secret).now()})
    assert r.status_code == 200, r.text
