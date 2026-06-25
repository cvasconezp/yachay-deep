"""WF1B — hashing argon2id con rehash transparente desde bcrypt."""
from passlib.context import CryptContext
from backend.auth.jwt import hash_password, verify_password, needs_rehash
from backend.models.user import User, UserRole


def test_nuevo_hash_es_argon2id():
    h = hash_password("MiClaveSegura123!")
    assert h.startswith("$argon2id$")
    assert verify_password("MiClaveSegura123!", h)
    assert not verify_password("otra", h)


def test_bcrypt_viejo_se_verifica_y_marca_rehash():
    bcrypt_ctx = CryptContext(schemes=["bcrypt"])
    viejo = bcrypt_ctx.hash("MiClaveSegura123!")
    # se sigue pudiendo verificar (compatibilidad)
    assert verify_password("MiClaveSegura123!", viejo)
    # pero se marca para rehash
    assert needs_rehash(viejo) is True
    # un argon2 fresco NO necesita rehash
    assert needs_rehash(hash_password("x")) is False


def test_login_migra_hash_bcrypt_a_argon2(client, db):
    bcrypt_ctx = CryptContext(schemes=["bcrypt"])
    u = User(email="viejo@test.ec", nombre="Viejo",
             hashed_password=bcrypt_ctx.hash("ClaveVieja123!"),
             role=UserRole.admin, is_active=True)
    db.add(u); db.commit()
    assert u.hashed_password.startswith("$2")  # bcrypt
    r = client.post("/auth/login", data={"username": "viejo@test.ec", "password": "ClaveVieja123!"})
    assert r.status_code == 200, r.text
    db.refresh(u)
    assert u.hashed_password.startswith("$argon2id$")  # migrado
