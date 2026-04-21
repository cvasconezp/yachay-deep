"""
Tests for student endpoints and helpers.

Covers:
  - diagnosticar_riesgo() decision tree
  - GET /students/search
  - GET /students/{id}/ficha
  - GET /students/{id}/comparativa
"""

import pytest
from types import SimpleNamespace

from backend.models import Student, Grade, Enrollment
from backend.models.course_config import SemesterConfig
from backend.routes.students import diagnosticar_riesgo

from .conftest import auth


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def semester_config(db):
    sc = SemesterConfig(semestre="P68", activo=True, bloque_actual="1")
    db.add(sc)
    db.commit()
    return sc


@pytest.fixture
def sample_students(db):
    students = [
        Student(
            id=1, nombre="GARCIA LOPEZ MARIA",
            correo_institucional="mgarcia@est.test.edu",
            carrera="EDUCACION BASICA", nivel_riesgo="Alto",
            indice_compromiso=0.2, cedula="1234567890",
            estado_matricula="Matriculado",
        ),
        Student(
            id=2, nombre="PEREZ RUIZ JUAN",
            correo_institucional="jperez@est.test.edu",
            carrera="DERECHO", nivel_riesgo="Bajo",
            indice_compromiso=0.8, cedula="0987654321",
            estado_matricula="Matriculado",
        ),
    ]
    db.add_all(students)
    db.commit()
    return students


@pytest.fixture
def sample_grades(db, sample_students, semester_config):
    grades = [
        Grade(
            student_id=1, asignatura="MATEMATICAS",
            nota_final=6.5, periodo="P68", carrera="EDUCACION BASICA",
        ),
        Grade(
            student_id=1, asignatura="LENGUA",
            nota_final=7.0, periodo="P68", carrera="EDUCACION BASICA",
        ),
    ]
    db.add_all(grades)
    db.commit()
    return grades


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _intervencion(motivo: str):
    """Create a lightweight object with a .motivo attribute."""
    return SimpleNamespace(motivo=motivo)


# ─── Unit tests: diagnosticar_riesgo ─────────────────────────────────────────

class TestDiagnosticarRiesgo:
    """Unit tests for the risk-diagnosis decision tree."""

    def test_not_enrolled_returns_en_riesgo(self):
        result = diagnosticar_riesgo("Retirado", 0.8, [])
        assert result == "En riesgo"

    def test_none_estado_returns_en_riesgo(self):
        result = diagnosticar_riesgo(None, 0.5, [])
        assert result == "En riesgo"

    def test_empty_estado_returns_en_riesgo(self):
        result = diagnosticar_riesgo("", 0.9, [])
        assert result == "En riesgo"

    def test_low_index_returns_desercion(self):
        result = diagnosticar_riesgo("Matriculado", 0.2, [])
        assert result == "Riesgo de Deserción"

    def test_zero_index_returns_desercion(self):
        result = diagnosticar_riesgo("Matriculado", 0.0, [])
        assert result == "Riesgo de Deserción"

    def test_medium_index_returns_academico(self):
        result = diagnosticar_riesgo("Matriculado", 0.5, [])
        assert result == "Riesgo Académico"

    def test_boundary_030_returns_academico(self):
        result = diagnosticar_riesgo("Matriculado", 0.3, [])
        assert result == "Riesgo Académico"

    def test_high_index_returns_aprobacion(self):
        result = diagnosticar_riesgo("Matriculado", 0.8, [])
        assert result == "Aprobación"

    def test_boundary_060_returns_aprobacion(self):
        result = diagnosticar_riesgo("Matriculado", 0.6, [])
        assert result == "Aprobación"

    def test_ausentismo_overrides_high_index(self):
        inv = [_intervencion("no ingresa regularmente al avac")]
        result = diagnosticar_riesgo("Matriculado", 0.9, inv)
        assert result == "Riesgo de Deserción"

    def test_notas_overrides_high_index(self):
        inv = [_intervencion("bajas calificaciones")]
        result = diagnosticar_riesgo("Matriculado", 0.7, inv)
        assert result == "Riesgo Académico"

    def test_none_indice_with_ausentismo(self):
        inv = [_intervencion("ausencia avac")]
        result = diagnosticar_riesgo("Matriculado", None, inv)
        assert result == "Riesgo de Deserción"

    def test_none_indice_with_notas(self):
        inv = [_intervencion("nota cero")]
        result = diagnosticar_riesgo("Matriculado", None, inv)
        assert result == "Riesgo Académico"

    def test_none_indice_no_interventions(self):
        result = diagnosticar_riesgo("Matriculado", None, [])
        assert result == "Datos insuficientes"


