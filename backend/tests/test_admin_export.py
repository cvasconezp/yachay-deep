"""
Tests de endpoints Admin y Export — [ARCH-01] Remediación.

Cobertura:
  - Admin: ETL trigger, ETL runs, system status, AVAC cookie, deduplication
  - Export: columnas disponibles, estudiantes Excel, intervenciones Excel, ficha PDF
"""

import pytest
from unittest.mock import patch, MagicMock

from backend.models import Student, Grade, Intervention
from backend.models.course_config import SemesterConfig
from .conftest import auth


# ═══════════════════ FIXTURES ═══════════════════


@pytest.fixture
def semester_config(db):
    sc = SemesterConfig(semestre="P68", activo=True, bloque_actual="1")
    db.add(sc)
    db.commit()
    return sc


@pytest.fixture
def sample_students(db):
    students = [
        Student(id=1, nombre="GARCIA LOPEZ MARIA", carrera="EDUCACION BASICA",
                cedula="1234567890", nivel_riesgo="Alto", indice_compromiso=0.3),
        Student(id=2, nombre="PEREZ RUIZ JUAN", carrera="DERECHO",
                cedula="0987654321", nivel_riesgo="Bajo", indice_compromiso=0.8),
    ]
    db.add_all(students)
    db.commit()
    return students


@pytest.fixture
def sample_grades(db, sample_students):
    grades = [
        Grade(student_id=1, asignatura="MATEMATICAS", docente="DOCENTE1",
              carrera="EDUCACION BASICA", nota_final=55, periodo="P68"),
    ]
    db.add_all(grades)
    db.commit()
    return grades


@pytest.fixture
def sample_interventions(db, sample_students, admin_user):
    interventions = [
        Intervention(student_id=1, monitor_id=admin_user.id, monitor_nombre="Admin",
                     medio="WhatsApp", motivo="Inactividad", estado="Contactado"),
    ]
    db.add_all(interventions)
    db.commit()
    return interventions


# ═══════════════════ ADMIN: POST /admin/etl/run ═══════════════════


class TestTriggerETL:
    @patch("backend.routes.admin._run_etl_background")
    def test_admin_can_trigger_etl(self, mock_etl, client, admin_token):
        resp = client.post("/admin/etl/run", headers=auth(admin_token))
        assert resp.status_code == 200
        assert "ETL" in resp.json()["message"]

    def test_monitor_forbidden(self, client, monitor_token):
        resp = client.post("/admin/etl/run", headers=auth(monitor_token))
        assert resp.status_code == 403

    def test_no_auth_401(self, client):
        resp = client.post("/admin/etl/run")
        assert resp.status_code == 401


# ═══════════════════ ADMIN: GET /admin/etl/runs ═══════════════════


class TestETLRuns:
    def test_returns_paginated_list(self, client, admin_token):
        resp = client.get("/admin/etl/runs", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "pages" in data

    def test_no_auth_401(self, client):
        resp = client.get("/admin/etl/runs")
        assert resp.status_code == 401


# ═══════════════════ ADMIN: GET /admin/system/status ═══════════════════


class TestSystemStatus:
    def test_returns_status_fields(self, client, admin_token, sample_students):
        resp = client.get("/admin/system/status", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "total_estudiantes" in data
        assert data["total_estudiantes"] == 2
        assert "ultima_actualizacion" in data
        assert "estado_pipeline" in data

    def test_no_auth_401(self, client):
        resp = client.get("/admin/system/status")
        assert resp.status_code == 401


# ═══════════════════ ADMIN: GET /admin/system/avac-cookie ═══════════════════


class TestAvacCookie:
    def test_no_cookie_configured(self, client, admin_token):
        resp = client.get("/admin/system/avac-cookie", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["configured"] is False

    def test_no_auth_401(self, client):
        resp = client.get("/admin/system/avac-cookie")
        assert resp.status_code == 401


# ═══════════════════ ADMIN: POST /admin/students/deduplicate ═══════════════════


class TestDeduplicateStudents:
    @patch("backend.routes.admin.ETLPipeline")
    def test_returns_fusionados(self, mock_pipeline_cls, client, admin_token):
        mock_instance = MagicMock()
        mock_instance._merge_duplicate_students.return_value = 3
        mock_pipeline_cls.return_value = mock_instance
        resp = client.post("/admin/students/deduplicate", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["fusionados"] == 3

    def test_no_auth_401(self, client):
        resp = client.post("/admin/students/deduplicate")
        assert resp.status_code == 401


# ═══════════════════ EXPORT: GET /export/columnas-disponibles ═══════════════════


class TestExportColumns:
    def test_returns_column_list(self, client, admin_token):
        resp = client.get("/export/columnas-disponibles", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "key" in data[0]
        assert "label" in data[0]

    def test_no_auth_401(self, client):
        resp = client.get("/export/columnas-disponibles")
        assert resp.status_code == 401


# ═══════════════════ EXPORT: GET /export/estudiantes/excel ═══════════════════


class TestExportStudents:
    def test_with_students_returns_xlsx(self, client, admin_token, sample_students):
        resp = client.get("/export/estudiantes/excel", headers=auth(admin_token))
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers["content-type"]

    def test_empty_returns_404(self, client, admin_token):
        resp = client.get("/export/estudiantes/excel", headers=auth(admin_token))
        assert resp.status_code == 404

    def test_no_auth_401(self, client):
        resp = client.get("/export/estudiantes/excel")
        assert resp.status_code == 401


# ═══════════════════ EXPORT: GET /export/intervenciones/excel ═══════════════════


class TestExportInterventions:
    def test_with_interventions_returns_xlsx(self, client, admin_token,
                                             sample_interventions):
        resp = client.get("/export/intervenciones/excel", headers=auth(admin_token))
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers["content-type"]

    def test_empty_returns_404(self, client, admin_token):
        resp = client.get("/export/intervenciones/excel", headers=auth(admin_token))
        assert resp.status_code == 404

    def test_no_auth_401(self, client):
        resp = client.get("/export/intervenciones/excel")
        assert resp.status_code == 401


# ═══════════════════ EXPORT: GET /export/ficha/{id}/pdf ═══════════════════


class TestExportFichaPDF:
    def test_valid_student_returns_pdf(self, client, admin_token, sample_students):
        resp = client.get("/export/ficha/1/pdf", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"

    def test_not_found_returns_404(self, client, admin_token):
        resp = client.get("/export/ficha/9999/pdf", headers=auth(admin_token))
        assert resp.status_code == 404

    def test_no_auth_401(self, client):
        resp = client.get("/export/ficha/1/pdf")
        assert resp.status_code == 401
