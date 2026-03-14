"""
Endpoints de intervenciones — equivalente a GuardarMonitoreoEnReporte() del VBA.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from ..database import get_db
from ..models import Intervention, Student
from ..models.user import User
from ..auth.jwt import get_current_user

router = APIRouter(prefix="/interventions", tags=["interventions"])


class InterventionCreate(BaseModel):
    student_id: int
    medio: str              # WhatsApp / Llamada / Email / Presencial
    motivo: str             # Bajo rendimiento / Inactividad AVAC / No entrega tareas / etc
    estado: str             # Activo / SNA / Retirado / Recuperado
    asignatura: Optional[str] = None
    docente: Optional[str] = None
    observacion: Optional[str] = None
    resultado: Optional[str] = None       # Contactado / No contestó / Buzón de voz
    requiere_seguimiento: Optional[str] = None  # "si" / "no"


class InterventionResponse(BaseModel):
    id: int
    student_id: int
    monitor_nombre: Optional[str]
    medio: Optional[str]
    motivo: Optional[str]
    estado: Optional[str]
    asignatura: Optional[str]
    observacion: Optional[str]
    resultado: Optional[str]
    requiere_seguimiento: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


@router.post("/", response_model=InterventionResponse)
def create_intervention(
    payload: InterventionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Registra una intervención de seguimiento.
    Equivalente a GuardarMonitoreoEnReporte() — pero ahora en BD real.
    """
    student = db.query(Student).filter(Student.id == payload.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")

    intervention = Intervention(
        student_id=payload.student_id,
        monitor_id=current_user.id,
        monitor_nombre=current_user.nombre,
        carrera=student.carrera,
        medio=payload.medio,
        motivo=payload.motivo,
        estado=payload.estado,
        asignatura=payload.asignatura,
        docente=payload.docente,
        observacion=payload.observacion,
        resultado=payload.resultado,
        requiere_seguimiento=payload.requiere_seguimiento,
    )
    db.add(intervention)
    db.commit()
    db.refresh(intervention)
    return intervention


@router.get("/", response_model=list[InterventionResponse])
def list_interventions(
    student_id: Optional[int] = None,
    monitor_id: Optional[int] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Intervention)
    if student_id:
        query = query.filter(Intervention.student_id == student_id)
    if monitor_id:
        query = query.filter(Intervention.monitor_id == monitor_id)
    return query.order_by(Intervention.created_at.desc()).limit(limit).all()


@router.get("/stats")
def intervention_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Estadísticas de intervenciones: conteos por medio, motivo y resultado.
    Esto es NUEVO — el Excel no podía analizar su propio log.
    """
    from sqlalchemy import func

    by_medio = (
        db.query(Intervention.medio, func.count(Intervention.id).label("total"))
        .group_by(Intervention.medio)
        .all()
    )
    by_motivo = (
        db.query(Intervention.motivo, func.count(Intervention.id).label("total"))
        .group_by(Intervention.motivo)
        .all()
    )
    by_resultado = (
        db.query(Intervention.resultado, func.count(Intervention.id).label("total"))
        .group_by(Intervention.resultado)
        .all()
    )
    by_estado_cambio = (
        db.query(Intervention.estado, func.count(Intervention.id).label("total"))
        .group_by(Intervention.estado)
        .all()
    )

    return {
        "por_medio": [{"medio": r.medio, "total": r.total} for r in by_medio],
        "por_motivo": [{"motivo": r.motivo, "total": r.total} for r in by_motivo],
        "por_resultado": [{"resultado": r.resultado, "total": r.total} for r in by_resultado],
        "por_estado": [{"estado": r.estado, "total": r.total} for r in by_estado_cambio],
    }
