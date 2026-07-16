"""ADMIN_RESET: la única vía de recuperación si se pierde la contraseña de admin.

No hay servicio de correo, así que no puede haber enlace de restablecimiento — y un
"restablecer" abierto en el login sería una puerta trasera: cualquiera podría resetear al
admin. La recuperación se autoriza teniendo acceso a las variables de entorno del
despliegue, que es lo que demuestra que eres el dueño.

BUG QUE ARREGLAN ESTOS TESTS: la comprobación de ADMIN_RESET iba DESPUÉS de un `return`
temprano que saltaba cuando el correo del admin coincidía con ADMIN_EMAIL — es decir, en
el caso normal. La recuperación era inalcanzable justo cuando hacía falta.
"""
import backend.main as bm
import backend.database as bd
from backend.models.user import User, UserRole
from backend.auth.jwt import hash_password, verify_password
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.database import Base

EMAIL = "carlos@yachaydeep.com"
NUEVA = "NuevaClaveSegura123!"


def _factory(monkeypatch):
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    F = sessionmaker(bind=eng)
    monkeypatch.setattr(bd, "SessionLocal", F)
    monkeypatch.setenv("ADMIN_EMAIL", EMAIL)
    monkeypatch.setenv("ADMIN_PASSWORD", NUEVA)
    return F


def _sembrar(F, email=EMAIL, **kw):
    db = F()
    db.add(User(email=email, nombre="Admin", hashed_password=hash_password("ClaveVieja1!"),
                role=UserRole.admin, is_active=True, **kw))
    db.commit(); db.close()


def test_resetea_aunque_el_correo_coincida(monkeypatch):
    """EL BUG: con el correo igual a ADMIN_EMAIL, el reseteo nunca llegaba a ejecutarse."""
    F = _factory(monkeypatch)
    monkeypatch.setenv("ADMIN_RESET", "true")
    _sembrar(F)

    bm._create_default_admin()

    db = F()
    u = db.query(User).filter(User.email == EMAIL).first()
    assert verify_password(NUEVA, u.hashed_password), (
        "ADMIN_RESET debe funcionar aunque el correo ya coincida: es el caso normal"
    )


def test_resetea_si_el_correo_cambio_en_la_app(monkeypatch):
    F = _factory(monkeypatch)
    monkeypatch.setenv("ADMIN_RESET", "true")
    _sembrar(F, email="otro@correo.com")

    bm._create_default_admin()

    db = F()
    u = db.query(User).filter(User.role == UserRole.admin).first()
    assert u.email == EMAIL
    assert verify_password(NUEVA, u.hashed_password)


def test_el_reseteo_desactiva_el_2fa(monkeypatch):
    """Sin esto, quien perdió la clave Y el segundo factor seguiría fuera."""
    F = _factory(monkeypatch)
    monkeypatch.setenv("ADMIN_RESET", "true")
    _sembrar(F, totp_enabled=True, totp_secret="SECRETO", recovery_codes=["x"])

    bm._create_default_admin()

    db = F()
    u = db.query(User).filter(User.email == EMAIL).first()
    assert u.totp_enabled is False
    assert u.totp_secret is None
    assert u.recovery_codes is None


def test_reactiva_un_admin_desactivado(monkeypatch):
    F = _factory(monkeypatch)
    monkeypatch.setenv("ADMIN_RESET", "true")
    _sembrar(F)
    db = F(); db.query(User).first().is_active = False; db.commit(); db.close()

    bm._create_default_admin()

    db = F()
    assert db.query(User).filter(User.email == EMAIL).first().is_active is True


def test_sin_admin_reset_no_toca_la_clave(monkeypatch):
    """Lo normal: cada arranque respeta lo que se cambió en la app."""
    F = _factory(monkeypatch)
    monkeypatch.delenv("ADMIN_RESET", raising=False)
    _sembrar(F)

    bm._create_default_admin()

    db = F()
    u = db.query(User).filter(User.email == EMAIL).first()
    assert verify_password("ClaveVieja1!", u.hashed_password), (
        "sin ADMIN_RESET, el arranque no debe pisar la contraseña"
    )


def test_sin_admin_reset_no_desactiva_el_2fa(monkeypatch):
    """El 2FA solo se limpia en una recuperación explícita, nunca de rutina."""
    F = _factory(monkeypatch)
    monkeypatch.delenv("ADMIN_RESET", raising=False)
    _sembrar(F, totp_enabled=True, totp_secret="SECRETO")

    bm._create_default_admin()

    db = F()
    u = db.query(User).filter(User.email == EMAIL).first()
    assert u.totp_enabled is True
    assert u.totp_secret == "SECRETO"
