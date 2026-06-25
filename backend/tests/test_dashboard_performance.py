"""
Tests para Dashboard Performance — Fase 2 T16.

Cobertura:
  - GET /dashboard/risk con 2,000+ estudiantes responde en <2s
  - GET /dashboard/stats con volumen alto
"""
import time
import pytest

from backend.models import Student, Grade
from backend.models.course_config import SemesterConfig
from backend.tests.conftest import auth


@pytest.fixture
def semester_config(db):
    sc = SemesterConfig(semestre="P68", activo=True, bloque_actual="1")
    db.add(sc)
    db.commit()
    return sc


@pytest.fixture
def bulk_students(db, semester_config):
    """Crea 2,000 estudiantes con datos variados para test de performance."""
    niveles_riesgo = ["Alto", "Moderado", "Bajo", None]
    carreras = ["EDUCACION BASICA", "DERECHO", "PSICOLOGIA", "COMUNICACION", "CONTABILIDAD"]

    students = []
    for i in range(1, 2001):
        s = Student(
            nombre=f"ALUMNO BULK {i:04d}",
            carrera=carreras[i % len(carreras)],
            nivel_academico=min(7, (i % 7) + 1),
            nivel_riesgo=niveles_riesgo[i % len(niveles_riesgo)],
            indice_compromiso=0.1 + (i % 90) / 100,
            dias_sin_acceso=i % 30,
            porcentaje_tareas=20.0 + (i % 80),
            prob_desercion=0.1 + (i % 80) / 100,
            prob_reprobacion=0.05 + (i % 90) / 100,
            estado_matricula="Matriculado",
        )
        students.append(s)

    db.add_all(students)
    db.commit()
    return students


# ═══════════════════ T16: Dashboard Performance ═══════════════════


class TestDashboardPerformance:
    """T16: Dashboard con volumen alto responde rapido."""

    def test_risk_dashboard_with_2000_students(self, client, monitor_token, bulk_students):
        """GET /dashboard/risk con 2,000 estudiantes responde en <2s."""
        start = time.time()
        r = client.get("/dashboard/risk", headers=auth(monitor_token))
        elapsed = time.time() - start

        assert r.status_code == 200
        assert elapsed < 2.0, f"Dashboard too slow: {elapsed:.2f}s (limit: 2s)"

        data = r.json()
        assert isinstance(data, list)

    def test_stats_with_2000_students(self, client, monitor_token, bulk_students):
        """GET /dashboard/stats responde rapidamente."""
        start = time.time()
        r = client.get("/dashboard/stats", headers=auth(monitor_token))
        elapsed = time.time() - start

        assert r.status_code == 200
        assert elapsed < 2.0, f"Stats too slow: {elapsed:.2f}s"

    def test_risk_dashboard_returns_students(self, client, monitor_token, bulk_students):
        """El dashboard retorna estudiantes con campos esperados."""
        r = client.get("/dashboard/risk", headers=auth(monitor_token))
        data = r.json()

        if len(data) > 0:
            student = data[0]
            # Debe tener campos basicos del schema RiskStudentOut
            assert "id" in student or "nombre" in student

    def test_carreras_endpoint_performance(self, client, monitor_token, bulk_students):
        """GET /dashboard/carreras responde rapido con datos masivos."""
        start = time.time()
        r = client.get("/dashboard/carreras", headers=auth(monitor_token))
        elapsed = time.time() - start

        assert r.status_code == 200
        assert elapsed < 2.0
        carreras = r.json()
        assert len(carreras) >= 3  # Al menos 3 de las 5 carreras
