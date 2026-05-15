"""
Tests para Fase 3 — Workflow de Intervenciones

Cubre:
  - Épica 3.1: Máquina de estados (transiciones válidas/inválidas)
  - Épica 3.2: Asignación y distribución de carga
  - Épica 3.3: SLAs y escalamiento automático
  - Épica 3.4: Recordatorios automáticos
  - Épica 3.5: Auditoría de acciones
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, PropertyMock

from backend.services.intervention_workflow import (
    VALID_STATES, TRANSITIONS, SLA_HOURS,
    validate_transition,
    transition_intervention,
    asignar_intervencion,
    autoasignar_round_robin,
    get_carga_monitores,
    detectar_overdue,
    generar_recordatorios,
    InterventionLog,
)


# ── Helpers ────────────────────────────────────────────────────────

def make_intervention(**kwargs):
    """Crea un mock de Intervention con campos workflow."""
    inv = MagicMock()
    inv.id = kwargs.get("id", 1)
    inv.student_id = kwargs.get("student_id", 100)
    inv.estado_workflow = kwargs.get("estado_workflow", "pendiente")
    inv.asignado_a = kwargs.get("asignado_a", None)
    inv.asignado_nombre = kwargs.get("asignado_nombre", None)
    inv.prioridad = kwargs.get("prioridad", 2)
    inv.fecha_asignacion = kwargs.get("fecha_asignacion", None)
    inv.fecha_limite = kwargs.get("fecha_limite", None)
    inv.fecha_contacto = kwargs.get("fecha_contacto", None)
    inv.fecha_resolucion = kwargs.get("fecha_resolucion", None)
    inv.escalado = kwargs.get("escalado", False)
    inv.escalado_a = kwargs.get("escalado_a", None)
    inv.overdue = kwargs.get("overdue", False)
    inv.nota_cierre = kwargs.get("nota_cierre", None)
    inv.motivo = kwargs.get("motivo", "bajo rendimiento")
    return inv


def make_db(query_return=None):
    """Crea un mock de Session."""
    db = MagicMock()
    if query_return is not None:
        db.query.return_value.filter.return_value.first.return_value = query_return
    return db


def make_user(id=1, nombre="Monitor A", role="monitor"):
    u = MagicMock()
    u.id = id
    u.nombre = nombre
    u.role = role
    return u


# ══════════════════════════════════════════════════════════════════
# Épica 3.1: Máquina de Estados
# ══════════════════════════════════════════════════════════════════

class TestValidateTransition:
    """Tests para validate_transition()."""

    def test_pendiente_a_en_progreso(self):
        assert validate_transition("pendiente", "en_progreso") is True

    def test_pendiente_a_escalado(self):
        assert validate_transition("pendiente", "escalado") is True

    def test_pendiente_a_cerrado(self):
        assert validate_transition("pendiente", "cerrado") is True

    def test_pendiente_a_resuelto_no_valido(self):
        assert validate_transition("pendiente", "resuelto") is False

    def test_en_progreso_a_contactado(self):
        assert validate_transition("en_progreso", "contactado") is True

    def test_en_progreso_a_sin_respuesta(self):
        assert validate_transition("en_progreso", "sin_respuesta") is True

    def test_contactado_a_resuelto(self):
        assert validate_transition("contactado", "resuelto") is True

    def test_resuelto_es_terminal(self):
        for state in VALID_STATES:
            assert validate_transition("resuelto", state) is False

    def test_cerrado_es_terminal(self):
        for state in VALID_STATES:
            assert validate_transition("cerrado", state) is False

    def test_sin_respuesta_a_en_progreso_reintento(self):
        assert validate_transition("sin_respuesta", "en_progreso") is True

    def test_escalado_a_en_progreso(self):
        assert validate_transition("escalado", "en_progreso") is True

    def test_escalado_a_resuelto(self):
        assert validate_transition("escalado", "resuelto") is True

    def test_none_se_trata_como_pendiente(self):
        assert validate_transition(None, "en_progreso") is True


class TestTransitionIntervention:
    """Tests para transition_intervention()."""

    def test_transition_ok(self):
        inv = make_intervention(estado_workflow="pendiente")
        db = make_db(inv)

        result = transition_intervention(db, 1, "en_progreso", user_id=5, user_nombre="Admin")

        assert "error" not in result
        assert result["estado_anterior"] == "pendiente"
        assert result["estado_nuevo"] == "en_progreso"
        assert inv.estado_workflow == "en_progreso"
        db.commit.assert_called_once()

    def test_transition_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        result = transition_intervention(db, 999, "en_progreso", user_id=1, user_nombre="X")
        assert result["error"] == "Intervención no encontrada"
        assert result["status"] == 404

    def test_transition_invalid_state(self):
        inv = make_intervention()
        db = make_db(inv)
        result = transition_intervention(db, 1, "inventado", user_id=1, user_nombre="X")
        assert "error" in result
        assert result["status"] == 400

    def test_transition_not_allowed(self):
        inv = make_intervention(estado_workflow="pendiente")
        db = make_db(inv)
        result = transition_intervention(db, 1, "resuelto", user_id=1, user_nombre="X")
        assert "error" in result
        assert "no permitida" in result["error"]

    def test_transition_contactado_sets_fecha(self):
        inv = make_intervention(estado_workflow="en_progreso")
        db = make_db(inv)
        transition_intervention(db, 1, "contactado", user_id=1, user_nombre="X")
        assert inv.fecha_contacto is not None

    def test_transition_resuelto_sets_fecha_resolucion(self):
        inv = make_intervention(estado_workflow="contactado")
        db = make_db(inv)
        transition_intervention(db, 1, "resuelto", user_id=1, user_nombre="X")
        assert inv.fecha_resolucion is not None

    def test_transition_escalado_sets_flag(self):
        inv = make_intervention(estado_workflow="en_progreso")
        db = make_db(inv)
        transition_intervention(db, 1, "escalado", user_id=1, user_nombre="X", escalado_a="Director")
        assert inv.escalado is True
        assert inv.escalado_a == "Director"

    def test_transition_con_nota(self):
        inv = make_intervention(estado_workflow="contactado")
        db = make_db(inv)
        transition_intervention(db, 1, "resuelto", user_id=1, user_nombre="X", nota="Problema resuelto")
        assert inv.nota_cierre == "Problema resuelto"

    def test_transition_creates_log(self):
        inv = make_intervention(estado_workflow="pendiente")
        db = make_db(inv)
        transition_intervention(db, 1, "en_progreso", user_id=5, user_nombre="Admin")
        # db.add should be called with InterventionLog
        added = [call[0][0] for call in db.add.call_args_list]
        assert any(isinstance(a, InterventionLog) for a in added)


# ══════════════════════════════════════════════════════════════════
# Épica 3.2: Asignación y Distribución de Carga
# ══════════════════════════════════════════════════════════════════

class TestAsignarIntervencion:
    """Tests para asignar_intervencion()."""

    def test_asignar_ok(self):
        inv = make_intervention(estado_workflow="pendiente")
        db = make_db(inv)
        result = asignar_intervencion(db, 1, asignado_a=10, asignado_nombre="Monitor B", prioridad=1)

        assert "error" not in result
        assert inv.asignado_a == 10
        assert inv.asignado_nombre == "Monitor B"
        assert inv.prioridad == 1
        assert inv.fecha_asignacion is not None
        assert inv.fecha_limite is not None
        # Pendiente se mueve a en_progreso
        assert inv.estado_workflow == "en_progreso"

    def test_asignar_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        result = asignar_intervencion(db, 999, asignado_a=1, asignado_nombre="X")
        assert result["error"] == "Intervención no encontrada"

    def test_asignar_sla_prioridad_1(self):
        inv = make_intervention(estado_workflow="pendiente")
        db = make_db(inv)
        asignar_intervencion(db, 1, asignado_a=10, asignado_nombre="X", prioridad=1)
        diff = inv.fecha_limite - inv.fecha_asignacion
        assert abs(diff.total_seconds() - 24 * 3600) < 5  # 24h ± 5s

    def test_asignar_sla_prioridad_3(self):
        inv = make_intervention(estado_workflow="pendiente")
        db = make_db(inv)
        asignar_intervencion(db, 1, asignado_a=10, asignado_nombre="X", prioridad=3)
        diff = inv.fecha_limite - inv.fecha_asignacion
        assert abs(diff.total_seconds() - 72 * 3600) < 5  # 72h

    def test_asignar_creates_log(self):
        inv = make_intervention(estado_workflow="pendiente")
        db = make_db(inv)
        asignar_intervencion(db, 1, asignado_a=10, asignado_nombre="Monitor B")
        added = [call[0][0] for call in db.add.call_args_list]
        assert any(isinstance(a, InterventionLog) for a in added)

    def test_asignar_no_cambia_estado_si_no_pendiente(self):
        inv = make_intervention(estado_workflow="en_progreso")
        db = make_db(inv)
        asignar_intervencion(db, 1, asignado_a=10, asignado_nombre="X")
        assert inv.estado_workflow == "en_progreso"


class TestGetCargaMonitores:
    """Tests para get_carga_monitores()."""

    def test_carga_vacia(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
        result = get_carga_monitores(db)
        assert result == []

    def test_carga_con_datos(self):
        row = MagicMock()
        row.asignado_a = 10
        row.asignado_nombre = "Monitor A"
        row.total = 5
        row.pendientes = 3
        db = MagicMock()
        db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [row]
        result = get_carga_monitores(db)
        assert len(result) == 1
        assert result[0]["total_activas"] == 5
        assert result[0]["pendientes"] == 3


# ══════════════════════════════════════════════════════════════════
# Épica 3.3: SLAs y Escalamiento Automático
# ══════════════════════════════════════════════════════════════════

class TestDetectarOverdue:
    """Tests para detectar_overdue()."""

    def test_marca_overdue(self):
        now = datetime.now(timezone.utc)
        inv = make_intervention(
            fecha_limite=now - timedelta(hours=1),
            overdue=False,
            estado_workflow="en_progreso",
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [inv]
        result = detectar_overdue(db)
        assert result["nuevas_overdue"] == 1
        assert inv.overdue is True
        db.commit.assert_called_once()

    def test_sin_overdue(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        result = detectar_overdue(db)
        assert result["nuevas_overdue"] == 0
        db.commit.assert_not_called()

    def test_overdue_crea_log(self):
        now = datetime.now(timezone.utc)
        inv = make_intervention(
            fecha_limite=now - timedelta(hours=1),
            overdue=False,
            estado_workflow="en_progreso",
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [inv]
        detectar_overdue(db)
        added = [call[0][0] for call in db.add.call_args_list]
        assert any(isinstance(a, InterventionLog) for a in added)


class TestSLAConstants:
    """Valida configuración de SLAs."""

    def test_sla_prioridad_1(self):
        assert SLA_HOURS[1] == 24

    def test_sla_prioridad_2(self):
        assert SLA_HOURS[2] == 48

    def test_sla_prioridad_3(self):
        assert SLA_HOURS[3] == 72


# ══════════════════════════════════════════════════════════════════
# Épica 3.4: Recordatorios Automáticos
# ══════════════════════════════════════════════════════════════════

class TestGenerarRecordatorios:
    """Tests para generar_recordatorios()."""

    def test_recordatorio_proximo_a_vencer(self):
        now = datetime.now(timezone.utc)
        inv = make_intervention(
            fecha_limite=now + timedelta(hours=3),
            overdue=False,
            estado_workflow="en_progreso",
            asignado_a=10,
            asignado_nombre="Monitor X",
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [inv]
        result = generar_recordatorios(db)
        assert len(result) == 1
        assert result[0]["horas_restantes"] < 6

    def test_sin_recordatorios(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        result = generar_recordatorios(db)
        assert result == []

    def test_recordatorio_contiene_campos(self):
        now = datetime.now(timezone.utc)
        inv = make_intervention(
            id=42,
            student_id=200,
            fecha_limite=now + timedelta(hours=2),
            overdue=False,
            estado_workflow="en_progreso",
            asignado_a=10,
            asignado_nombre="Monitor Y",
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [inv]
        result = generar_recordatorios(db)
        r = result[0]
        assert r["intervention_id"] == 42
        assert r["student_id"] == 200
        assert r["asignado_nombre"] == "Monitor Y"
        assert "fecha_limite" in r


# ══════════════════════════════════════════════════════════════════
# Épica 3.5: Auditoría de Acciones
# ══════════════════════════════════════════════════════════════════

class TestInterventionLogModel:
    """Tests del modelo InterventionLog."""

    def test_table_name(self):
        assert InterventionLog.__tablename__ == "intervention_logs"

    def test_has_required_columns(self):
        cols = {c.name for c in InterventionLog.__table__.columns}
        expected = {"id", "intervention_id", "user_id", "user_nombre", "accion",
                    "estado_anterior", "estado_nuevo", "detalle", "created_at"}
        assert expected.issubset(cols)


# ══════════════════════════════════════════════════════════════════
# Tests de constantes y estados
# ══════════════════════════════════════════════════════════════════

class TestEstados:
    """Valida la coherencia de la máquina de estados."""

    def test_7_estados(self):
        assert len(VALID_STATES) == 7

    def test_estados_terminales_sin_transiciones(self):
        assert TRANSITIONS["resuelto"] == set()
        assert TRANSITIONS["cerrado"] == set()

    def test_todos_estados_en_transitions(self):
        assert set(TRANSITIONS.keys()) == VALID_STATES

    def test_transiciones_solo_a_estados_validos(self):
        for src, targets in TRANSITIONS.items():
            for t in targets:
                assert t in VALID_STATES, f"Transición {src}→{t} apunta a estado inválido"
