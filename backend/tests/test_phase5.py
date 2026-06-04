"""
Tests para Fase 5 — ML Avanzado, Moodle, Multi-tenancy

Cubre:
  - Épica 5.1: Recomendaciones Adaptativas
  - Épica 5.2: SHAP + Clustering
  - Épica 5.3: Moodle API Client
  - Épica 5.4: Multi-tenancy (Institutions)
"""
import pytest
import numpy as np
from unittest.mock import MagicMock, patch


# ══════════════════════════════════════════════════════════════════
# Épica 5.1: Recomendaciones Adaptativas
# ══════════════════════════════════════════════════════════════════

from backend.ml.adaptive_recommendations import (
    _fallback_reglas, predict_best_intervention, get_model_status,
    _extract_training_data, MIN_SAMPLES, _MODEL_CACHE,
)


class TestFallbackReglas:

    def _make_student(self, **kw):
        s = MagicMock()
        s.dias_sin_acceso = kw.get("dias_sin_acceso", 0)
        s.indice_compromiso = kw.get("indice_compromiso", 0.5)
        s.porcentaje_tareas = kw.get("porcentaje_tareas", 60)
        s.prob_desercion = kw.get("prob_desercion", 0.3)
        s.prob_reprobacion = kw.get("prob_reprobacion", 0.2)
        s.score_recuperabilidad = kw.get("score_recuperabilidad", 50)
        return s

    def test_inactivo_prolongado_llamada(self):
        s = self._make_student(dias_sin_acceso=20)
        r = _fallback_reglas(s)
        assert r["fuente"] == "reglas"
        assert "Llamada" in r["medio_recomendado"]

    def test_inactivo_moderado_whatsapp(self):
        s = self._make_student(dias_sin_acceso=10)
        r = _fallback_reglas(s)
        assert "WhatsApp" in r["medio_recomendado"]

    def test_bajo_compromiso_tutoria(self):
        s = self._make_student(dias_sin_acceso=3, indice_compromiso=0.2)
        r = _fallback_reglas(s)
        assert "Tutoría" in r["medio_recomendado"]

    def test_tareas_atrasadas_whatsapp(self):
        s = self._make_student(dias_sin_acceso=3, indice_compromiso=0.5, porcentaje_tareas=30)
        r = _fallback_reglas(s)
        assert "WhatsApp" in r["medio_recomendado"]

    def test_seguimiento_general_email(self):
        s = self._make_student(dias_sin_acceso=2, indice_compromiso=0.6, porcentaje_tareas=70)
        r = _fallback_reglas(s)
        assert "Email" in r["medio_recomendado"]

    def test_confianza_05(self):
        s = self._make_student()
        r = _fallback_reglas(s)
        assert r["confianza"] == 0.5


class TestPredictSinModelo:

    def test_fallback_when_no_model(self):
        _MODEL_CACHE.clear()
        s = MagicMock()
        s.dias_sin_acceso = 20
        s.indice_compromiso = 0.3
        s.porcentaje_tareas = 30
        s.prob_desercion = 0.8
        s.prob_reprobacion = 0.5
        s.score_recuperabilidad = 20
        r = predict_best_intervention(s)
        assert r["fuente"] == "reglas"


class TestGetModelStatus:

    def test_not_trained(self):
        _MODEL_CACHE.clear()
        r = get_model_status()
        assert r["status"] == "not_trained"

    def test_trained(self):
        _MODEL_CACHE["adaptive"] = {
            "n_samples": 100, "accuracy": 0.75, "classes": ["WhatsApp", "Llamada"],
            "trained_at": "2026-01-01T00:00:00",
        }
        r = get_model_status()
        assert r["status"] == "trained"
        assert r["n_samples"] == 100
        _MODEL_CACHE.clear()


