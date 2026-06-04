"""
Tests para Fase 4 — Analytics Avanzados

Cubre:
  - Épica 4.1: Dashboard Ejecutivo
  - Épica 4.2: Efectividad de Intervenciones
  - Épica 4.3: Análisis Histórico por Asignatura
  - Épica 4.4: Efectividad Docente
  - Épica 4.5: Reporte Mensual
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone


# ══════════════════════════════════════════════════════════════════
# Épica 4.2: Efectividad helpers
# ══════════════════════════════════════════════════════════════════

from backend.routes.analytics.effectiveness import _calcular_efectividad_intervencion, _agrupar_por


class TestCalcularEfectividadIntervencion:

    def _make_inv(self, **kw):
        inv = MagicMock()
        inv.id = kw.get("id", 1)
        inv.student_id = kw.get("student_id", 10)
        inv.medio = kw.get("medio", "WhatsApp")
        inv.motivo = kw.get("motivo", "Bajo rendimiento")
        inv.resultado = kw.get("resultado", "Contactado")
        inv.estado_workflow = kw.get("estado_workflow", "resuelto")
        inv.carrera = kw.get("carrera", "Ingeniería")
        inv.snapshot_compromiso = kw.get("snapshot_compromiso", 0.3)
        inv.snapshot_porcentaje_tareas = kw.get("snapshot_porcentaje_tareas", 40.0)
        inv.snapshot_prob_desercion = kw.get("snapshot_prob_desercion", 0.7)
        return inv

    def _make_student(self, **kw):
        s = MagicMock()
        s.indice_compromiso = kw.get("indice_compromiso", 0.6)
        s.porcentaje_tareas = kw.get("porcentaje_tareas", 70.0)
        s.prob_desercion = kw.get("prob_desercion", 0.3)
        return s

    def test_exitosa_mejora_compromiso(self):
        inv = self._make_inv(snapshot_compromiso=0.3)
        student = self._make_student(indice_compromiso=0.6)
        result = _calcular_efectividad_intervencion(inv, student)
        assert result["exitosa"] is True
        assert result["delta_compromiso"] > 0

    def test_exitosa_baja_desercion(self):
        inv = self._make_inv(snapshot_compromiso=0.5, snapshot_prob_desercion=0.8)
        student = self._make_student(indice_compromiso=0.5, prob_desercion=0.3)
        result = _calcular_efectividad_intervencion(inv, student)
        assert result["exitosa"] is True
        assert result["delta_prob_desercion"] < 0

    def test_no_exitosa(self):
        inv = self._make_inv(snapshot_compromiso=0.6, snapshot_prob_desercion=0.3)
        student = self._make_student(indice_compromiso=0.4, prob_desercion=0.5)
        result = _calcular_efectividad_intervencion(inv, student)
        assert result["exitosa"] is False

    def test_sin_student(self):
        inv = self._make_inv()
        result = _calcular_efectividad_intervencion(inv, None)
        assert result["delta_compromiso"] is None
        assert result["exitosa"] is False

    def test_sin_snapshots(self):
        inv = self._make_inv(snapshot_compromiso=None, snapshot_prob_desercion=None, snapshot_porcentaje_tareas=None)
        student = self._make_student()
        result = _calcular_efectividad_intervencion(inv, student)
        assert result["delta_compromiso"] is None

    def test_campos_basicos(self):
        inv = self._make_inv(id=42, medio="Llamada", motivo="Inactividad")
        student = self._make_student()
        result = _calcular_efectividad_intervencion(inv, student)
        assert result["intervention_id"] == 42
        assert result["medio"] == "Llamada"
        assert result["motivo"] == "Inactividad"


class TestAgruparPor:

    def test_agrupar_por_medio(self):
        datos = [
            {"medio": "WhatsApp", "exitosa": True, "delta_compromiso": 0.1},
            {"medio": "WhatsApp", "exitosa": False, "delta_compromiso": -0.05},
            {"medio": "Llamada", "exitosa": True, "delta_compromiso": 0.2},
        ]
        result = _agrupar_por(datos, "medio")
        assert len(result) == 2
        wa = next(r for r in result if r["medio"] == "WhatsApp")
        assert wa["total"] == 2
        assert wa["exitosas"] == 1
        assert wa["tasa_exito"] == 50.0

    def test_campo_none(self):
        datos = [{"medio": None, "exitosa": True, "delta_compromiso": 0.1}]
        result = _agrupar_por(datos, "medio")
        assert result[0]["medio"] == "Sin especificar"

    def test_vacio(self):
        result = _agrupar_por([], "medio")
        assert result == []


# ══════════════════════════════════════════════════════════════════
# Épica 4.3: Tendencia lineal
# ══════════════════════════════════════════════════════════════════

from backend.routes.analytics.historical import _linear_trend


class TestLinearTrend:

    def test_tendencia_empeorando(self):
        values = [10, 15, 20, 30, 40]
        result = _linear_trend(values)
        assert result["tendencia"] == "empeorando"
        assert result["slope"] > 0

    def test_tendencia_mejorando(self):
        values = [40, 30, 20, 15, 10]
        result = _linear_trend(values)
        assert result["tendencia"] == "mejorando"
        assert result["slope"] < 0

    def test_tendencia_estable(self):
        values = [20, 20, 20, 20]
        result = _linear_trend(values)
        assert result["tendencia"] == "estable"

    def test_un_solo_valor(self):
        result = _linear_trend([10])
        assert result["tendencia"] == "estable"

    def test_vacio(self):
        result = _linear_trend([])
        assert result["tendencia"] == "estable"

    def test_dos_valores(self):
        result = _linear_trend([10, 50])
        assert result["tendencia"] == "empeorando"


# ══════════════════════════════════════════════════════════════════
# Épica 4.1/4.5: Endpoint integration via TestClient
# ══════════════════════════════════════════════════════════════════

from backend.tests.conftest import *  # noqa - import fixtures


class TestExecutiveEndpoint:
    """Test executive dashboard endpoint."""

    def test_executive_sin_datos(self, client, admin_token):
        resp = client.get("/analytics/executive", cookies={"yd_token": admin_token})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_estudiantes"] == 0

    def test_executive_con_periodo(self, client, admin_token):
        resp = client.get("/analytics/executive?periodo=P68", cookies={"yd_token": admin_token})
        assert resp.status_code == 200


class TestEffectivenessEndpoint:

    def test_effectiveness_sin_datos(self, client, admin_token):
        resp = client.get("/analytics/effectiveness", cookies={"yd_token": admin_token})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_analizadas"] == 0


class TestHistoricalEndpoint:

    def test_historical_sin_datos(self, client, admin_token):
        resp = client.get("/analytics/historical/asignaturas", cookies={"yd_token": admin_token})
        assert resp.status_code == 200
        data = resp.json()
        assert data["asignaturas"] == []

    def test_abandono_sin_datos(self, client, admin_token):
        resp = client.get("/analytics/historical/abandono-asignaturas", cookies={"yd_token": admin_token})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_desertores"] == 0


class TestDocenteEffectivenessEndpoint:

    def test_docente_effectiveness_sin_datos(self, client, admin_token):
        resp = client.get("/analytics/docente-effectiveness", cookies={"yd_token": admin_token})
        assert resp.status_code == 200
        data = resp.json()
        assert data["docentes"] == []


class TestMonthlyReportEndpoint:

    def test_monthly_report_sin_datos(self, client, admin_token):
        resp = client.get("/analytics/monthly-report", cookies={"yd_token": admin_token})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_estudiantes"] == 0

    def test_monthly_report_con_periodo(self, client, admin_token):
        resp = client.get("/analytics/monthly-report?periodo=P68", cookies={"yd_token": admin_token})
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════
# Test de consistencia de routers
# ══════════════════════════════════════════════════════════════════

class TestRouterRegistration:

    def test_analytics_has_executive_routes(self):
        from backend.routes.analytics import router
        paths = [r.path for r in router.routes]
        assert "/executive" in paths or any("/executive" in p for p in paths)

    def test_analytics_has_effectiveness_routes(self):
        from backend.routes.analytics import router
        paths = [r.path for r in router.routes]
        assert any("effectiveness" in p for p in paths)

    def test_analytics_has_historical_routes(self):
        from backend.routes.analytics import router
        paths = [r.path for r in router.routes]
        assert any("historical" in p for p in paths)

    def test_analytics_has_monthly_report_routes(self):
        from backend.routes.analytics import router
        paths = [r.path for r in router.routes]
        assert any("monthly-report" in p for p in paths)
