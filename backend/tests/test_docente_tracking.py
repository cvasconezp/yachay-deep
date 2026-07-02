"""
Tests for docente tracking analytics endpoints.

Covers:
  - GET /analytics/docente-tracking        (list with severity sorting)
  - GET /analytics/docente-tracking/resumen (summary stats)
  - GET /analytics/docente-tracking/{name}  (detail per docente)

NOTA: el endpoint deriva el seguimiento de CourseConfig (cursos con docente
asignado en el bloque activo) + TaskSubmission (entregas del periodo activo,
último snapshot). Los fixtures siembran ESAS tablas — no una tabla propia.
"""
from datetime import date

import pytest

from .conftest import auth
from backend.models.course_config import SemesterConfig, CourseConfig
from backend.models.task_submission import TaskSubmission
from backend.models.student import Student


SNAP = date.today()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def semester_config(db):
    # Sin calendario_academico -> _unidades_vencidas() = {"1","2","3","4"} -> no filtra unidades.
    sc = SemesterConfig(semestre="P68", activo=True, bloque_actual="1")
    db.add(sc)
    db.commit()
    return sc


@pytest.fixture
def sample_tracking(db, semester_config):
    # Cursos con docente asignado en el bloque activo ("1")
    db.add_all([
        CourseConfig(codigo_avac="C001", nombre="MATEMATICAS", asignatura="MATEMATICAS",
                     docente="GARCIA JUAN", correo_docente="garcia@x.edu",
                     carrera="SOFTWARE", bloque="1", activo=True),
        CourseConfig(codigo_avac="C002", nombre="LENGUA", asignatura="LENGUA",
                     docente="PEREZ ANA", correo_docente="perez@x.edu",
                     carrera="SOFTWARE", bloque="1", activo=True),
    ])
    # Estudiantes (para la lista de pendientes del detalle)
    db.add_all([
        Student(id=1, nombre="EST UNO", correo="uno@x.edu"),
        Student(id=2, nombre="EST DOS", correo="dos@x.edu"),
    ])
    db.commit()
    # Entregas del periodo activo (P68), mismo snapshot.
    subs = [
        # GARCIA / C001: 3 entregadas, 1 calificada -> 33% -> critico (unidades 1,2,3)
        TaskSubmission(student_id=1, codigo_curso="C001", periodo="P68", snapshot_date=SNAP, unidad="1", entregada=True, calificada=True),
        TaskSubmission(student_id=1, codigo_curso="C001", periodo="P68", snapshot_date=SNAP, unidad="2", entregada=True, calificada=False),
        TaskSubmission(student_id=1, codigo_curso="C001", periodo="P68", snapshot_date=SNAP, unidad="3", entregada=True, calificada=False),
        # PEREZ / C002: 2 entregadas, 2 calificadas -> 100% -> ok
        TaskSubmission(student_id=2, codigo_curso="C002", periodo="P68", snapshot_date=SNAP, unidad="1", entregada=True, calificada=True),
        TaskSubmission(student_id=2, codigo_curso="C002", periodo="P68", snapshot_date=SNAP, unidad="2", entregada=True, calificada=True),
    ]
    db.add_all(subs)
    db.commit()
    return subs


# ---------------------------------------------------------------------------
# Tests: list endpoint
# ---------------------------------------------------------------------------

class TestDocenteTrackingList:
    """GET /analytics/docente-tracking"""

    def test_list_sorted_by_severity(self, client, admin_token, sample_tracking):
        resp = client.get("/analytics/docente-tracking", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        # critico primero, ok al final
        assert data[0]["alerta"] == "critico"
        assert data[0]["docente"] == "GARCIA JUAN"
        assert data[1]["alerta"] == "ok"
        assert data[1]["docente"] == "PEREZ ANA"

    def test_alert_thresholds(self, client, admin_token, sample_tracking):
        data = client.get("/analytics/docente-tracking", headers=auth(admin_token)).json()

        garcia = next(d for d in data if d["docente"] == "GARCIA JUAN")
        assert garcia["total_tareas"] == 3
        assert garcia["actividades_calificadas"] == 1
        assert garcia["actividades_pendientes"] == 2
        assert garcia["porcentaje_calificacion"] < 50
        assert garcia["alerta"] == "critico"

        perez = next(d for d in data if d["docente"] == "PEREZ ANA")
        assert perez["total_tareas"] == 2
        assert perez["actividades_calificadas"] == 2
        assert perez["actividades_pendientes"] == 0
        assert perez["porcentaje_calificacion"] >= 80
        assert perez["alerta"] == "ok"

    def test_item_fields(self, client, admin_token, sample_tracking):
        item = client.get("/analytics/docente-tracking", headers=auth(admin_token)).json()[0]
        expected_keys = {
            "docente", "total_tareas", "actividades_calificadas",
            "actividades_pendientes", "porcentaje_calificacion",
            "promedio_dias_retraso", "cursos", "alerta",
        }
        assert expected_keys.issubset(item.keys())

    def test_empty_returns_empty_list(self, client, admin_token, semester_config):
        resp = client.get("/analytics/docente-tracking", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Tests: resumen endpoint
# ---------------------------------------------------------------------------

class TestDocenteTrackingResumen:
    """GET /analytics/docente-tracking/resumen"""

    def test_resumen_with_data(self, client, admin_token, sample_tracking):
        resp = client.get("/analytics/docente-tracking/resumen", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_docentes"] == 2
        assert data["docentes_criticos"] == 1   # GARCIA < 50%
        assert data["docentes_en_atencion"] == 0
        assert "promedio_general_calificacion" in data

    def test_resumen_empty_returns_zeros(self, client, admin_token, semester_config):
        data = client.get("/analytics/docente-tracking/resumen", headers=auth(admin_token)).json()
        assert data["total_docentes"] == 0
        assert data["docentes_criticos"] == 0
        assert data["docentes_en_atencion"] == 0
        assert data["promedio_general_calificacion"] == 0


# ---------------------------------------------------------------------------
# Tests: detail endpoint
# ---------------------------------------------------------------------------

class TestDocenteTrackingDetalle:
    """GET /analytics/docente-tracking/{docente_name}"""

    def test_detail_returns_activities(self, client, admin_token, sample_tracking):
        resp = client.get("/analytics/docente-tracking/GARCIA JUAN", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        # GARCIA tiene 1 curso (C001) con 3 actividades (unidades 1,2,3)
        assert len(data) == 1
        curso = data[0]
        assert curso["codigo_curso"] == "C001"
        assert curso["total_tareas"] == 3
        assert len(curso["actividades"]) == 3
        assert all("actividad" in a for a in curso["actividades"])

    def test_unknown_docente_returns_empty(self, client, admin_token, semester_config):
        resp = client.get("/analytics/docente-tracking/NO EXISTE", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Tests: authentication
# ---------------------------------------------------------------------------

class TestDocenteTrackingAuth:
    """All endpoints require authentication."""

    def test_list_no_auth(self, client):
        assert client.get("/analytics/docente-tracking").status_code == 401

    def test_resumen_no_auth(self, client):
        assert client.get("/analytics/docente-tracking/resumen").status_code == 401

    def test_detail_no_auth(self, client):
        assert client.get("/analytics/docente-tracking/GARCIA JUAN").status_code == 401
