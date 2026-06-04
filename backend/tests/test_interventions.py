"""
Tests for interventions CRUD endpoints.
"""
import pytest
from unittest.mock import patch

from backend.models import Student, Intervention
from backend.models.course_config import SemesterConfig
from .conftest import auth


@pytest.fixture
def semester_config(db):
    sc = SemesterConfig(semestre="P68", activo=True, bloque_actual="1")
    db.add(sc)
    db.commit()
    return sc


@pytest.fixture
def sample_student(db):
    s = Student(
        id=1, nombre="ALUMNO TEST", carrera="EDUCACION BASICA",
        nivel_riesgo="Alto", indice_compromiso=0.3, dias_sin_acceso=10,
        porcentaje_tareas=40.0, estado_matricula="Matriculado",
    )
    db.add(s)
    db.commit()
    return s


def _payload(**overrides):
    """Base valid intervention payload."""
    base = {
        "student_id": 1,
        "medio": "WhatsApp",
        "motivo": "Bajo rendimiento",
        "estado": "Activo",
        "observacion": "Contacto inicial",
    }
    base.update(overrides)
    return base


MOCK_EMAIL = "backend.services.email.send_bienestar_report"


# ---------------------------------------------------------------------------
# POST /interventions/
# ---------------------------------------------------------------------------
class TestCreateIntervention:

    @patch(MOCK_EMAIL, return_value=True)
    def test_create_valid(self, mock_email, client, admin_token, admin_user, sample_student, semester_config):
        resp = client.post("/interventions/", json=_payload(), headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["student_id"] == 1
        assert data["medio"] == "WhatsApp"
        assert data["monitor_nombre"] == admin_user.nombre

    @patch(MOCK_EMAIL, return_value=True)
    def test_create_missing_student(self, mock_email, client, admin_token, admin_user):
        resp = client.post(
            "/interventions/", json=_payload(student_id=9999), headers=auth(admin_token),
        )
        assert resp.status_code == 404

    def test_create_no_auth(self, client, sample_student):
        resp = client.post("/interventions/", json=_payload())
        assert resp.status_code == 401

    @patch(MOCK_EMAIL, return_value=True)
    def test_auto_populates_periodo(self, mock_email, client, admin_token, admin_user, sample_student, semester_config):
        payload = _payload()
        payload.pop("periodo", None)  # ensure no explicit periodo
        resp = client.post("/interventions/", json=payload, headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["periodo"] == "P68"

    @patch(MOCK_EMAIL, return_value=True)
    def test_captures_snapshot(self, mock_email, client, db, admin_token, admin_user, sample_student, semester_config):
        resp = client.post("/interventions/", json=_payload(), headers=auth(admin_token))
        assert resp.status_code == 200
        inv = db.query(Intervention).get(resp.json()["id"])
        assert inv.snapshot_compromiso == 0.3
        assert inv.snapshot_dias_sin_acceso == 10
        assert inv.snapshot_porcentaje_tareas == 40.0
        assert inv.snapshot_nivel_riesgo == "Alto"

    @patch(MOCK_EMAIL, return_value=True)
    def test_derivar_bienestar_sends_email(self, mock_email, client, admin_token, admin_user, sample_student, semester_config):
        payload = _payload(derivar_bienestar=True, reporte_bienestar="Caso grave")
        resp = client.post("/interventions/", json=payload, headers=auth(admin_token))
        assert resp.status_code == 200
        mock_email.assert_called_once()
        assert resp.json()["email_enviado"] is True


# ---------------------------------------------------------------------------
# POST /interventions/bulk
# ---------------------------------------------------------------------------
class TestBulkCreateIntervention:

    @patch(MOCK_EMAIL, return_value=True)
    def test_bulk_valid(self, mock_email, client, db, admin_token, admin_user, semester_config):
        # Create two students
        for sid in (10, 11):
            db.add(Student(id=sid, nombre=f"Alumno {sid}", carrera="EIB",
                           nivel_riesgo="Medio", estado_matricula="Matriculado"))
        db.commit()

        payload = {
            "student_ids": [10, 11],
            "medio": "Llamada",
            "motivo": "Inactividad",
            "estado": "Activo",
        }
        resp = client.post("/interventions/bulk", json=payload, headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 2
        assert data["errors"] == []

    @patch(MOCK_EMAIL, return_value=True)
    def test_bulk_mixed_valid_invalid(self, mock_email, client, db, admin_token, admin_user, sample_student, semester_config):
        payload = {
            "student_ids": [1, 9999],
            "medio": "Email",
            "motivo": "Bajo rendimiento",
            "estado": "Activo",
        }
        resp = client.post("/interventions/bulk", json=payload, headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 1
        assert len(data["errors"]) == 1
        assert data["errors"][0]["student_id"] == 9999


# ---------------------------------------------------------------------------
# GET /interventions/
# ---------------------------------------------------------------------------
class TestListInterventions:

    @patch(MOCK_EMAIL, return_value=True)
    def test_list_returns_interventions(self, mock_email, client, admin_token, admin_user, sample_student, semester_config):
        # Create an intervention first
        client.post("/interventions/", json=_payload(), headers=auth(admin_token))
        resp = client.get("/interventions/", headers=auth(admin_token))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    @patch(MOCK_EMAIL, return_value=True)
    def test_list_filter_by_student_id(self, mock_email, client, db, admin_token, admin_user, sample_student, semester_config):
        # Create intervention for student 1
        client.post("/interventions/", json=_payload(), headers=auth(admin_token))
        # Create second student + intervention
        db.add(Student(id=2, nombre="Otro", carrera="EIB", estado_matricula="Matriculado"))
        db.commit()
        client.post("/interventions/", json=_payload(student_id=2), headers=auth(admin_token))

        resp = client.get("/interventions/?student_id=1", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert all(item["student_id"] == 1 for item in data)

    def test_list_no_auth(self, client):
        resp = client.get("/interventions/")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /interventions/{id}
# ---------------------------------------------------------------------------
class TestUpdateIntervention:

    @patch(MOCK_EMAIL, return_value=True)
    def test_owner_can_update(self, mock_email, client, admin_token, admin_user, sample_student, semester_config):
        create_resp = client.post("/interventions/", json=_payload(), headers=auth(admin_token))
        inv_id = create_resp.json()["id"]

        resp = client.patch(
            f"/interventions/{inv_id}",
            json={"resultado": "Contactado"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["resultado"] == "Contactado"

    @patch(MOCK_EMAIL, return_value=True)
    def test_non_owner_non_admin_forbidden(self, mock_email, client, admin_token, admin_user, monitor_token, monitor_user, sample_student, semester_config):
        # Admin creates intervention
        create_resp = client.post("/interventions/", json=_payload(), headers=auth(admin_token))
        inv_id = create_resp.json()["id"]

        # Monitor tries to update
        resp = client.patch(
            f"/interventions/{inv_id}",
            json={"resultado": "No contesto"},
            headers=auth(monitor_token),
        )
        assert resp.status_code == 403

    @patch(MOCK_EMAIL, return_value=True)
    def test_admin_can_update_anyone(self, mock_email, client, admin_token, admin_user, monitor_token, monitor_user, sample_student, semester_config):
        # Monitor creates intervention
        create_resp = client.post("/interventions/", json=_payload(), headers=auth(monitor_token))
        inv_id = create_resp.json()["id"]

        # Admin updates it
        resp = client.patch(
            f"/interventions/{inv_id}",
            json={"resultado": "Contactado"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["resultado"] == "Contactado"

    @patch(MOCK_EMAIL, return_value=True)
    def test_not_found(self, mock_email, client, admin_token, admin_user):
        resp = client.patch(
            "/interventions/9999",
            json={"resultado": "X"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /interventions/{id}
# ---------------------------------------------------------------------------
class TestDeleteIntervention:

    @patch(MOCK_EMAIL, return_value=True)
    def test_owner_can_delete(self, mock_email, client, admin_token, admin_user, sample_student, semester_config):
        create_resp = client.post("/interventions/", json=_payload(), headers=auth(admin_token))
        inv_id = create_resp.json()["id"]

        resp = client.delete(f"/interventions/{inv_id}", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["id"] == inv_id

    @patch(MOCK_EMAIL, return_value=True)
    def test_non_owner_non_admin_forbidden(self, mock_email, client, admin_token, admin_user, monitor_token, monitor_user, sample_student, semester_config):
        create_resp = client.post("/interventions/", json=_payload(), headers=auth(admin_token))
        inv_id = create_resp.json()["id"]

        resp = client.delete(f"/interventions/{inv_id}", headers=auth(monitor_token))
        assert resp.status_code == 403

    @patch(MOCK_EMAIL, return_value=True)
    def test_admin_can_delete_anyone(self, mock_email, client, admin_token, admin_user, monitor_token, monitor_user, sample_student, semester_config):
        create_resp = client.post("/interventions/", json=_payload(), headers=auth(monitor_token))
        inv_id = create_resp.json()["id"]

        resp = client.delete(f"/interventions/{inv_id}", headers=auth(admin_token))
        assert resp.status_code == 200

    @patch(MOCK_EMAIL, return_value=True)
    def test_not_found(self, mock_email, client, admin_token, admin_user):
        resp = client.delete("/interventions/9999", headers=auth(admin_token))
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /interventions/stats
# ---------------------------------------------------------------------------
class TestInterventionStats:

    @patch(MOCK_EMAIL, return_value=True)
    def test_returns_aggregated_counts(self, mock_email, client, admin_token, admin_user, sample_student, semester_config):
        # Create a couple of interventions with different attributes
        client.post("/interventions/", json=_payload(medio="WhatsApp", motivo="Inactividad", resultado="Contactado"), headers=auth(admin_token))
        client.post("/interventions/", json=_payload(medio="Llamada", motivo="Bajo rendimiento", resultado="No contesto"), headers=auth(admin_token))

        resp = client.get("/interventions/stats", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "por_medio" in data
        assert "por_motivo" in data
        assert "por_resultado" in data
        assert "por_estado" in data
        # Check we have aggregation entries
        assert len(data["por_medio"]) == 2  # WhatsApp, Llamada

    def test_empty_returns_empty_arrays(self, client, admin_token, admin_user):
        resp = client.get("/interventions/stats", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["por_medio"] == []
        assert data["por_motivo"] == []
        assert data["por_resultado"] == []
        assert data["por_estado"] == []


# ---------------------------------------------------------------------------
# GET /interventions/{id}/impact
# ---------------------------------------------------------------------------
class TestInterventionImpact:

    @patch(MOCK_EMAIL, return_value=True)
    def test_with_snapshot_data(self, mock_email, client, db, admin_token, admin_user, sample_student, semester_config):
        create_resp = client.post("/interventions/", json=_payload(), headers=auth(admin_token))
        inv_id = create_resp.json()["id"]

        # Simulate student improvement after intervention
        student = db.query(Student).get(1)
        student.indice_compromiso = 0.7
        student.dias_sin_acceso = 2
        student.porcentaje_tareas = 80.0
        db.commit()

        resp = client.get(f"/interventions/{inv_id}/impact", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["disponible"] is True
        assert data["antes"]["compromiso"] == 0.3
        assert data["ahora"]["compromiso"] == 0.7
        assert data["cambio"]["compromiso"] > 0  # improved
        assert data["cambio"]["dias_sin_acceso"] < 0  # improved (fewer days)
        assert data["mejoro"] is True

    @patch(MOCK_EMAIL, return_value=True)
    def test_without_snapshot(self, mock_email, client, db, admin_token, admin_user, sample_student, semester_config):
        # Manually create intervention without snapshot
        inv = Intervention(
            student_id=1, monitor_id=admin_user.id,
            medio="WhatsApp", motivo="Test", estado="Activo",
            snapshot_compromiso=None, snapshot_dias_sin_acceso=None,
        )
        db.add(inv)
        db.commit()
        db.refresh(inv)

        resp = client.get(f"/interventions/{inv.id}/impact", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["disponible"] is False
