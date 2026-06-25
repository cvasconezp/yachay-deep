"""Opción B: _create_default_admin no sobrescribe admin existente (salvo ADMIN_RESET)."""
import os
import backend.main as bm
import backend.database as bd
from backend.models.user import User, UserRole
from backend.auth.jwt import hash_password, verify_password
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.database import Base


def _patch_sessionlocal(monkeypatch):
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    Factory = sessionmaker(bind=eng)
    monkeypatch.setattr(bd, "SessionLocal", Factory)
    return Factory


def test_no_sobrescribe_admin_existente(monkeypatch):
    Factory = _patch_sessionlocal(monkeypatch)
    monkeypatch.setenv("ADMIN_EMAIL", "bootstrap@x.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "BootPass123!")
    monkeypatch.delenv("ADMIN_RESET", raising=False)
    db = Factory()
    db.add(User(email="cambiado@x.com", nombre="A", hashed_password=hash_password("MiClaveReal1!"),
                role=UserRole.admin, is_active=True))
    db.commit(); db.close()

    bm._create_default_admin()

    db = Factory()
    # el admin existente NO cambió de correo ni de clave
    assert db.query(User).filter(User.email == "cambiado@x.com").count() == 1
    assert db.query(User).filter(User.email == "bootstrap@x.com").count() == 0
    u = db.query(User).filter(User.email == "cambiado@x.com").first()
    assert verify_password("MiClaveReal1!", u.hashed_password)
    db.close()


def test_admin_reset_fuerza(monkeypatch):
    Factory = _patch_sessionlocal(monkeypatch)
    monkeypatch.setenv("ADMIN_EMAIL", "bootstrap@x.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "BootPass123!")
    monkeypatch.setenv("ADMIN_RESET", "true")
    db = Factory()
    db.add(User(email="cambiado@x.com", nombre="A", hashed_password=hash_password("vieja"),
                role=UserRole.admin, is_active=True))
    db.commit(); db.close()

    bm._create_default_admin()

    db = Factory()
    u = db.query(User).filter(User.role == UserRole.admin).first()
    assert u.email == "bootstrap@x.com"
    assert verify_password("BootPass123!", u.hashed_password)
    db.close()


def test_crea_si_no_hay_admin(monkeypatch):
    Factory = _patch_sessionlocal(monkeypatch)
    monkeypatch.setenv("ADMIN_EMAIL", "bootstrap@x.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "BootPass123!")
    monkeypatch.delenv("ADMIN_RESET", raising=False)
    bm._create_default_admin()
    db = Factory()
    assert db.query(User).filter(User.email == "bootstrap@x.com").count() == 1
    db.close()
