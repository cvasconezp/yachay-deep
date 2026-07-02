"""
Configuración de pytest para Yachay Deep.

REMEDIACIÓN:
  [ARCH-01] Infraestructura de testing completa con BD aislada
"""

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Forzar entorno de test ANTES de importar la app
os.environ["DATABASE_URL"] = "sqlite://"  # BD en memoria
os.environ["SECRET_KEY"] = "test-secret-key-DO-NOT-USE-IN-PRODUCTION-abc123"
os.environ["DEBUG"] = "True"
os.environ["ADMIN_EMAIL"] = "admin@test.yachay.edu.ec"
os.environ["ADMIN_PASSWORD"] = "TestPassword123!"
# [Cifrado en reposo] Llaves de TEST (no usar en prod) para ejercitar el dual-write.
os.environ["ENC_KEYS"] = "VmKKWyyCCl43l_U5AalkRRHVAXaRBVwAGq2jJQ9dvow="
os.environ["BLIND_INDEX_KEY"] = "5d55e351c661de0aad9760dc68e95b074488a1d7ccbbb9d1f1fd3b5d6f2f70ce"

from backend.database import Base, get_db, get_prod_db
from backend.main import app

# Desactivar rate limiting en tests (evita 429 al hacer múltiples logins)
try:
    from backend.auth.routes import limiter as _auth_limiter
    _auth_limiter.enabled = False
except Exception:
    pass
from backend.models.user import User, UserRole
from backend.auth.jwt import hash_password, create_access_token

# BD SQLite en memoria con StaticPool para compartir entre threads
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    """Crea tablas frescas para cada test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    """Sesión de BD aislada."""
    session = TestSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(db):
    """TestClient con BD de test inyectada."""
    def _override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    app.dependency_overrides[get_prod_db] = _override  # auth usa get_prod_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db):
    """Crea usuario admin."""
    user = User(
        email="admin@test.yachay.edu.ec",
        nombre="Admin Test",
        hashed_password=hash_password("TestPassword123!"),
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def monitor_user(db):
    """Crea usuario monitor."""
    user = User(
        email="monitor@test.yachay.edu.ec",
        nombre="Monitor Test",
        hashed_password=hash_password("TestPassword123!"),
        role=UserRole.monitor,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user):
    """Token JWT válido de admin."""
    return create_access_token({"sub": str(admin_user.id)})


@pytest.fixture
def monitor_token(monitor_user):
    """Token JWT válido de monitor."""
    return create_access_token({"sub": str(monitor_user.id)})


def auth(token: str) -> dict:
    """Helper: headers de Authorization."""
    return {"Authorization": f"Bearer {token}"}
