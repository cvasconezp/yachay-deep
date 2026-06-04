"""
Tests de autenticación — [ARCH-01] Remediación.

Cobertura:
  - Login correcto / incorrecto / usuario inactivo / case-insensitive
  - Endpoint /auth/me con token válido / inválido / sin token
  - CRUD de usuarios (admin vs monitor)
  - Headers de seguridad ([SEC-08])
  - Health check
"""

import pytest
from backend.auth.jwt import hash_password, verify_password, create_access_token
from .conftest import auth


# ═══════════════════ UNIT: jwt.py ═══════════════════

class TestPasswordHashing:
    def test_hash_produces_different_output(self):
        assert hash_password("pass123") != "pass123"

    def test_verify_correct(self):
        h = hash_password("pass123")
        assert verify_password("pass123", h) is True

    def test_verify_incorrect(self):
        h = hash_password("pass123")
        assert verify_password("wrong", h) is False

    def test_different_inputs_different_hashes(self):
        assert hash_password("a") != hash_password("b")


class TestTokenCreation:
    def test_creates_string(self):
        t = create_access_token({"sub": "1"})
        assert isinstance(t, str) and len(t) > 20


# ═══════════════ INTEGRATION: /auth ═══════════════

class TestLogin:
    def test_success(self, client, admin_user):
        r = client.post("/auth/login", data={"username": "admin@test.yachay.edu.ec", "password": "TestPassword123!"})
        assert r.status_code == 200
        d = r.json()
        assert "access_token" in d
        assert d["token_type"] == "bearer"
        assert d["user"]["email"] == "admin@test.yachay.edu.ec"

    def test_wrong_password(self, client, admin_user):
        r = client.post("/auth/login", data={"username": "admin@test.yachay.edu.ec", "password": "wrong"})
        assert r.status_code == 401

    def test_nonexistent_user(self, client):
        r = client.post("/auth/login", data={"username": "noone@test.com", "password": "x"})
        assert r.status_code == 401

    def test_inactive_user(self, client, db):
        from backend.models.user import User, UserRole
        u = User(email="off@test.com", nombre="Off", hashed_password=hash_password("p"), role=UserRole.monitor, is_active=False)
        db.add(u); db.commit()
        r = client.post("/auth/login", data={"username": "off@test.com", "password": "p"})
        assert r.status_code == 403

    def test_case_insensitive_email(self, client, admin_user):
        r = client.post("/auth/login", data={"username": "ADMIN@TEST.YACHAY.EDU.EC", "password": "TestPassword123!"})
        assert r.status_code == 200


class TestMe:
    def test_with_token(self, client, admin_token):
        r = client.get("/auth/me", headers=auth(admin_token))
        assert r.status_code == 200
        assert r.json()["email"] == "admin@test.yachay.edu.ec"

    def test_without_token(self, client):
        assert client.get("/auth/me").status_code == 401

    def test_invalid_token(self, client):
        assert client.get("/auth/me", headers=auth("bad.token.here")).status_code == 401

    def test_expired_token(self, client, admin_user):
        from datetime import timedelta
        t = create_access_token({"sub": str(admin_user.id)}, expires_delta=timedelta(seconds=-10))
        assert client.get("/auth/me", headers=auth(t)).status_code == 401


class TestUserCRUD:
    def test_admin_creates_user(self, client, admin_token):
        r = client.post("/auth/users", headers=auth(admin_token), json={
            "email": "new@test.com", "nombre": "New", "password": "pass12345", "role": "monitor"
        })
        assert r.status_code == 200
        assert r.json()["email"] == "new@test.com"

    def test_monitor_cannot_create(self, client, monitor_token):
        r = client.post("/auth/users", headers=auth(monitor_token), json={
            "email": "x@test.com", "nombre": "X", "password": "pass12345"
        })
        assert r.status_code == 403

    def test_duplicate_email(self, client, admin_token, admin_user):
        r = client.post("/auth/users", headers=auth(admin_token), json={
            "email": "admin@test.yachay.edu.ec", "nombre": "Dup", "password": "pass12345"
        })
        assert r.status_code == 400

    def test_list_users(self, client, admin_token, admin_user):
        r = client.get("/auth/users", headers=auth(admin_token))
        assert r.status_code == 200
        assert len(r.json()) >= 1


# ═══════════════ SECURITY HEADERS ═══════════════

class TestSecurityHeaders:
    """[SEC-08] Verificar headers de seguridad."""

    def test_x_content_type(self, client):
        r = client.get("/health")
        assert r.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame(self, client):
        assert client.get("/health").headers.get("X-Frame-Options") == "DENY"

    def test_csp_present(self, client):
        csp = client.get("/health").headers.get("Content-Security-Policy", "")
        assert "default-src" in csp
        assert "frame-ancestors 'none'" in csp


class TestHealthCheck:
    def test_returns_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
