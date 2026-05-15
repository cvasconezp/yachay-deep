"""
T30: Tests RBAC — permisos admin vs monitor.

Verifica que:
  - Endpoints de admin rechazan monitores con 403
  - Monitores acceden a sus recursos correctamente
  - Usuarios no autenticados reciben 401
"""
import pytest
from backend.tests.conftest import auth


class TestAdminOnlyEndpoints:
    """Endpoints que requieren rol admin."""

    ADMIN_ENDPOINTS = [
        ("POST", "/admin/etl/run", {}),
        ("GET", "/admin/etl/runs"),
        ("GET", "/admin/system/status"),
        ("POST", "/auth/users", {"email": "x@x.com", "nombre": "X", "password": "12345678"}),
        ("GET", "/auth/users"),
        ("POST", "/predictions/train", {}),
        ("POST", "/predictions/run", {}),
    ]

    @pytest.mark.parametrize("method,path", [(e[0], e[1]) for e in ADMIN_ENDPOINTS])
    def test_monitor_rejected_from_admin_endpoints(self, client, monitor_token, method, path):
        """Monitores reciben 403 en endpoints de admin."""
        headers = auth(monitor_token)
        if method == "GET":
            r = client.get(path, headers=headers)
        else:
            body = next((e[2] for e in self.ADMIN_ENDPOINTS if e[1] == path and len(e) > 2), {})
            r = client.post(path, json=body, headers=headers)
        assert r.status_code == 403, f"{method} {path} devolvió {r.status_code}, esperaba 403"

    @pytest.mark.parametrize("method,path", [(e[0], e[1]) for e in ADMIN_ENDPOINTS])
    def test_unauthenticated_rejected(self, client, method, path):
        """Sin autenticación reciben 401."""
        if method == "GET":
            r = client.get(path)
        else:
            r = client.post(path, json={})
        assert r.status_code == 401, f"{method} {path} devolvió {r.status_code}, esperaba 401"


class TestMonitorAccess:
    """Endpoints que monitores SI pueden acceder."""

    MONITOR_ENDPOINTS = [
        ("GET", "/auth/me"),
        ("GET", "/dashboard/carreras"),
        ("GET", "/dashboard/stats"),
        ("GET", "/dashboard/risk"),
    ]

    @pytest.mark.parametrize("method,path", MONITOR_ENDPOINTS)
    def test_monitor_can_access_read_endpoints(self, client, monitor_token, method, path):
        """Monitores acceden normalmente a endpoints de lectura."""
        r = client.get(path, headers=auth(monitor_token))
        assert r.status_code == 200, f"Monitor rechazado de {path}: {r.status_code}"

    @pytest.mark.parametrize("method,path", MONITOR_ENDPOINTS)
    def test_admin_can_also_access(self, client, admin_token, method, path):
        """Admin también accede a los endpoints de monitor."""
        r = client.get(path, headers=auth(admin_token))
        assert r.status_code == 200


class TestUserManagement:
    """Tests de gestión de usuarios (solo admin)."""

    def test_admin_can_create_user(self, client, admin_token):
        r = client.post("/auth/users", json={
            "email": "nuevo@test.com",
            "nombre": "Nuevo Usuario",
            "password": "SecurePass123!",
            "role": "monitor",
        }, headers=auth(admin_token))
        assert r.status_code == 200
        assert r.json()["email"] == "nuevo@test.com"
        assert r.json()["role"] == "monitor"

    def test_monitor_cannot_create_user(self, client, monitor_token):
        r = client.post("/auth/users", json={
            "email": "hack@test.com",
            "nombre": "Hacker",
            "password": "12345678",
        }, headers=auth(monitor_token))
        assert r.status_code == 403

    def test_duplicate_email_rejected(self, client, admin_token, admin_user):
        """No se puede crear usuario con email duplicado."""
        r = client.post("/auth/users", json={
            "email": admin_user.email,
            "nombre": "Duplicate",
            "password": "12345678",
        }, headers=auth(admin_token))
        assert r.status_code == 400
        assert "registrado" in r.json()["detail"].lower()

    def test_admin_can_deactivate_user(self, client, admin_token, db):
        """Admin puede desactivar un usuario."""
        from backend.models.user import User
        from backend.auth.jwt import hash_password
        user = User(email="deactivate@test.com", nombre="Test",
                     hashed_password=hash_password("12345678"), role="monitor")
        db.add(user)
        db.commit()

        r = client.patch(f"/auth/users/{user.id}",
                         json={"is_active": False},
                         headers=auth(admin_token))
        assert r.status_code == 200
        assert r.json()["is_active"] is False