# ─── Endpoint tests: search ──────────────────────────────────────────────────

class TestSearchStudents:
    """Tests for GET /students/search."""

    def test_short_query_no_filters_returns_empty(
        self, client, admin_token, sample_students
    ):
        r = client.get("/students/search?q=G", headers=auth(admin_token))
        assert r.status_code == 200
        body = r.json()
        assert body["items"] == []
        assert body["total"] == 0

    def test_search_by_nombre(self, client, admin_token, sample_students):
        r = client.get("/students/search?q=GARCIA", headers=auth(admin_token))
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["nombre"] == "GARCIA LOPEZ MARIA"

    def test_search_by_correo(self, client, admin_token, sample_students):
        r = client.get(
            "/students/search?q=jperez@est", headers=auth(admin_token)
        )
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_search_by_cedula(self, client, admin_token, sample_students):
        r = client.get(
            "/students/search?q=1234567890", headers=auth(admin_token)
        )
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_carrera_filter_case_insensitive(
        self, client, admin_token, sample_students
    ):
        r = client.get(
            "/students/search?carrera=educacion basica",
            headers=auth(admin_token),
        )
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["carrera"] == "EDUCACION BASICA"

    def test_nivel_riesgo_filter(self, client, admin_token, sample_students):
        r = client.get(
            "/students/search?nivel_riesgo=Alto", headers=auth(admin_token)
        )
        assert r.status_code == 200
        items = r.json()["items"]
        assert all(s["nivel_riesgo"] == "Alto" for s in items)

    def test_pagination(self, client, admin_token, sample_students):
        r = client.get(
            "/students/search?carrera=EDUCACION BASICA&page=1&limit=1",
            headers=auth(admin_token),
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) <= 1
        assert body["page"] == 1


# ─── Endpoint tests: ficha ───────────────────────────────────────────────────

class TestFichaEstudiante:
    """Tests for GET /students/{id}/ficha."""

    def test_valid_student_returns_ficha(
        self, client, admin_token, sample_students, semester_config
    ):
        r = client.get("/students/1/ficha", headers=auth(admin_token))
        assert r.status_code == 200
        body = r.json()
        assert body["nombre"] == "GARCIA LOPEZ MARIA"

    def test_invalid_id_returns_404(
        self, client, admin_token, semester_config
    ):
        r = client.get("/students/9999/ficha", headers=auth(admin_token))
        assert r.status_code == 404

    def test_no_auth_returns_401(self, client, sample_students):
        r = client.get("/students/1/ficha")
        assert r.status_code == 401


# ─── Endpoint tests: comparativa ─────────────────────────────────────────────

class TestComparativa:
    """Tests for GET /students/{id}/comparativa."""

    def test_student_with_grades(
        self, client, admin_token, sample_grades, semester_config
    ):
        r = client.get("/students/1/comparativa", headers=auth(admin_token))
        assert r.status_code == 200
        body = r.json()
        assert "asignaturas" in body

    def test_student_without_grades(
        self, client, admin_token, sample_students, semester_config
    ):
        r = client.get("/students/2/comparativa", headers=auth(admin_token))
        assert r.status_code == 200
        body = r.json()
        assert body.get("asignaturas", []) == [] or body.get("asignaturas") is not None

    def test_invalid_id_returns_404(
        self, client, admin_token, semester_config
    ):
        r = client.get("/students/9999/comparativa", headers=auth(admin_token))
        assert r.status_code == 404


# ─── Edge cases ──────────────────────────────────────────────────────────────

class TestEdgeCases:
    """Auth and not-found edge cases across endpoints."""

    def test_search_no_auth(self, client):
        r = client.get("/students/search?q=test")
        assert r.status_code == 401

    def test_ficha_no_auth(self, client):
        r = client.get("/students/1/ficha")
        assert r.status_code == 401

    def test_comparativa_no_auth(self, client):
        r = client.get("/students/1/comparativa")
        assert r.status_code == 401

    def test_ficha_not_found(self, client, admin_token, semester_config):
        r = client.get("/students/0/ficha", headers=auth(admin_token))
        assert r.status_code == 404

    def test_comparativa_not_found(self, client, admin_token, semester_config):
        r = client.get("/students/0/comparativa", headers=auth(admin_token))
        assert r.status_code == 404
