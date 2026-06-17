"""Regresión WF3: el enrolamiento 2FA debe persistir aunque get_db y get_prod_db
sean sesiones DISTINTAS (como en producción). Antes fallaba con
'Primero llama a /2fa/setup' porque se commiteaba la sesión equivocada."""
import pyotp
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db, get_prod_db
from backend.main import app
from backend.models.user import User, UserRole
from backend.auth.jwt import hash_password, create_access_token


def test_2fa_persiste_con_sesiones_separadas():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)

    s0 = Session()
    u = User(email="sep@test.ec", nombre="Sep", hashed_password=hash_password("Clave123!"),
             role=UserRole.admin, is_active=True)
    s0.add(u); s0.commit(); uid = u.id; s0.close()

    # get_db y get_prod_db → sesiones independientes sobre el mismo engine (como prod)
    def ov_db():
        d = Session()
        try: yield d
        finally: d.close()
    def ov_prod():
        d = Session()
        try: yield d
        finally: d.close()

    from backend.auth.routes import limiter
    limiter.enabled = False
    app.dependency_overrides[get_db] = ov_db
    app.dependency_overrides[get_prod_db] = ov_prod
    try:
        c = TestClient(app)
        h = {"Authorization": f"Bearer {create_access_token({'sub': str(uid)})}"}

        r = c.post("/auth/2fa/setup", headers=h)
        assert r.status_code == 200, r.text
        secret = r.json()["secret"]

        # el secreto DEBE haberse persistido (releer en sesión fresca)
        s1 = Session(); usr = s1.get(User, uid)
        assert usr.totp_secret == secret, "totp_secret no se persistió (bug de sesión)"
        s1.close()

        r = c.post("/auth/2fa/verify-setup", headers=h, data={"code": pyotp.TOTP(secret).now()})
        assert r.status_code == 200, r.text
        assert len(r.json()["recovery_codes"]) == 8
    finally:
        app.dependency_overrides.clear()
