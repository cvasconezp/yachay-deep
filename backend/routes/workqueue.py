"""
Bandeja de Trabajo Diaria — endpoint /workqueue para monitores.

[Épica 2.3] Bandeja de Trabajo Diaria

Retorna una lista priorizada de acciones pendientes para el monitor:
1. Alertas críticas sin atender
2. Alertas altas sin atender
3. Estudiantes con deterioro progresivo
4. Intervenciones pendientes de seguimiento

Cada ítem incluye: tipo, prioridad, estudiante, acción sugerida, datos contextuales.
"""
from typing import Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, case
from pydantic import BaseModel

from ..database import get_db
from ..models import Student
from ..models.alert_event import AlertEvent
from ..models.course_config import SemesterConfig, CourseConfig
from ..auth.jwt import get_current_user
from ..models.user import User

router = APIRouter(prefix="/workqueue", tags=["workqueue"])


class WorkItem(BaseModel):
    """Ítem individual en la bandeja de trabajo."""
    id: int
    tipo: str                          # "alerta_critica", "alerta_alta", "deterioro", "seguimiento"
    prioridad: int                     # 1=máxima, 2=alta, 3=media
    student_id: int
    student_nombre: Optional[str] = None
    student_carrera: Optional[str] = None
    alert_tipo: Optional[str] = None   # tipo original de alerta
    mensaje: str
    accion_sugerida: str
    codigo_curso: Optional[str] = None
    asignatura: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class WorkQueueResponse(BaseModel):
    """Respuesta completa de la bandeja de trabajo."""
    items: list[WorkItem]
    total: int
    por_prioridad: dict                # {1: N, 2: N, 3: N}
    resumen: str                       # "12 acciones pendientes (3 urgentes)"
    timestamp: str


# ── Mapeo de acciones sugeridas por tipo de alerta ──
ACCIONES_SUGERIDAS = {
    "inactividad": "Contactar al estudiante por email/WhatsApp para verificar situación",
    "compromiso_bajo": "Agendar tutoría sincrónica con el docente de la materia",
    "nota_cero": "Verificar si el estudiante entregó la actividad; contactar docente",
    "tareas_bajas": "Enviar recordatorio de tareas pendientes y ofrecer apoyo",
    "segunda_matricula": "Programar sesión de acompañamiento académico personalizado",
    "tercera_matricula": "Derivar a Bienestar Estudiantil — seguimiento prioritario",
    "deterioro_progresivo": "Intervención inmediata: contactar estudiante + docente + coordinador",
}


@router.get("", response_model=WorkQueueResponse)
def get_workqueue(
    limit: int = Query(50, le=200),
    carrera: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retorna la bandeja de trabajo priorizada del monitor.
    Ordena por: severidad (critico > alto > medio), luego por fecha.
    """
    # Base query: alertas no leídas con datos del estudiante
    q = (
        db.query(AlertEvent, Student.nombre, Student.carrera)
        .outerjoin(Student, AlertEvent.student_id == Student.id)
        .filter(AlertEvent.leido == False)
    )

    # Filtro por carrera
    if carrera:
        q = q.filter(func.lower(Student.carrera).contains(carrera.lower()))

    # Ordenar por severidad y fecha
    severity_order = case(
        (AlertEvent.severidad == "critico", 1),
        (AlertEvent.severidad == "alto", 2),
        else_=3,
    )
    q = q.order_by(severity_order, AlertEvent.created_at.desc())

    rows = q.limit(limit).all()

    # Pre-load asignatura names
    curso_codes = {alert.codigo_curso for alert, _, _ in rows if alert.codigo_curso}
    asignatura_map = {}
    if curso_codes:
        for cc in db.query(CourseConfig).filter(CourseConfig.codigo_avac.in_(curso_codes)).all():
            asignatura_map[cc.codigo_avac] = cc.asignatura

    # Build work items
    items = []
    for alert, nombre, student_carrera in rows:
        # Determinar prioridad
        if alert.severidad == "critico":
            prioridad = 1
            tipo = "alerta_critica"
        elif alert.severidad == "alto":
            prioridad = 2
            tipo = "alerta_alta"
        else:
            prioridad = 3
            tipo = "alerta_media"

        # Override para deterioro progresivo (siempre prioridad alta)
        if alert.tipo == "deterioro_progresivo":
            tipo = "deterioro"
            prioridad = min(prioridad, 1)  # Siempre urgente

        accion = ACCIONES_SUGERIDAS.get(alert.tipo, "Revisar situación del estudiante")

        items.append(WorkItem(
            id=alert.id,
            tipo=tipo,
            prioridad=prioridad,
            student_id=alert.student_id,
            student_nombre=nombre,
            student_carrera=student_carrera,
            alert_tipo=alert.tipo,
            mensaje=alert.mensaje or "",
            accion_sugerida=accion,
            codigo_curso=alert.codigo_curso,
            asignatura=asignatura_map.get(alert.codigo_curso) if alert.codigo_curso else None,
            created_at=alert.created_at.isoformat() if alert.created_at else None,
        ))

    # Conteo por prioridad
    por_prioridad = {1: 0, 2: 0, 3: 0}
    for item in items:
        por_prioridad[item.prioridad] = por_prioridad.get(item.prioridad, 0) + 1

    total = len(items)
    urgentes = por_prioridad.get(1, 0)
    resumen = f"{total} acciones pendientes"
    if urgentes:
        resumen += f" ({urgentes} urgentes)"

    return WorkQueueResponse(
        items=items,
        total=total,
        por_prioridad=por_prioridad,
        resumen=resumen,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
