"""
Tests for docente tracking analytics endpoints.

Covers:
  - GET /analytics/docente-tracking        (list with severity sorting)
  - GET /analytics/docente-tracking/resumen (summary stats)
  - GET /analytics/docente-tracking/{name}  (detail per docente)
"""

import pytest
from .conftest import auth
from backend.models.course_config import SemesterConfig
from backend.models.docente_tracking import DocenteTracking


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def semester_config(db):
    sc = SemesterConfig(semestre="P68", activo=True, bloque_actual="1")
    db.add(sc)
    db.commit()
    return sc


@pytest.fixture
def sample_tracking(db, semester_config):
    from datetime import datetime, timezone

    records = [
        # GARCIA: 3 activities, 1 calificada -> 33% -> critico
        DocenteTracking(
            codigo_curso="C001", nombre_curso="MATEMATICAS",
            actividad="Tarea 1", tipo_actividad="assign",
            calificada=True, docente="GARCIA JUAN",
            dias_retraso=2.0, semestre="P68",
        ),
        DocenteTracking(
            codigo_curso="C001", nombre_curso="MATEMATICAS",
            actividad="Tarea 2", tipo_actividad="assign",
            calificada=False, docente="GARCIA JUAN",
            semestre="P68",
        ),
        DocenteTracking(
            codigo_curso="C001", nombre_curso="MATEMATICAS",
            actividad="Tarea 3", tipo_actividad="assign",
            calificada=False, docente="GARCIA JUAN",
            semestre="P68",
        ),
        # PEREZ: 2 activities, 2 calificadas -> 100% -> ok
        DocenteTracking(
            codigo_curso="C002", nombre_curso="LENGUA",
            actividad="Tarea 1", tipo_actividad="assign",
            calificada=True, docente="PEREZ ANA",
            dias_retraso=-1.0, semestre="P68",
        ),
        DocenteTracking(
            codigo_curso="C002", nombre_curso="LENGUA",
            actividad="Tarea 2", tipo_actividad="assign",
            calificada=True, docente="PEREZ ANA",
            dias_retraso=0.5, semestre="P68",
        ),
    ]
    db.add_all(records)
    db.commit()
    return records


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

        # critico first, ok last
        assert data[0]["alerta"] == "critico"
        assert data[0]["docente"] == "GARCIA JUAN"
        assert data[1]["alerta"] == "ok"
        assert data[1]["docente"] == "PEREZ ANA"

    def test_alert_thresholds(self, client, admin_token, sample_tracking):
        resp = client.get("/analytics/docente-tracking", headers=auth(admin_token))
        data = resp.json()

        garcia = next(d for d in data if d["docente"] == "GARCIA JUAN")
        assert garcia["total_actividades"] == 3
        assert garcia["actividades_calificadas"] == 1
        assert garcia["actividades_pendientes"] == 2
        assert garcia["porcentaje_calificacion"] < 50
        assert garcia["alerta"] == "critico"

        perez = next(d for d in data if d["docente"] == "PEREZ ANA")
        assert perez["total_actividades"] == 2
        assert perez["actividades_calificadas"] == 2
        assert perez["actividades_pendientes"] == 0
        assert perez["porcentaje_calificacion"] >= 80
        assert perez["alerta"] == "ok"

    def test_item_fields(self, client, admin_token, sample_tracking):
        resp = client.get("/analytics/docente-tracking", headers=auth(admin_token))
        item = resp.json()[0]
        expected_keys = {
            "docente", "total_actividades", "actividades_calificadas",
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
        resp = client.get("/analytics/docente-tracking/resumen", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()

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
        resp = client.get(
            "/analytics/docente-tracking/GARCIA JUAN",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        # DocenteTrackingDetalle doesn't have docente field; check actividad instead
        assert all("actividad" in item for item in data)

    def test_unknown_docente_returns_empty(self, client, admin_token, semester_config):
        resp = client.get(
            "/analytics/docente-tracking/NO EXISTE",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Tests: authentication
# ---------------------------------------------------------------------------

class TestDocenteTrackingAuth:
    """All endpoints require authentication."""

    def test_list_no_auth(self, client):
        resp = client.get("/analytics/docente-tracking")
        assert resp.status_code == 401

    def test_resumen_no_auth(self, client):
        resp = client.get("/analytics/docente-tracking/resumen")
        assert resp.status_code == 401

    def test_detail_no_auth(self, client):
        resp = client.get("/analytics/docente-tracking/GARCIA JUAN")
        assert resp.status_code == 401
