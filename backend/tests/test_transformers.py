"""
Unit tests for backend.etl.transformers — pure function tests.
No database or API fixtures needed.
"""
import math
import pytest
import numpy as np

from backend.etl.transformers import (
    normalizar_nombre,
    parse_dias_acceso,
    parse_calificacion,
    parse_estado_tarea,
    normalizar_carrera,
    extraer_grupo_numero,
    parse_nivel_academico,
    calcular_indice_compromiso,
)


class TestNormalizarNombre:
    def test_normal_name(self):
        assert normalizar_nombre("Juan Perez") == "JUAN PEREZ"

    def test_strips_avac_prefix(self):
        assert normalizar_nombre("Seleccionar 'MARIA LOPEZ'") == "MARIA LOPEZ"

    def test_collapses_extra_spaces(self):
        assert normalizar_nombre("Juan   Carlos   Perez") == "JUAN CARLOS PEREZ"

    def test_none_returns_empty(self):
        assert normalizar_nombre(None) == ""

    def test_empty_string_returns_empty(self):
        assert normalizar_nombre("") == ""

    def test_nan_returns_empty(self):
        assert normalizar_nombre(float("nan")) == ""

    def test_prefix_without_quotes(self):
        assert normalizar_nombre("Seleccionar LUIS") == "LUIS"


class TestParseDiasAcceso:
    def test_days_and_hours(self):
        result = parse_dias_acceso("8 dias 17 horas")
        assert result == pytest.approx(8.71, abs=0.01)

    def test_hours_only(self):
        result = parse_dias_acceso("3 horas")
        assert result == pytest.approx(3 / 24, abs=0.01)

    def test_minutes_only(self):
        result = parse_dias_acceso("45 minutos")
        assert result == pytest.approx(45 / 1440, abs=0.01)

    def test_nunca_returns_none(self):
        assert parse_dias_acceso("Nunca") is None

    def test_dash_returns_none(self):
        assert parse_dias_acceso("-") is None

    def test_none_returns_none(self):
        assert parse_dias_acceso(None) is None

    def test_empty_returns_none(self):
        assert parse_dias_acceso("") is None

    def test_zero_days_zero_hours(self):
        result = parse_dias_acceso("0 dias 0 horas")
        assert result == 0.0


class TestParseCalificacion:
    def test_normal_with_comma(self):
        assert parse_calificacion("15,00 / 15,00") == (15.0, 15.0)

    def test_zero_score(self):
        assert parse_calificacion("0,00 / 20,00") == (0.0, 20.0)

    def test_single_value(self):
        score, maximum = parse_calificacion("10,50")
        assert score == 10.5
        assert maximum is None

    def test_dash_returns_nones(self):
        assert parse_calificacion("-") == (None, None)

    def test_none_returns_nones(self):
        assert parse_calificacion(None) == (None, None)

    def test_empty_returns_nones(self):
        assert parse_calificacion("") == (None, None)

    def test_fractional_score(self):
        assert parse_calificacion("10,50 / 20,00") == (10.5, 20.0)


class TestParseEstadoTarea:
    def test_enviado_para_calificar(self):
        assert parse_estado_tarea("Enviado para calificar") == (True, False, False)

    def test_calificado(self):
        assert parse_estado_tarea("Calificado") == (True, True, False)

    def test_enviado_retrasada(self):
        assert parse_estado_tarea("Enviado para calificar - Retrasada") == (True, False, True)

    def test_calificado_retrasada(self):
        assert parse_estado_tarea("Calificado - Retrasada") == (True, True, True)

    def test_none_returns_false_triple(self):
        assert parse_estado_tarea(None) == (False, False, False)

    def test_empty_returns_false_triple(self):
        assert parse_estado_tarea("") == (False, False, False)


class TestNormalizarCarrera:
    def test_normal(self):
        assert normalizar_carrera("Educacion Intercultural") == "EDUCACION INTERCULTURAL"

    def test_strips_brackets(self):
        result = normalizar_carrera("Educacion [Bilingue] Intercultural")
        assert result == "EDUCACION INTERCULTURAL"

    def test_collapses_extra_spaces(self):
        assert normalizar_carrera("Educacion   Intercultural") == "EDUCACION INTERCULTURAL"

    def test_none_returns_empty(self):
        assert normalizar_carrera(None) == ""

    def test_nan_returns_empty(self):
        assert normalizar_carrera(float("nan")) == ""


