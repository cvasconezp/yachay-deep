"""WF3 — 2FA TOTP para usuarios (enrolamiento, login en dos pasos, recovery)."""
import pyotp
from backend.models.user import User, UserRole
from backend.auth.jwt import hash_password


def _login(client, email, password, code=None):
    data = {"username": email, "password": password}
    if code is not None:
        data["code"] = code
    return client.post("/auth/login", data=data)


def _mk_admin(db, email="adm2fa@test.ec", pwd="ClaveAdmin123!"):
    u = User(email=email, nombre="Admin", hashed_password=hash_password(pwd),
             role=UserRole.admin, is_active=True)
    db.add(u); db.commit(); db.refresh(u)
    return u


def _auth_headers(client, email, pwd):
    r = _login(client, email, pwd)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _enroll(client, db, email="adm2fa@test.ec", pwd="ClaveAdmin123!"):
    """Helper (NO test): crea admin y completa enrolamiento 2FA. Devuelve (secret, recovery, headers)."""
    _mk_admin(db, email=email, pwd=pwd)
    h = _auth_headers(client, email, pwd)
    secret = client.post("/auth/2fa/setup", headers=h).json()["secret"]
    r = client.post("/auth/2fa/verify-setup", headers=h, data={"code": pyotp.TOTP(secret).now()})
    assert r.status_code == 200, r.text
    return secret, r.json()["recovery_codes"], h


def test_setup_entrega_qr_y_no_habilita_aun(client, db):
    _mk_admin(db)
    h = _auth_headers(client, "adm2fa@test.ec", "ClaveAdmin123!")
    r = client.post("/auth/2fa/setup", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["qr"].startswith("data:image/png;base64,")
    assert client.get("/auth/2fa/status", headers=h).json()["enabled"] is False


def test_verify_setup_habilita_y_da_8_recovery(client, db):
    secret, recovery, h = _enroll(client, db)
    assert len(recovery) == 8
    assert client.get("/auth/2fa/status", headers=h).json()["enabled"] is True


def test_login_exige_codigo_cuando_2fa_activo(client, db):
    secret, recovery, h = _enroll(client, db)
    # sin código → 2FA_REQUIRED
    r = _login(client, "adm2fa@test.ec", "ClaveAdmin123!")
    assert r.status_code == 401 and r.json()["detail"] == "2FA_REQUIRED"
    # código correcto → OK
    assert _login(client, "adm2fa@test.ec", "ClaveAdmin123!", code=pyotp.TOTP(secret).now()).status_code == 200
    # código inválido → 401
    r = _login(client, "adm2fa@test.ec", "ClaveAdmin123!", code="000000")
    assert r.status_code == 401 and "inválido" in r.json()["detail"].lower()


def test_codigo_recuperacion_un_solo_uso(client, db):
    secret, recovery, h = _enroll(client, db)
    rc = recovery[0]
    assert _login(client, "adm2fa@test.ec", "ClaveAdmin123!", code=rc).status_code == 200
    # reuso del mismo código → rechazado
    assert _login(client, "adm2fa@test.ec", "ClaveAdmin123!", code=rc).status_code == 401
    # otro código de recuperación distinto sigue sirviendo
    assert _login(client, "adm2fa@test.ec", "ClaveAdmin123!", code=recovery[1]).status_code == 200


def test_disable_requiere_password(client, db):
    secret, recovery, h = _enroll(client, db, email="adm3@test.ec")
    assert client.post("/auth/2fa/disable", headers=h, data={"password": "mala"}).status_code == 401
    assert client.post("/auth/2fa/disable", headers=h, data={"password": "ClaveAdmin123!"}).status_code == 200
    # login ya no pide código
    assert _login(client, "adm3@test.ec", "ClaveAdmin123!").status_code == 200
