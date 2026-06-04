"""
Servicio de Workflow de Intervenciones — Fase 3

Gestiona la máquina de estados, asignación de carga, SLAs,
escalamiento automático y auditoría de acciones.

Estados válidos:
  pendiente → en_progreso → contactado → resuelto | escalado | sin_respuesta | cerrado
                          → sin_respuesta → en_progreso (reintentar)
                          → escalado (desde cualquier estado excepto resuelto/cerrado)

SLAs por prioridad:
  1 (urgente): 24 horas
  2 (normal):  48 horas
  3 (baja):    72 horas
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from ..models.intervention import Intervention
from ..models.user import User


# ── Máquina de Estados (Épica 3.1) ────────────────────────────────

VALID_STATES = {"pendiente", "en_progreso", "contactado", "resuelto", "escalado", "sin_respuesta", "cerrado"}

TRANSITIONS = {
    "pendiente":      {"en_progreso", "escalado", "cerrado"},
    "en_progreso":    {"contactado", "sin_respuesta", "escalado", "cerrado"},
    "contactado":     {"resuelto", "escalado", "cerrado"},
    "sin_respuesta":  {"en_progreso", "escalado", "cerrado"},
    "escalado":       {"en_progreso", "resuelto", "cerrado"},
    "resuelto":       set(),   # estado terminal
    "cerrado":        set(),   # estado terminal
}

SLA_HOURS = {1: 24, 2: 48, 3: 72}


def validate_transition(current: str, target: str) -> bool:
    """Verifica si la transición de estado es válida."""
    current = current or "pendiente"
    return target in TRANSITIONS.get(current, set())


def transition_intervention(
    db: Session,
    intervention_id: int,
    new_state: str,
    user_id: int,
    user_nombre: str,
    nota: Optional[str] = None,
    escalado_a: Optional[str] = None,
) -> dict:
    """Ejecuta una transición de estado en una intervención.

    Retorna dict con la intervención actualizada o error.
    """
    inv = db.query(Intervention).filter(Intervention.id == intervention_id).first()
    if not inv:
        return {"error": "Intervención no encontrada", "status": 404}

    current = inv.estado_workflow or "pendiente"
    if new_state not in VALID_STATES:
        return {"error": f"Estado '{new_state}' no es válido. Estados: {', '.join(sorted(VALID_STATES))}", "status": 400}

    if not validate_transition(current, new_state):
        allowed = TRANSITIONS.get(current, set())
        return {"error": f"Transición '{current}' → '{new_state}' no permitida. Permitidas: {', '.join(sorted(allowed))}", "status": 400}

    now = datetime.now(timezone.utc)

    # Actualizar estado
    inv.estado_workflow = new_state

    # Timestamps según estado
    if new_state == "contactado":
        inv.fecha_contacto = now
    elif new_state == "resuelto" or new_state == "cerrado":
        inv.fecha_resolucion = now
    elif new_state == "escalado":
        inv.escalado = True
        inv.escalado_a = escalado_a

    # Nota de cierre
    if nota:
        inv.nota_cierre = nota

    # Log de auditoría (Épica 3.5)
    log_entry = InterventionLog(
        intervention_id=inv.id,
        user_id=user_id,
        user_nombre=user_nombre,
        accion="cambio_estado",
        estado_anterior=current,
        estado_nuevo=new_state,
        detalle=nota,
    )
    db.add(log_entry)
    db.commit()

    return {
        "id": inv.id,
        "estado_anterior": current,
        "estado_nuevo": new_state,
        "timestamp": now.isoformat(),
    }


# ── Asignación y Distribución de Carga (Épica 3.2) ────────────────

def get_carga_monitores(db: Session) -> list[dict]:
    """Retorna la distribución de carga de intervenciones activas por monitor."""
    activas = db.query(
        Intervention.asignado_a,
        Intervention.asignado_nombre,
        sqlfunc.count(Intervention.id).label("total"),
        sqlfunc.count(sqlfunc.nullif(Intervention.estado_workflow, "resuelto")).label("pendientes"),
    ).filter(
        Intervention.asignado_a.isnot(None),
        Intervention.estado_workflow.notin_(["resuelto", "cerrado"]),
    ).group_by(Intervention.asignado_a, Intervention.asignado_nombre).all()

    return [
        {"user_id": r.asignado_a, "nombre": r.asignado_nombre, "total_activas": r.total, "pendientes": r.pendientes}
        for r in activas
    ]


def asignar_intervencion(
    db: Session,
    intervention_id: int,
    asignado_a: int,
    asignado_nombre: str,
    prioridad: int = 2,
    user_id: int = None,
    user_nombre: str = None,
) -> dict:
    """Asigna una intervención a un monitor y calcula SLA."""
    inv = db.query(Intervention).filter(Intervention.id == intervention_id).first()
    if not inv:
        return {"error": "Intervención no encontrada", "status": 404}

    now = datetime.now(timezone.utc)
    inv.asignado_a = asignado_a
    inv.asignado_nombre = asignado_nombre
    inv.prioridad = prioridad
    inv.fecha_asignacion = now
    inv.fecha_limite = now + timedelta(hours=SLA_HOURS.get(prioridad, 48))

    if inv.estado_workflow == "pendiente":
        inv.estado_workflow = "en_progreso"

    # Log
    log_entry = InterventionLog(
        intervention_id=inv.id,
        user_id=user_id or asignado_a,
        user_nombre=user_nombre or asignado_nombre,
        accion="asignacion",
        detalle=f"Asignada a {asignado_nombre}, prioridad {prioridad}, SLA: {SLA_HOURS.get(prioridad, 48)}h",
    )
    db.add(log_entry)
    db.commit()

    return {
        "id": inv.id,
        "asignado_a": asignado_a,
        "asignado_nombre": asignado_nombre,
        "fecha_limite": inv.fecha_limite.isoformat(),
        "estado_workflow": inv.estado_workflow,
    }


def autoasignar_round_robin(db: Session, intervention_ids: list[int], user_id: int, user_nombre: str) -> dict:
    """Autoasigna intervenciones pendientes distribuyendo equitativamente entre monitores activos."""
    monitores = db.query(User).filter(User.role.in_(["monitor", "admin"]), User.role.in_(["monitor", "admin"])).all()
    if not monitores:
        return {"error": "No hay monitores activos", "asignadas": 0}

    # Obtener carga actual
    carga = {m.id: 0 for m in monitores}
    activas = db.query(Intervention.asignado_a, sqlfunc.count(Intervention.id)).filter(
        Intervention.asignado_a.isnot(None),
        Intervention.estado_workflow.notin_(["resuelto", "cerrado"]),
    ).group_by(Intervention.asignado_a).all()
    for uid, count in activas:
        if uid in carga:
            carga[uid] = count

    # Ordenar monitores por menor carga
    sorted_monitores = sorted(monitores, key=lambda m: carga.get(m.id, 0))

    asignadas = 0
    for i, inv_id in enumerate(intervention_ids):
        monitor = sorted_monitores[i % len(sorted_monitores)]
        result = asignar_intervencion(db, inv_id, monitor.id, monitor.nombre, user_id=user_id, user_nombre=user_nombre)
        if "error" not in result:
            asignadas += 1

    return {"asignadas": asignadas, "total_monitores": len(monitores)}


# ── SLAs y Escalamiento (Épica 3.3) ───────────────────────────────

def detectar_overdue(db: Session) -> dict:
    """Marca como overdue las intervenciones que superaron su SLA.
    Retorna conteo de nuevas intervenciones marcadas como overdue."""
    now = datetime.now(timezone.utc)

    overdue_new = db.query(Intervention).filter(
        Intervention.fecha_limite.isnot(None),
        Intervention.fecha_limite < now,
        Intervention.overdue == False,
        Intervention.estado_workflow.notin_(["resuelto", "cerrado"]),
    ).all()

    count = 0
    for inv in overdue_new:
        inv.overdue = True
        log_entry = InterventionLog(
            intervention_id=inv.id,
            user_id=None,
            user_nombre="sistema",
            accion="overdue",
            detalle=f"SLA vencido. Fecha límite: {inv.fecha_limite.isoformat()}",
        )
        db.add(log_entry)
        count += 1

    if count > 0:
        db.commit()

    return {"nuevas_overdue": count}


def generar_recordatorios(db: Session) -> list[dict]:
    """Genera lista de intervenciones que se acercan al vencimiento (< 6h restantes).
    Épica 3.4: Recordatorios Automáticos."""
    now = datetime.now(timezone.utc)
    umbral = now + timedelta(hours=6)

    proximas = db.query(Intervention).filter(
        Intervention.fecha_limite.isnot(None),
        Intervention.fecha_limite > now,
        Intervention.fecha_limite <= umbral,
        Intervention.overdue == False,
        Intervention.estado_workflow.notin_(["resuelto", "cerrado"]),
    ).all()

    recordatorios = []
    for inv in proximas:
        horas_restantes = (inv.fecha_limite - now).total_seconds() / 3600
        recordatorios.append({
            "intervention_id": inv.id,
            "student_id": inv.student_id,
            "asignado_a": inv.asignado_a,
            "asignado_nombre": inv.asignado_nombre,
            "estado": inv.estado_workflow,
            "horas_restantes": round(horas_restantes, 1),
            "fecha_limite": inv.fecha_limite.isoformat(),
        })

    return recordatorios


# ── Modelo de Log de Auditoría (Épica 3.5) ────────────────────────
# Importado aquí para evitar circular imports; se registra en models/__init__.py

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from ..database import Base

class InterventionLog(Base):
    """Log de auditoría para intervenciones."""
    __tablename__ = "intervention_logs"

    id = Column(Integer, primary_key=True, index=True)
    intervention_id = Column(Integer, ForeignKey("interventions.id", ondelete="CASCADE"), index=True)
    user_id = Column(Integer, nullable=True)
    user_nombre = Column(String, nullable=True)
    accion = Column(String, nullable=False)  # cambio_estado, asignacion, overdue, recordatorio, nota
    estado_anterior = Column(String, nullable=True)
    estado_nuevo = Column(String, nullable=True)
    detalle = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=sqlfunc.now())
