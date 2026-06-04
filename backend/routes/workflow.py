"""
Endpoints de Workflow de Intervenciones — Fase 3

Gestiona transiciones de estado, asignaciones, SLAs y auditoría.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime

from ..database import get_db
from ..models.intervention import Intervention
from ..models.user import User
from ..auth.jwt import get_current_user
from ..services.intervention_workflow import (
    VALID_STATES, TRANSITIONS, SLA_HOURS,
    transition_intervention,
    asignar_intervencion,
    autoasignar_round_robin,
    get_carga_monitores,
    detectar_overdue,
    generar_recordatorios,
    InterventionLog,
)

router = APIRouter(prefix="/workflow", tags=["workflow"])


# ── Schemas ────────────────────────────────────────────────────────

class TransitionRequest(BaseModel):
    estado: str = Field(..., description="Nuevo estado del workflow")
    nota: Optional[str] = Field(None, max_length=2000)
    escalado_a: Optional[str] = Field(None, max_length=200)

class AsignacionRequest(BaseModel):
    asignado_a: int
    asignado_nombre: str
    prioridad: int = Field(2, ge=1, le=3)

class AutoAsignarRequest(BaseModel):
    intervention_ids: list[int]

class CargaMonitorResponse(BaseModel):
    user_id: int
    nombre: Optional[str]
    total_activas: int
    pendientes: int

class LogEntry(BaseModel):
    id: int
    intervention_id: int
    user_id: Optional[int]
    user_nombre: Optional[str]
    accion: str
    estado_anterior: Optional[str]
    estado_nuevo: Optional[str]
    detalle: Optional[str]
    created_at: Optional[str]

    class Config:
        from_attributes = True


# ── Endpoints ──────────────────────────────────────────────────────

@router.get("/states")
def get_states():
    """Retorna la máquina de estados con transiciones válidas."""
    return {
        "estados": sorted(VALID_STATES),
        "transiciones": {k: sorted(v) for k, v in TRANSITIONS.items()},
        "sla_horas": SLA_HOURS,
    }


@router.patch("/interventions/{intervention_id}/transition")
def do_transition(
    intervention_id: int,
    body: TransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ejecuta una transición de estado en una intervención."""
    result = transition_intervention(
        db, intervention_id, body.estado,
        user_id=current_user.id,
        user_nombre=current_user.nombre,
        nota=body.nota,
        escalado_a=body.escalado_a,
    )
    if "error" in result:
        raise HTTPException(status_code=result.get("status", 400), detail=result["error"])
    return result


@router.post("/interventions/{intervention_id}/assign")
def do_assign(
    intervention_id: int,
    body: AsignacionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Asigna una intervención a un monitor."""
    result = asignar_intervencion(
        db, intervention_id, body.asignado_a, body.asignado_nombre,
        prioridad=body.prioridad,
        user_id=current_user.id,
        user_nombre=current_user.nombre,
    )
    if "error" in result:
        raise HTTPException(status_code=result.get("status", 400), detail=result["error"])
    return result


@router.post("/auto-assign")
def do_auto_assign(
    body: AutoAsignarRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Autoasigna intervenciones distribuyendo equitativamente entre monitores."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo admin puede autoasignar")
    result = autoasignar_round_robin(db, body.intervention_ids, current_user.id, current_user.nombre)
    return result


@router.get("/carga", response_model=list[CargaMonitorResponse])
def get_carga(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna distribución de carga de intervenciones por monitor."""
    return get_carga_monitores(db)


@router.post("/check-sla")
def check_sla(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Detecta intervenciones con SLA vencido y las marca como overdue."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo admin puede verificar SLAs")
    overdue = detectar_overdue(db)
    recordatorios = generar_recordatorios(db)
    return {**overdue, "recordatorios_proximos": len(recordatorios), "detalle_recordatorios": recordatorios}


@router.get("/interventions/{intervention_id}/logs", response_model=list[LogEntry])
def get_logs(
    intervention_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna el historial de auditoría de una intervención."""
    logs = db.query(InterventionLog).filter(
        InterventionLog.intervention_id == intervention_id
    ).order_by(InterventionLog.created_at.desc()).all()

    return [
        LogEntry(
            id=l.id,
            intervention_id=l.intervention_id,
            user_id=l.user_id,
            user_nombre=l.user_nombre,
            accion=l.accion,
            estado_anterior=l.estado_anterior,
            estado_nuevo=l.estado_nuevo,
            detalle=l.detalle,
            created_at=l.created_at.isoformat() if l.created_at else None,
        )
        for l in logs
    ]


@router.get("/overdue")
def get_overdue_interventions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista intervenciones con SLA vencido."""
    overdues = db.query(Intervention).filter(
        Intervention.overdue == True,
        Intervention.estado_workflow.notin_(["resuelto", "cerrado"]),
    ).order_by(Intervention.fecha_limite).all()

    return [{
        "id": inv.id,
        "student_id": inv.student_id,
        "estado_workflow": inv.estado_workflow,
        "asignado_nombre": inv.asignado_nombre,
        "prioridad": inv.prioridad,
        "fecha_limite": inv.fecha_limite.isoformat() if inv.fecha_limite else None,
        "motivo": inv.motivo,
    } for inv in overdues]
