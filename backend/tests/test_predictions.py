"""
Tests para endpoints de predicción ML — /predictions/*.

Cubre: train, run, task-status, status, predict student,
recommendations, counterfactual y what-if.
"""

import pytest
from unittest.mock import patch, MagicMock

from .conftest import auth
from backend.models import Student, Grade
from backend.models.course_config import SemesterConfig


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def semester_config(db):
    sc = SemesterConfig(semestre="P68", activo=True, bloque_actual="1")
    db.add(sc)
    db.commit()
    return sc


@pytest.fixture
def sample_student(db):
    s = Student(
        id=1,
        nombre="ALUMNO TEST",
        carrera="EDUCACION BASICA",
        nivel_riesgo="Alto",
        indice_compromiso=0.3,
        dias_sin_acceso=10,
        porcentaje_tareas=40.0,
        promedio_calificaciones=55.0,
        prob_desercion=0.7,
        prob_reprobacion=0.6,
    )
    db.add(s)
    db.commit()
    return s


@pytest.fixture(autouse=True)
def _reset_bg_task():
    """Reset background task state between tests."""
    with patch.dict(
        "backend.routes.predictions._bg_task",
        {"running": False, "type": None, "started": None, "result": None, "error": None},
    ):
        yield


# ── Train ─────────────────────────────────────────────────────────────


