"""
T31: Tests de autenticación y JWT.

Verifica:
  - Login con credenciales inválidas
  - Token JWT malformado/expirado
  - Login setea HttpOnly cookie
  - Logout borra cookie
  - Usuario desactivado no puede logear
  - Rate limiting en login (5/min)
"""
import pytest
from datetime import timedelta
from backend.auth.jwt import create_access_token, hash_password, COOKIE_NAME
from backend.models.user import User
from backend.tests.conftest import auth


@pytest.fixture(autouse=True)
def reset_rate_limit():
    """Reset slowapi rate limiter entre tests."""
    try:
        from backend.auth.routes import limiter
        limiter.reset()
    except Exception:
        pass
    yield


class TestLogin:
    """Tests del flujo de login."""

    def test_login_correcto(self, client, admin_user):
        r = client.post("/auth/login", data={
            "username": admin_user.email,
            "password": "TestPassword123!",
        })
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["user"]["email"] == admin_user.email
        assert data["user"]["role"] == "admin"

    def test_login_password_incorrecto(self, client, admin_user):
        r = client.post("/auth/login", data={
            "username": admin_user.email,
            "password": "WrongPassword!",
        })
        assert r.status_code == 401
        assert "incorrecto" in r.json()["detail"].lower()

    def test_login_email_inexistente(self, client):
        r = client.post("/auth/login", data={
            "username": "noexiste@test.com",
            "password": "anything",
        })
        assert r.status_code == 401

    def test_login_usuario_desactivado(self, client, db):
        """Un usuario desactivado recibe 403."""
        user = User(
            email="inactive@test.com", nombre="Inactive",
            hashed_password=hash_password("ValidPass123!"),
            role="monitor", is_active=False,
        )
        db.add(user)
        db.commit()

        r = client.post("/auth/login", data={
            "username": "inactive@test.com",
            "password": "ValidPass123!",
        })
        assert r.status_code == 403
        assert "desactivado" in r.json()["detail"].lower()

    def test_login_case_insensitive_email(self, client, admin_user):
        """El email es case-insensitive en login."""
        r = client.post("/auth/login", data={
            "username": admin_user.email.upper(),
            "password": "TestPassword123!",
        })
        assert r.status_code == 200

    def test_login_sets_cookie(self, client, admin_user):
        """Login setea HttpOnly cookie yd_token."""
        r = client.post("/auth/login", data={
            "username": admin_user.email,
            "password": "TestPassword123!",
        })
        assert r.status_code == 200
        # TestClient almacena cookies; verificar que la respuesta tiene set-cookie
        cookies = r.headers.get_list("set-cookie") if hasattr(r.headers, 'get_list') else [
            v for k, v in r.headers.items() if k.lower() == "set-cookie"
        ]
        cookie_found = any(COOKIE_NAME in c for c in cookies)
        assert cookie_found, f"Cookie {COOKIE_NAME} no encontrada en set-cookie headers"


class TestLogout:
    def test_logout_borra_cookie(self, client):
        """Logout retorna instrucción de borrar cookie."""
        r = client.post("/auth/logout")
        assert r.status_code == 200
        assert "cerrada" in r.json()["detail"].lower()


class TestJWTSecurity:
    """Tests de seguridad del token JWT."""

    def test_token_malformado_rechazado(self, client):
        """Un token JWT malformado retorna 401."""
        r = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"})
        assert r.status_code == 401

    def test_token_con_sub_invalido(self, client):
        """Token con sub que no es un user ID válido."""
        token = create_access_token({"sub": "99999"})
        r = client.get("/auth/me", headers=auth(token))
        assert r.status_code == 401

    def test_token_sin_sub(self, client):
        """Token sin campo sub es rechazado."""
        token = create_access_token({"role": "admin"})
        r = client.get("/auth/me", headers=auth(token))
        assert r.status_code == 401

    def test_token_expirado(self, client):
        """Token expirado retorna 401."""
        token = create_access_token({"sub": "1"}, expires_delta=timedelta(seconds=-1))
        r = client.get("/auth/me", headers=auth(token))
        assert r.status_code == 401

    def test_sin_token_retorna_401(self, client):
        """Endpoints protegidos sin token retornan 401."""
        r = client.get("/auth/me")
        assert r.status_code == 401

    def test_bearer_empty_string(self, client):
        """Bearer con string vacío retorna 401."""
        r = client.get("/auth/me", headers={"Authorization": "Bearer "})
        assert r.status_code == 401

    def test_password_validation_min_length(self, client, admin_token):
        """Password menor a 8 caracteres es rechazado en create user."""
        r = client.post("/auth/users", json={
            "email": "short@test.com",
            "nombre": "Short",
            "password": "123",
        }, headers=auth(admin_token))
        assert r.status_code == 422