class TestExtraerGrupoNumero:
    def test_standard_format(self):
        assert extraer_grupo_numero("Grupo - 3") == "3"

    def test_multi_digit(self):
        assert extraer_grupo_numero("Grupo - 16 (Educacion Intercultural)") == "16"

    def test_uppercase(self):
        assert extraer_grupo_numero("GRUPO - 5") == "5"

    def test_no_match(self):
        assert extraer_grupo_numero("Eib 13041 Latacunga") is None

    def test_none_returns_none(self):
        assert extraer_grupo_numero(None) is None

    def test_empty_returns_none(self):
        assert extraer_grupo_numero("") is None


class TestParseNivelAcademico:
    def test_ordinal_1er(self):
        assert parse_nivel_academico("1er nivel") == 1

    def test_ordinal_5to(self):
        assert parse_nivel_academico("5to nivel") == 5

    def test_ordinal_7mo(self):
        assert parse_nivel_academico("7mo nivel") == 7

    def test_numeric_string(self):
        assert parse_nivel_academico("3") == 3

    def test_integer_value(self):
        assert parse_nivel_academico(5) == 5

    def test_float_value(self):
        assert parse_nivel_academico(8.0) == 8

    def test_out_of_range_zero(self):
        assert parse_nivel_academico(0) is None

    def test_out_of_range_eleven(self):
        assert parse_nivel_academico(11) is None

    def test_oyente_condicionado(self):
        assert parse_nivel_academico("Oyente condicionado") is None

    def test_none_returns_none(self):
        assert parse_nivel_academico(None) is None

    def test_nan_returns_none(self):
        assert parse_nivel_academico(float("nan")) is None


class TestCalcularIndiceCompromiso:
    def test_high_engagement_low_risk(self):
        """Active student, many tasks done, good grades, enrolled."""
        result = calcular_indice_compromiso(
            dias_sin_acceso=1.0,
            tareas_entregadas=8,
            tareas_totales=10,
            notas=[85.0, 90.0],
            bloque_actual=1,
            promedio_calificaciones=87.0,
            estado_matricula="Matriculado",
        )
        assert result["nivel_riesgo"] == "Bajo"
        assert result["color_riesgo"] == "#00B050"
        assert result["indice_compromiso"] >= 0.65

    def test_low_engagement_high_risk(self):
        """30 days inactive, no tasks, low grades."""
        result = calcular_indice_compromiso(
            dias_sin_acceso=30.0,
            tareas_entregadas=0,
            tareas_totales=10,
            notas=[30.0],
            bloque_actual=1,
            promedio_calificaciones=30.0,
            estado_matricula="Matriculado",
        )
        assert result["nivel_riesgo"] == "Alto"
        assert result["color_riesgo"] == "#FF4C4C"
        assert result["indice_compromiso"] < 0.35

    def test_insufficient_data(self):
        """All None/0 -- fewer than 2 data points."""
        result = calcular_indice_compromiso(
            dias_sin_acceso=None,
            tareas_entregadas=0,
            tareas_totales=0,
            notas=[],
            bloque_actual=1,
            promedio_calificaciones=None,
            estado_matricula=None,
        )
        assert result["nivel_riesgo"] is None
        assert result["color_riesgo"] == "#94a3b8"

    def test_medium_engagement(self):
        """Moderate activity -- medium risk."""
        result = calcular_indice_compromiso(
            dias_sin_acceso=10.0,
            tareas_entregadas=4,
            tareas_totales=10,
            notas=[65.0],
            bloque_actual=1,
            promedio_calificaciones=65.0,
            estado_matricula="Matriculado",
        )
        assert result["nivel_riesgo"] == "Medio"
        assert result["color_riesgo"] == "#FFC000"
        assert 0.35 <= result["indice_compromiso"] < 0.65

    def test_result_keys(self):
        """Verify all expected keys are present."""
        result = calcular_indice_compromiso(
            dias_sin_acceso=5.0,
            tareas_entregadas=3,
            tareas_totales=5,
            notas=[],
            bloque_actual=1,
            promedio_calificaciones=70.0,
            estado_matricula="Matriculado",
        )
        expected_keys = {
            "indice_compromiso", "nivel_riesgo", "color_riesgo",
            "puntaje_acceso", "puntaje_tareas",
            "puntaje_rendimiento", "puntaje_admin",
        }
        assert set(result.keys()) == expected_keys

    def test_component_scores_are_bounded(self):
        """Each component score should be non-negative."""
        result = calcular_indice_compromiso(
            dias_sin_acceso=0.0,
            tareas_entregadas=10,
            tareas_totales=10,
            notas=[100.0],
            bloque_actual=1,
            promedio_calificaciones=100.0,
            estado_matricula="Matriculado",
        )
        assert result["puntaje_acceso"] >= 0
        assert result["puntaje_tareas"] >= 0
        assert result["puntaje_rendimiento"] >= 0
        assert result["puntaje_admin"] >= 0
        assert result["indice_compromiso"] <= 1.0
