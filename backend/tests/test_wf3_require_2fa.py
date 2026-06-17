"""WF3 — 2FA obligatorio (REQUIRE_2FA) + reset solo super-admin (admin tenant nulo)."""
import pyotp
import pytest
from backend.config import settings
from backend.models.user import User, UserRole
from backend.auth.jwt import hash_password


def _mk(db, email, role=UserRole.monitor, tenant=None, pwd="Clave123!"):
    u = User(email=email, nombre="U", hashed_password=hash_password(pwd),
             role=role, is_active=True, tenant=tenant)
    db.add(u); db.commit(); db.refresh(u)
    return u


def _hdr(client, email, pwd="Clave123!"):
    r = client.post("/auth/login", data={"username": email, "password": pwd})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()


@pytest.fixture
def require_2fa_on():
    old = settings.REQUIRE_2FA
    settings.REQUIRE_2FA = True
    yield
    settings.REQUIRE_2FA = old


def test_login_marca_must_enroll_cuando_obligatorio(client, db, require_2fa_on):
    _mk(db, "sin2fa@test.ec")
    _, body = _hdr(client, "sin2fa@test.ec")
    assert body["user"]["must_enroll_2fa"] is True
    assert body["user"]["totp_enabled"] is False


def test_sin_2fa_bloqueado_pero_puede_enrolar(client, db, require_2fa_on):
    _mk(db, "sin2fa@test.ec")
    h, _ = _hdr(client, "sin2fa@test.ec")
    # endpoint protegido cualquiera → 403 2FA_ENROLLMENT_REQUIRED
    r = client.get("/dashboard/stats?periodo=P68", headers=h)
    assert r.status_code == 403 and r.json()["detail"] == "2FA_ENROLLMENT_REQUIRED"
    # pero SÍ puede usar las rutas de enrolamiento
    assert client.get("/auth/2fa/status", headers=h).status_code == 200
    assert client.get("/auth/me", headers=h).status_code == 200
    # enrolarse
    secret = client.post("/auth/2fa/setup", headers=h).json()["secret"]
    r = client.post("/auth/2fa/verify-setup", headers=h, data={"code": pyotp.TOTP(secret).now()})
    assert r.status_code == 200, r.text
    # tras enrolar (nuevo login con código) ya no está bloqueado
    r = client.post("/auth/login", data={"username": "sin2fa@test.ec", "password": "Clave123!", "code": pyotp.TOTP(secret).now()})
    assert r.status_code == 200
    h2 = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/auth/2fa/status", headers=h2).json()["enabled"] is True


def test_reset_solo_super_admin(client, db):
    # super admin = admin con tenant NULL
    _mk(db, "super@test.ec", UserRole.admin, tenant=None)
    # admin de tenant (NO super)
    _mk(db, "tadmin@test.ec", UserRole.admin, tenant="ups")
    victima = _mk(db, "vic@test.ec", UserRole.monitor)

    # admin de tenant NO puede resetear
    th, _ = _hdr(client, "tadmin@test.ec")
    assert client.post(f"/auth/users/{victima.id}/reset-2fa", headers=th).status_code == 403

    # super admin SÍ puede
    sh, sbody = _hdr(client, "super@test.ec")
    assert sbody["user"]["is_super_admin"] is True
    assert client.post(f"/auth/users/{victima.id}/reset-2fa", headers=sh).status_code == 200