class TestTrain:
    URL = "/predictions/train"

    @patch("backend.routes.predictions.threading.Thread")
    def test_admin_starts_training(self, mock_thread, client, admin_token):
        mock_thread.return_value = MagicMock()
        resp = client.post(self.URL, headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "started"
        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()

    @patch("backend.routes.predictions.threading.Thread")
    def test_monitor_forbidden(self, mock_thread, client, monitor_token):
        resp = client.post(self.URL, headers=auth(monitor_token))
        assert resp.status_code == 403
        mock_thread.assert_not_called()

    def test_no_auth_unauthorized(self, client):
        resp = client.post(self.URL)
        assert resp.status_code == 401


# ── Run ───────────────────────────────────────────────────────────────


class TestRun:
    URL = "/predictions/run"

    @patch("backend.routes.predictions.threading.Thread")
    def test_admin_starts_predictions(self, mock_thread, client, admin_token):
        mock_thread.return_value = MagicMock()
        resp = client.post(self.URL, headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "started"
        mock_thread.return_value.start.assert_called_once()

    @patch("backend.routes.predictions.threading.Thread")
    def test_monitor_forbidden(self, mock_thread, client, monitor_token):
        resp = client.post(self.URL, headers=auth(monitor_token))
        assert resp.status_code == 403

    def test_no_auth_unauthorized(self, client):
        resp = client.post(self.URL)
        assert resp.status_code == 401


# ── Task Status ───────────────────────────────────────────────────────


class TestTaskStatus:
    URL = "/predictions/task-status"

    def test_returns_status(self, client, admin_token):
        resp = client.get(self.URL, headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "running" in data
        assert "type" in data
        assert "result" in data
        assert "error" in data

    def test_no_auth_unauthorized(self, client):
        resp = client.get(self.URL)
        assert resp.status_code == 401


# ── Prediction Status ─────────────────────────────────────────────────


class TestPredictionStatus:
    URL = "/predictions/status"

    @patch("backend.ml.predict.Predictor")
    def test_returns_model_status(self, mock_predictor_cls, client, admin_token):
        mock_instance = MagicMock()
        mock_instance.get_status.return_value = {
            "loaded": False,
            "models": {},
            "trained_at": None,
        }
        mock_predictor_cls.get_instance.return_value = mock_instance

        resp = client.get(self.URL, headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "loaded" in data

    def test_no_auth_unauthorized(self, client):
        resp = client.get(self.URL)
        assert resp.status_code == 401


# ── Predict Student ───────────────────────────────────────────────────


class TestPredictStudent:

    @patch("backend.ml.predict.Predictor")
    def test_valid_student(self, mock_predictor_cls, client, admin_token, sample_student):
        mock_instance = MagicMock()
        mock_instance.predict_single.return_value = {
            "student_id": 1,
            "prob_desercion": 0.72,
            "prob_reprobacion": 0.61,
            "features": {"promedio_notas": 55.0},
            "model_used": "global",
        }
        mock_predictor_cls.get_instance.return_value = mock_instance

        resp = client.get("/predictions/student/1", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["student_id"] == 1
        assert "prob_desercion" in data

    @patch("backend.ml.predict.Predictor")
    def test_student_not_found(self, mock_predictor_cls, client, admin_token):
        mock_instance = MagicMock()
        mock_instance.predict_single.return_value = None
        mock_predictor_cls.get_instance.return_value = mock_instance

        resp = client.get("/predictions/student/9999", headers=auth(admin_token))
        assert resp.status_code == 404

    def test_no_auth_unauthorized(self, client):
        resp = client.get("/predictions/student/1")
        assert resp.status_code == 401


# ── Recommendations ───────────────────────────────────────────────────


class TestRecommendations:

    @patch("backend.ml.recommendations.generate_recommendations")
    @patch("backend.ml.predict.Predictor")
    def test_valid_student(
        self, mock_predictor_cls, mock_gen_recs, client, admin_token, sample_student
    ):
        mock_instance = MagicMock()
        mock_instance.predict_single.return_value = {"student_id": 1, "features": {}}
        mock_predictor_cls.get_instance.return_value = mock_instance
        mock_gen_recs.return_value = [
            {"tipo": "academica", "prioridad": "alta", "mensaje": "Agendar tutoría"},
        ]

        resp = client.get("/predictions/student/1/recommendations", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["student_id"] == 1
        assert isinstance(data["recommendations"], list)
        assert data["total"] >= 1

    def test_no_auth_unauthorized(self, client):
        resp = client.get("/predictions/student/1/recommendations")
        assert resp.status_code == 401


# ── Counterfactual ────────────────────────────────────────────────────


class TestCounterfactual:

    @patch("backend.ml.counterfactual_conductual.generate_behavioral_counterfactual")
    @patch("backend.ml.counterfactual.generate_counterfactual")
    @patch("backend.ml.predict.Predictor")
    def test_valid_student(
        self,
        mock_predictor_cls,
        mock_gen_cf,
        mock_gen_bcf,
        client,
        admin_token,
        sample_student,
    ):
        mock_instance = MagicMock()
        mock_instance.is_loaded = True
        mock_instance.load_models.return_value = True
        mock_instance.predict_single.return_value = {
            "student_id": 1,
            "prob_desercion": 0.7,
            "features": {"promedio_notas": 55.0},
            "model_used": "global",
        }
        mock_predictor_cls.get_instance.return_value = mock_instance
        mock_gen_cf.return_value = {"changes": [{"feature": "promedio_notas", "from": 55, "to": 70}]}
        mock_gen_bcf.return_value = {"sugerencias": ["Acceder al AVAC más frecuentemente"]}

        resp = client.get("/predictions/student/1/counterfactual", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["student_id"] == 1
        assert "contrafactual_desercion" in data
        assert "contrafactual_conductual" in data

    def test_no_auth_unauthorized(self, client):
        resp = client.get("/predictions/student/1/counterfactual")
        assert resp.status_code == 401


# ── What-If ───────────────────────────────────────────────────────────


class TestWhatIf:

    @patch("backend.ml.features.FEATURE_COLUMNS", ["promedio_notas", "num_reprobadas"])
    @patch("backend.ml.predict.Predictor")
    def test_valid_what_if(self, mock_predictor_cls, client, admin_token, sample_student):
        import numpy as np
        mock_model_des = MagicMock()
        mock_model_des.predict_proba.return_value = np.array([[0.4, 0.6]])
        mock_model_rep = MagicMock()
        mock_model_rep.predict_proba.return_value = np.array([[0.5, 0.5]])

        mock_instance = MagicMock()
        mock_instance.is_loaded = True
        mock_instance.load_models.return_value = True
        mock_instance.predict_single.return_value = {
            "student_id": 1,
            "prob_desercion": 0.7,
            "prob_reprobacion": 0.6,
            "features": {"promedio_notas": 55.0, "num_reprobadas": 3},
            "model_used": "global",
        }
        mock_instance.models = {
            "global": {"desercion": mock_model_des, "reprobacion": mock_model_rep}
        }
        mock_predictor_cls.get_instance.return_value = mock_instance

        resp = client.post(
            "/predictions/student/1/what-if",
            json={"promedio_notas": 75.0},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["student_id"] == 1
        assert "desercion" in data
        assert "reprobacion" in data
        assert data["desercion"]["prob_modificada"] == 0.6
        assert "cambios_aplicados" in data

    def test_no_auth_unauthorized(self, client):
        resp = client.post("/predictions/student/1/what-if", json={"promedio_notas": 75.0})
        assert resp.status_code == 401
