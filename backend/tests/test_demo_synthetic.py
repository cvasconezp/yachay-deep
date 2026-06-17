"""DEMO — generación de datos sintéticos (super-admin, ≤6 materias/semestre)."""
import backend.routes.demo_seed as ds
from backend.models import Student, Enrollment, SemesterConfig
from backend.models.user import User, UserRole
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.database import Base


def _demo_session_factory():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)


def test_solo_super_admin_genera(monkeypatch):
    Factory = _demo_session_factory()
    monkeypatch.setattr(ds, "_get_demo_db", lambda: Factory())

    # admin de tenant (no super) → 403
    no_super = User(email="t@x.ec", nombre="T", hashed_password="x", role=UserRole.admin, tenant="ups")
    import pytest
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        ds.regenerate_synthetic(n_estudiantes=10, current_user=no_super)
    assert exc.value.status_code == 403


def test_genera_datos_y_respeta_tope_6(monkeypatch):
    Factory = _demo_session_factory()
    monkeypatch.setattr(ds, "_get_demo_db", lambda: Factory())
    super_admin = User(email="s@x.ec", nombre="S", hashed_password="x", role=UserRole.admin, tenant=None)

    res = ds.regenerate_synthetic(n_estudiantes=40, current_user=super_admin)
    assert res["creados"]["estudiantes"] == 40
    assert res["creados"]["matriculas"] > 0

    # verificar en la BD demo: nadie supera 6 materias en el semestre
    db = Factory()
    try:
        assert db.query(Student).count() == 40
        assert db.query(SemesterConfig).filter(SemesterConfig.activo == True).count() == 1
        counts = db.query(Enrollment.student_id, func.count(Enrollment.id)) \
                   .group_by(Enrollment.student_id).all()
        assert counts, "debe haber matrículas"
        assert all(c <= 6 for _, c in counts), f"hay estudiantes con >6 materias: {counts}"
        assert all(c >= 4 for _, c in counts)
    finally:
        db.close()


def test_regenera_limpia_lo_anterior(monkeypatch):
    Factory = _demo_session_factory()
    monkeypatch.setattr(ds, "_get_demo_db", lambda: Factory())
    sa = User(email="s@x.ec", nombre="S", hashed_password="x", role=UserRole.admin, tenant=None)
    ds.regenerate_synthetic(n_estudiantes=20, current_user=sa)
    ds.regenerate_synthetic(n_estudiantes=15, current_user=sa)  # segunda corrida
    db = Factory()
    try:
        assert db.query(Student).count() == 15  # no se acumuló
    finally:
        db.close()
