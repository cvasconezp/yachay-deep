"""
Tests for dashboard and alerts endpoints.
"""

import pytest
from datetime import date, datetime, timedelta, timezone

from backend.models import Student, Grade, Enrollment
from backend.models.course_config import SemesterConfig, CourseConfig
from backend.models.avac_access import AvacAccess
from backend.models.alert_event import AlertEvent
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
        Student(id=1, nombre="ALUMNO ALTO RIESGO", carrera="EDUCACION BASICA",
                nivel_riesgo="Alto", indice_compromiso=0.2, dias_sin_acceso=25),
        Student(id=2, nombre="ALUMNO BAJO RIESGO", carrera="DERECHO",
                nivel_riesgo="Bajo", indice_compromiso=0.9, dias_sin_acceso=1),
    ]
    db.add_all(students)
    db.commit()
    return students


@pytest.fixture
def sample_grades(db, sample_students):
    grades = [
        Grade(student_id=1, asignatura="MATEMATICAS", docente="GARCIA",
              carrera="EDUCACION BASICA", nota_final=55, periodo="P68"),
        Grade(student_id=2, asignatura="DERECHO CIVIL", docente="PEREZ",
              carrera="DERECHO", nota_final=90, periodo="P68"),
    ]
    db.add_all(grades)
    db.commit()
    return grades


@pytest.fixture
def sample_avac(db, sample_students, semester_config):
    accesses = [
        AvacAccess(student_id=1, codigo_curso="COURSE1", periodo="P68",
                   snapshot_date=date.today(), dias_sin_acceso=25.0),
        AvacAccess(student_id=2, codigo_curso="COURSE2", periodo="P68",
                   snapshot_date=date.today(), dias_sin_acceso=1.0),
    ]
    db.add_all(accesses)
    db.commit()
    return accesses


@pytest.fixture
def sample_alerts(db, sample_students):
    alerts = [
        AlertEvent(student_id=1, tipo="inactividad", severidad="critico",
                   mensaje="25 dias sin acceso", leido=False),
        AlertEvent(student_id=1, tipo="compromiso_bajo", severidad="alto",
                   mensaje="Compromiso 0.2", leido=False),
        AlertEvent(student_id=2, tipo="inactividad", severidad="medio",
                   mensaje="Test alert", leido=True),  # already read
    ]
    db.add_all(alerts)
    db.commit()
    return alerts


# ─── Dashboard: /dashboard/risk ─────────────────────────────────────────────


