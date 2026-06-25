"""WF4 — refresh tokens con rotación, detección de reuso, revocación en logout."""
from backend.models.user import User, UserRole
from backend.models.refresh_token import RefreshToken
from backend.auth.jwt import hash_password


def _mk(db, email="ref@test.ec", pwd="ClaveRef123!"):
    u = User(email=email, nombre="U", hashed_password=hash_password(pwd),
             role=UserRole.admin, is_active=True)
    db.add(u); db.commit(); db.refresh(u)
    return u


def _login(client, email="ref@test.ec", pwd="ClaveRef123!"):
    return client.post("/auth/login", data={"username": email, "password": pwd})


def test_login_emite_refresh_token(client, db):
    _mk(db)
    r = _login(client)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("refresh_token")
    assert db.query(RefreshToken).count() == 1
    assert db.query(RefreshToken).first().revoked is False


def test_refresh_rota_y_revoca_el_viejo(client, db):
    _mk(db)
    old_refresh = _login(client).json()["refresh_token"]
    client.cookies.clear()  # forzar uso del body, no cookie
    r = client.post("/auth/refresh", data={"refresh_token": old_refresh})
    assert r.status_code == 200, r.text
    new_refresh = r.json()["refresh_token"]
    assert new_refresh and new_refresh != old_refresh
    # el viejo quedó revocado y apunta al nuevo
    from backend.auth.jwt import decode_token
    old_jti = decode_token(old_refresh)["jti"]
    rec = db.query(RefreshToken).filter(RefreshToken.id == old_jti).first()
    assert rec.revoked is True and rec.replaced_by is not None


def test_deteccion_de_reuso_revoca_cadena(client, db):
    _mk(db)
    old_refresh = _login(client).json()["refresh_token"]
    client.cookies.clear()
    # primer refresh OK
    assert client.post("/auth/refresh", data={"refresh_token": old_refresh}).status_code == 200
    # reusar el viejo (ya revocado) → 401 y revoca TODOS los tokens del usuario
    r = client.post("/auth/refresh", data={"refresh_token": old_refresh})
    assert r.status_code == 401
    activos = db.query(RefreshToken).filter(RefreshToken.revoked == False).count()
    assert activos == 0


def test_refresh_token_no_sirve_como_access(client, db):
    _mk(db)
    refresh = _login(client).json()["refresh_token"]
    # usar el refresh como Bearer contra /auth/me debe fallar
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {refresh}"})
    assert r.status_code == 401


def test_logout_revoca_refresh(client, db):
    _mk(db)
    refresh = _login(client).json()["refresh_token"]
    client.post("/auth/logout", data={"refresh_token": refresh})
    # tras logout, el refresh ya no se puede usar
    client.cookies.clear()
    r = client.post("/auth/refresh", data={"refresh_token": refresh})
    assert r.status_code == 401
