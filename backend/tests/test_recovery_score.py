"""Tests para el Score de Recuperabilidad (Épica 1.4)."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import date, timedelta

from backend.services.recovery_score import (
    _score_actividad,
    _score_tareas,
    _score_calificaciones,
    _score_historial,
    _score_tendencia,
    calcular_score_estudiante,
    calcular_scores_batch,
    MAX_DIAS_INACTIVIDAD,
    MAX_REPITENCIAS,
)


# ── Tests de componentes individuales ──────────────────────────────

class TestScoreActividad:
    def test_sin_datos_retorna_neutro(self):
        assert _score_actividad(None) == 50.0

    def test_cero_dias_retorna_100(self):
        assert _score_actividad(0) == 100.0

    def test_max_dias_retorna_0(self):
        assert _score_actividad(MAX_DIAS_INACTIVIDAD) == 0.0

    def test_medio_rango(self):
        score = _score_actividad(30)
        assert 40 < score < 60  # ~50%

    def test_negativo_retorna_100(self):
        assert _score_actividad(-5) == 100.0


class TestScoreTareas:
    def test_sin_datos_retorna_neutro(self):
        assert _score_tareas(None) == 50.0

    def test_100_porciento(self):
        assert _score_tareas(100.0) == 100.0

    def test_0_porciento(self):
        assert _score_tareas(0.0) == 0.0

    def test_clamp_superior(self):
        assert _score_tareas(150.0) == 100.0


class TestScoreCalificaciones:
    def test_sin_datos_retorna_neutro(self):
        assert _score_calificaciones(None) == 50.0

    def test_aprobado_retorna_100(self):
        assert _score_calificaciones(7.0) == 100.0
        assert _score_calificaciones(10.0) == 100.0

    def test_cero_retorna_0(self):
        assert _score_calificaciones(0.0) == 0.0

    def test_mitad(self):
        score = _score_calificaciones(3.5)
        assert 45 < score < 55


class TestScoreHistorial:
    def test_sin_repitencias(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.scalar.return_value = None
        assert _score_historial(1, db) == 100.0

    def test_cero_repitencias(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.scalar.return_value = 0
        assert _score_historial(1, db) == 100.0

    def test_max_repitencias(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.scalar.return_value = MAX_REPITENCIAS
        assert _score_historial(1, db) == 0.0


class TestScoreTendencia:
    def test_sin_snapshots(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        assert _score_tendencia(1, db) == 50.0

    def test_un_solo_snapshot(self):
        db = MagicMock()
        snap = MagicMock()
        snap.dias_sin_acceso = 5
        snap.snapshot_date = date.today()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [snap]
        assert _score_tendencia(1, db) == 50.0

    def test_mejorando(self):
        db = MagicMock()
        snap_reciente = MagicMock(dias_sin_acceso=2, snapshot_date=date.today())
        snap_anterior = MagicMock(dias_sin_acceso=10, snapshot_date=date.today() - timedelta(days=7))
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [snap_reciente, snap_anterior]
        score = _score_tendencia(1, db)
        assert score > 50  # mejorando

    def test_empeorando(self):
        db = MagicMock()
        snap_reciente = MagicMock(dias_sin_acceso=15, snapshot_date=date.today())
        snap_anterior = MagicMock(dias_sin_acceso=3, snapshot_date=date.today() - timedelta(days=7))
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [snap_reciente, snap_anterior]
        score = _score_tendencia(1, db)
        assert score < 50  # empeorando


class TestCalcularScoreEstudiante:
    def test_retorna_estructura_completa(self):
        student = MagicMock()
        student.id = 1
        student.dias_sin_acceso = 5
        student.porcentaje_tareas = 80.0
        student.promedio_calificaciones = 7.5
        db = MagicMock()
        db.query.return_value.filter.return_value.scalar.return_value = 0
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        result = calcular_score_estudiante(student, db)

        assert "score_total" in result
        assert "nivel" in result
        assert "componentes" in result
        assert "recomendacion" in result
        assert result["nivel"] in ("alto", "medio", "bajo")
        assert 0 <= result["score_total"] <= 100

    def test_buen_estudiante_nivel_alto(self):
        student = MagicMock()
        student.id = 1
        student.dias_sin_acceso = 1
        student.porcentaje_tareas = 95.0
        student.promedio_calificaciones = 9.0
        db = MagicMock()
        db.query.return_value.filter.return_value.scalar.return_value = 0
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        result = calcular_score_estudiante(student, db)
        assert result["nivel"] == "alto"
        assert result["score_total"] >= 65

    def test_mal_estudiante_nivel_bajo(self):
        student = MagicMock()
        student.id = 1
        student.dias_sin_acceso = 55
        student.porcentaje_tareas = 5.0
        student.promedio_calificaciones = 1.0
        db = MagicMock()
        db.query.return_value.filter.return_value.scalar.return_value = 3
        snap_reciente = MagicMock(dias_sin_acceso=55, snapshot_date=date.today())
        snap_anterior = MagicMock(dias_sin_acceso=30, snapshot_date=date.today() - timedelta(days=7))
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [snap_reciente, snap_anterior]

        result = calcular_score_estudiante(student, db)
        assert result["nivel"] == "bajo"
        assert result["score_total"] < 35

    def test_custom_weights(self):
        student = MagicMock()
        student.id = 1
        student.dias_sin_acceso = 0
        student.porcentaje_tareas = 0.0
        student.promedio_calificaciones = 0.0
        db = MagicMock()
        db.query.return_value.filter.return_value.scalar.return_value = 0
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        # Solo peso en actividad (100% actividad = 100 * 1.0 = 100)
        weights = {"actividad": 1.0, "tareas": 0.0, "calificaciones": 0.0, "historial": 0.0, "tendencia": 0.0}
        result = calcular_score_estudiante(student, db, weights=weights)
        assert result["score_total"] == 100.0


class TestCalcularScoresBatch:
    def test_batch_persiste_y_retorna_stats(self):
        s1 = MagicMock()
        s1.id = 1
        s1.dias_sin_acceso = 1
        s1.porcentaje_tareas = 90.0
        s1.promedio_calificaciones = 8.0

        s2 = MagicMock()
        s2.id = 2
        s2.dias_sin_acceso = 50
        s2.porcentaje_tareas = 10.0
        s2.promedio_calificaciones = 2.0

        db = MagicMock()
        db.query.return_value.all.return_value = [s1, s2]
        db.query.return_value.filter.return_value.scalar.return_value = 0
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        result = calcular_scores_batch(db)

        assert result["total_calculados"] == 2
        assert "distribucion" in result
        assert result["distribucion"]["alto"] + result["distribucion"]["medio"] + result["distribucion"]["bajo"] == 2
        db.commit.assert_called_once()
        # Verificar que se persistió en el modelo
        assert s1.score_recuperabilidad is not None
        assert s1.nivel_recuperabilidad is not None
