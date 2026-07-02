"""[SEC-03] Bloqueo por PIN enforced en servidor.

Verifica que al bloquear la sesión, las rutas protegidas responden 423 hasta
verificar el PIN — de modo que un reload no da acceso sin el PIN.
"""
from .conftest import auth

PIN = "135791"
PWD = "TestPassword123!"


def _set_pin(client, token):
    return client.post("/auth/set-pin", headers=auth(token),
                       json={"pin": PIN, "password": PWD})


class TestPinLock:
    def test_lock_bloquea_rutas_protegidas_y_pin_desbloquea(self, client, admin_token):
        assert _set_pin(client, admin_token).status_code == 200

        # antes de bloquear: ruta protegida accesible
        assert client.get("/auth/2fa/status", headers=auth(admin_token)).status_code == 200

        # bloquear
        r = client.post("/auth/lock", headers=auth(admin_token))
        assert r.status_code == 200 and r.json()["locked"] is True

        # ruta protegida ahora 423 (un reload no ayuda)
        assert client.get("/auth/2fa/status", headers=auth(admin_token)).status_code == 423

        # /auth/me sigue accesible y reporta locked=true (para re-mostrar el bloqueo)
        me = client.get("/auth/me", headers=auth(admin_token))
        assert me.status_code == 200 and me.json().get("locked") is True

        # PIN incorrecto no desbloquea
        assert client.post("/auth/verify-pin", headers=auth(admin_token),
                           json={"pin": "000000"}).status_code == 401
        assert client.get("/auth/2fa/status", headers=auth(admin_token)).status_code == 423

        # PIN correcto desbloquea
        assert client.post("/auth/verify-pin", headers=auth(admin_token),
                           json={"pin": PIN}).status_code == 200
        assert client.get("/auth/2fa/status", headers=auth(admin_token)).status_code == 200

    def test_login_desbloquea_sesion(self, client, admin_token):
        _set_pin(client, admin_token)
        client.post("/auth/lock", headers=auth(admin_token))
        # login limpio debe dejar la sesión desbloqueada
        r = client.post("/auth/login", data={"username": "admin@test.yachay.edu.ec", "password": PWD})
        assert r.status_code == 200
        me = client.get("/auth/me", headers=auth(admin_token))
        assert me.json().get("locked") is False