class TestRiskDashboard:

    def test_returns_students_sorted_by_risk(
        self, client, admin_token, sample_students, sample_grades, semester_config
    ):
        resp = client.get("/dashboard/risk?periodo=P68", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2
        # Alto should come before Bajo
        risk_levels = [s["nivel_riesgo"] for s in data]
        assert risk_levels.index("Alto") < risk_levels.index("Bajo")

    def test_filter_by_carrera(
        self, client, admin_token, sample_students, sample_grades, semester_config
    ):
        resp = client.get(
            "/dashboard/risk", params={"carrera": "DERECHO", "periodo": "P68"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(s["carrera"] == "DERECHO" for s in data)

    def test_filter_by_nivel_riesgo(
        self, client, admin_token, sample_students, sample_grades, semester_config
    ):
        resp = client.get(
            "/dashboard/risk", params={"nivel_riesgo": "Alto", "periodo": "P68"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(s["nivel_riesgo"] == "Alto" for s in data)

    def test_no_auth_returns_401(self, client):
        resp = client.get("/dashboard/risk")
        assert resp.status_code == 401

    def test_empty_db_returns_empty(self, client, admin_token, semester_config):
        resp = client.get("/dashboard/risk", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json() == []


# ─── Dashboard: /dashboard/stats ─────────────────────────────────────────────


class TestDashboardStats:

    def test_returns_stats_with_data(
        self, client, admin_token, sample_students, sample_grades, semester_config
    ):
        resp = client.get("/dashboard/stats?periodo=P68", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_estudiantes"] >= 2
        assert isinstance(data["por_nivel_riesgo"], list)
        assert "total_intervenciones" in data
        assert "estudiantes_intervenidos" in data

    def test_empty_db_returns_zeros(self, client, admin_token, semester_config):
        resp = client.get("/dashboard/stats", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_estudiantes"] == 0

    def test_no_auth_returns_401(self, client):
        resp = client.get("/dashboard/stats")
        assert resp.status_code == 401


# ─── Dashboard: /dashboard/carreras ──────────────────────────────────────────


class TestCarreras:

    def test_returns_sorted_distinct_carreras(
        self, client, admin_token, sample_students
    ):
        resp = client.get("/dashboard/carreras", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "DERECHO" in data
        assert "EDUCACION BASICA" in data
        assert data == sorted(data)

    def test_no_auth_returns_401(self, client):
        resp = client.get("/dashboard/carreras")
        assert resp.status_code == 401


# ─── Alerts: /alerts/pending ─────────────────────────────────────────────────


class TestPendingAlerts:

    def test_returns_unread_alerts(
        self, client, admin_token, sample_alerts, sample_grades, semester_config
    ):
        resp = client.get("/alerts/pending", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        # Only unread alerts (2 of 3 are unread)
        assert len(data) == 2
        assert all(not a["leido"] for a in data)

    def test_no_alerts_returns_empty(self, client, admin_token, semester_config):
        resp = client.get("/alerts/pending", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_no_auth_returns_401(self, client):
        resp = client.get("/alerts/pending")
        assert resp.status_code == 401


# ─── Alerts: /alerts/count ───────────────────────────────────────────────────


class TestAlertCount:

    def test_returns_count_by_severity(
        self, client, admin_token, sample_alerts, sample_grades, semester_config
    ):
        resp = client.get("/alerts/count", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2  # 2 unread
        assert data["critico"] == 1
        assert data["alto"] == 1
        assert data["medio"] == 0  # the medio one is already read

    def test_no_alerts_returns_zeros(self, client, admin_token, semester_config):
        resp = client.get("/alerts/count", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["critico"] == 0
        assert data["alto"] == 0
        assert data["medio"] == 0


# ─── Alerts: /alerts/{id}/read ───────────────────────────────────────────────


class TestMarkAlertRead:

    def test_marks_alert_as_read(
        self, client, admin_token, sample_alerts
    ):
        alert_id = sample_alerts[0].id
        resp = client.patch(
            f"/alerts/{alert_id}/read", headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == alert_id
        assert data["leido"] is True

    def test_not_found_returns_404(self, client, admin_token):
        resp = client.patch("/alerts/99999/read", headers=auth(admin_token))
        assert resp.status_code == 404

    def test_no_auth_returns_401(self, client):
        resp = client.patch("/alerts/1/read")
        assert resp.status_code == 401


# ─── Alerts: /alerts/generate ────────────────────────────────────────────────


class TestGenerateAlerts:

    def test_generates_inactividad_alerts(
        self, client, admin_token, sample_students, sample_avac, semester_config
    ):
        resp = client.post("/alerts/generate", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] >= 1
        # Student 1 has 25 days inactive (> 21 threshold) so should get critico

    def test_generates_compromiso_bajo_alerts(
        self, client, admin_token, sample_students, sample_avac, semester_config
    ):
        resp = client.post("/alerts/generate", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        # Student 1 has indice_compromiso=0.2 (< 0.3), should get critico
        assert data["created"] >= 1

    def test_dedup_no_duplicates_within_7_days(
        self, client, admin_token, db, sample_students, sample_avac, semester_config
    ):
        # First generation
        resp1 = client.post("/alerts/generate", headers=auth(admin_token))
        assert resp1.status_code == 200
        first_count = resp1.json()["created"]
        assert first_count >= 1

        # Mark all alerts as read so they survive the stale cleanup
        db.query(AlertEvent).update({"leido": True})
        db.commit()

        # Second generation should not duplicate read alerts within 7 days
        resp2 = client.post("/alerts/generate", headers=auth(admin_token))
        assert resp2.status_code == 200
        second_count = resp2.json()["created"]
        # Dedup: same student+tipo within 7 days should not be recreated
        assert second_count == 0

    def test_no_active_semester_returns_zero(
        self, client, admin_token, sample_students
    ):
        resp = client.post("/alerts/generate", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 0

    def test_no_auth_returns_401(self, client):
        resp = client.post("/alerts/generate")
        assert resp.status_code == 401
