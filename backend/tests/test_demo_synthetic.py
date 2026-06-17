"""DEMO — datos sintéticos: tope 6/nivel en malla, historial ML, alertas, etc."""
import backend.routes.demo_seed as ds
from backend.models import (Student, Enrollment, Grade, Intervention,
                            DocenteTracking, ScrapingRun, AlertEvent)
from backend.models.user import User, UserRole
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.database import Base
import pytest
from fastapi import HTTPException


def _factory():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)


def test_solo_super_admin(monkeypatch):
    monkeypatch.setattr(ds, "_get_demo_db", lambda: _factory()())
    no_super = User(email="t@x.ec", nombre="T", hashed_password="x", role=UserRole.admin, tenant="ups")
    with pytest.raises(HTTPException) as e:
        ds.regenerate_synthetic(n_estudiantes=10, current_user=no_super)
    assert e.value.status_code == 403


def test_malla_max_6_por_nivel_por_carrera(monkeypatch):
    Factory = _factory()
    monkeypatch.setattr(ds, "_get_demo_db", lambda: Factory())
    sa = User(email="s@x.ec", nombre="S", hashed_password="x", role=UserRole.admin, tenant=None)
    res = ds.regenerate_synthetic(n_estudiantes=80, current_user=sa)
    assert res["creados"]["estudiantes"] == 80

    db = Factory()
    try:
        # La malla canónica = asignaturas distintas por (carrera, nivel) en Grade.
        rows = db.query(Grade.carrera, Grade.nivel, Grade.asignatura).distinct().all()
        from collections import defaultdict
        por_carrera_nivel = defaultdict(set)
        for carrera, nivel, asig in rows:
            por_carrera_nivel[(carrera, nivel)].add(asig)
        peores = {k: len(v) for k, v in por_carrera_nivel.items() if len(v) > 6}
        assert not peores, f"Niveles con >6 materias: {peores}"

        # cada estudiante: en su nivel actual (matrículas P68) ≤6 materias
        enr = db.query(Enrollment.student_id, func.count(Enrollment.id)).group_by(Enrollment.student_id).all()
        assert all(c <= 6 for _, c in enr)

        # datos nuevos presentes
        assert res["creados"]["calificaciones"] > 0
        assert res["creados"]["seguimiento_docente"] > 0
        assert db.query(ScrapingRun).count() == 6
        # historial multi-periodo para ML
        periodos = {p for (p,) in db.query(Grade.periodo).distinct().all()}
        assert "P68" in periodos and len(periodos) >= 2
    finally:
        db.close()


def test_regenera_limpia(monkeypatch):
    Factory = _factory()
    monkeypatch.setattr(ds, "_get_demo_db", lambda: Factory())
    sa = User(email="s@x.ec", nombre="S", hashed_password="x", role=UserRole.admin, tenant=None)
    ds.regenerate_synthetic(n_estudiantes=20, current_user=sa)
    ds.regenerate_synthetic(n_estudiantes=15, current_user=sa)
    db = Factory()
    try:
        assert db.query(Student).count() == 15
        assert db.query(ScrapingRun).count() == 6
    finally:
        db.close()