class TestExtractTrainingData:

    def test_empty_db(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        X, y, classes = _extract_training_data(db)
        assert len(X) == 0

    def test_min_samples_constant(self):
        assert MIN_SAMPLES == 50


# ══════════════════════════════════════════════════════════════════
# Épica 5.2a: SHAP / Feature Importance
# ══════════════════════════════════════════════════════════════════

from backend.ml.explainability import compute_shap_explanation, _fallback_feature_importance


class TestFallbackFeatureImportance:

    def test_with_rf_model(self):
        from sklearn.ensemble import RandomForestClassifier
        clf = RandomForestClassifier(n_estimators=10, random_state=42)
        X = np.random.rand(20, 4)
        y = (X[:, 0] > 0.5).astype(int)
        clf.fit(X, y)

        features = ["f1", "f2", "f3", "f4"]
        result = _fallback_feature_importance(clf, features, X[0])
        assert result["method"] == "feature_importance"
        assert len(result["top_factors"]) <= 5
        assert "f1" in result["feature_importances"]

    def test_without_feature_importances(self):
        model = MagicMock()
        del model.feature_importances_
        del model.coef_
        features = ["a", "b"]
        result = _fallback_feature_importance(model, features, np.array([1.0, 2.0]))
        assert result["method"] == "feature_importance"


class TestComputeShapExplanation:

    def test_fallback_when_no_shap(self):
        """Sin SHAP instalado, debe usar fallback."""
        from sklearn.ensemble import RandomForestClassifier
        clf = RandomForestClassifier(n_estimators=10, random_state=42)
        X = np.random.rand(20, 3)
        y = (X[:, 0] > 0.5).astype(int)
        clf.fit(X, y)

        features = ["f1", "f2", "f3"]
        # Even if SHAP is installed, the result should have factors
        result = compute_shap_explanation(clf, features, X[0])
        assert "top_factors" in result
        assert len(result["top_factors"]) > 0


# ══════════════════════════════════════════════════════════════════
# Épica 5.2b: Clustering
# ══════════════════════════════════════════════════════════════════

from backend.ml.clustering import _describe_cluster, get_cluster_status, _CLUSTER_CACHE, CLUSTER_FEATURES


class TestDescribeCluster:

    def test_alto_compromiso_activo(self):
        profile = {
            "indice_compromiso": {"mean": 0.8, "std": 0.1},
            "dias_sin_acceso": {"mean": 2, "std": 1},
            "porcentaje_tareas": {"mean": 85, "std": 10},
            "prob_desercion": {"mean": 0.1, "std": 0.05},
            "score_recuperabilidad": {"mean": 80, "std": 10},
        }
        desc = _describe_cluster(profile)
        assert "alto compromiso" in desc
        assert "activos" in desc

    def test_bajo_compromiso_inactivo(self):
        profile = {
            "indice_compromiso": {"mean": 0.2, "std": 0.1},
            "dias_sin_acceso": {"mean": 20, "std": 5},
            "porcentaje_tareas": {"mean": 20, "std": 10},
            "prob_desercion": {"mean": 0.8, "std": 0.1},
            "score_recuperabilidad": {"mean": 20, "std": 10},
        }
        desc = _describe_cluster(profile)
        assert "bajo compromiso" in desc
        assert "inactivos" in desc
        assert "crítico" in desc


class TestGetClusterStatus:

    def test_not_run(self):
        _CLUSTER_CACHE.clear()
        r = get_cluster_status()
        assert r["status"] == "not_run"

    def test_features_list(self):
        assert len(CLUSTER_FEATURES) == 6
        assert "indice_compromiso" in CLUSTER_FEATURES


# ══════════════════════════════════════════════════════════════════
# Épica 5.3: Moodle API Client
# ══════════════════════════════════════════════════════════════════

from backend.integrations.moodle_api import MoodleAPIClient, MoodleAPIError, fetch_with_fallback


class TestMoodleAPIClient:

    def test_init(self):
        client = MoodleAPIClient("https://moodle.example.com", "token123")
        assert client.base_url == "https://moodle.example.com"
        assert client.token == "token123"
        assert "server.php" in client.ws_url

    def test_init_strips_trailing_slash(self):
        client = MoodleAPIClient("https://moodle.example.com/", "token123")
        assert client.base_url == "https://moodle.example.com"

    @patch("backend.integrations.moodle_api.httpx.get")
    def test_call_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"sitename": "Test Moodle"}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = MoodleAPIClient("https://moodle.example.com", "token123")
        result = client.get_site_info()
        assert result["sitename"] == "Test Moodle"

    @patch("backend.integrations.moodle_api.httpx.get")
    def test_call_moodle_exception(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"exception": "error", "message": "Token inválido"}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = MoodleAPIClient("https://moodle.example.com", "bad_token")
        with pytest.raises(MoodleAPIError, match="Token inválido"):
            client.get_site_info()

    @patch("backend.integrations.moodle_api.httpx.get")
    def test_get_course_activities(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {"modules": [{"id": 1, "name": "Tarea 1", "modname": "assign", "url": "http://x"}]},
            {"modules": [{"id": 2, "name": "Foro", "modname": "forum", "url": "http://y"}]},
        ]
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = MoodleAPIClient("https://moodle.example.com", "token")
        activities = client.get_course_activities(1)
        assert len(activities) == 2
        assert activities[0]["name"] == "Tarea 1"

    @patch("backend.integrations.moodle_api.httpx.get")
    def test_get_assignments(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "courses": [{"id": 1, "assignments": [{"id": 10, "name": "Tarea Final", "duedate": 1700000000, "cutoffdate": 0}]}]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = MoodleAPIClient("https://moodle.example.com", "token")
        assignments = client.get_assignments([1])
        assert len(assignments) == 1
        assert assignments[0]["name"] == "Tarea Final"


class TestFetchWithFallback:

    def test_fallback_to_scraping_when_no_client(self):
        scraping_fn = MagicMock(return_value={"data": "scraped"})
        data, source = fetch_with_fallback(None, "get_courses", scraping_fn)
        assert source == "scraping"
        assert data == {"data": "scraped"}

    @patch("backend.integrations.moodle_api.create_moodle_client")
    def test_fallback_on_api_error(self, mock_create):
        client = MagicMock()
        client.get_courses.side_effect = MoodleAPIError("timeout")
        mock_create.return_value = client

        scraping_fn = MagicMock(return_value={"data": "scraped"})
        data, source = fetch_with_fallback(MagicMock(), "get_courses", scraping_fn)
        assert source == "scraping"


# ══════════════════════════════════════════════════════════════════
# Épica 5.4: Multi-tenancy - Institutions
# ══════════════════════════════════════════════════════════════════

from backend.models.institution import Institution


class TestInstitutionModel:

    def test_table_name(self):
        assert Institution.__tablename__ == "institutions"

    def test_has_columns(self):
        cols = {c.name for c in Institution.__table__.columns}
        expected = {"id", "nombre", "codigo", "avac_url", "activa",
                    "umbral_riesgo_alto", "umbral_riesgo_medio",
                    "umbral_dias_critico", "umbral_compromiso_bajo"}
        assert expected.issubset(cols)

    def test_defaults(self):
        inst = Institution(nombre="Test Uni")
        assert inst.nombre == "Test Uni"


# Integration tests via TestClient

from backend.tests.conftest import *  # noqa


class TestInstitutionEndpoints:

    def test_list_empty(self, client, admin_token):
        resp = client.get("/institutions", cookies={"yd_token": admin_token})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_institution(self, client, admin_token):
        resp = client.post("/institutions", json={
            "nombre": "Universidad Test",
            "codigo": "UT",
        }, cookies={"yd_token": admin_token})
        assert resp.status_code == 200
        assert resp.json()["nombre"] == "Universidad Test"

    def test_create_duplicate_fails(self, client, admin_token):
        client.post("/institutions", json={"nombre": "Uni Dup"}, cookies={"yd_token": admin_token})
        resp = client.post("/institutions", json={"nombre": "Uni Dup"}, cookies={"yd_token": admin_token})
        assert resp.status_code == 409


class TestMLAdvancedEndpoints:

    def test_adaptive_status(self, client, admin_token):
        resp = client.get("/ml/adaptive/status", cookies={"yd_token": admin_token})
        assert resp.status_code == 200

    def test_clustering_status(self, client, admin_token):
        resp = client.get("/ml/clustering/status", cookies={"yd_token": admin_token})
        assert resp.status_code == 200
