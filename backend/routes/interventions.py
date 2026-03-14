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
    derivar_bienestar: Optional[bool] = False
    tipo_evento_critico: Optional[str] = None
    reporte_bienestar: Optional[str] = None


class InterventionUpdate(BaseModel):
    medio: Optional[str] = None
    motivo: Optional[str] = None
    estado: Optional[str] = None
    asignatura: Optional[str] = None
    docente: Optional[str] = None
    observacion: Optional[str] = None
    resultado: Optional[str] = None
    requiere_seguimiento: Optional[str] = None
    derivar_bienestar: Optional[bool] = None
    tipo_evento_critico: Optional[str] = None
    reporte_bienestar: Optional[str] = None


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
    derivar_bienestar: Optional[bool]
    tipo_evento_critico: Optional[str]
    reporte_bienestar: Optional[str]
    email_enviado: Optional[bool]
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
        derivar_bienestar=payload.derivar_bienestar,
        tipo_evento_critico=payload.tipo_evento_critico,
        reporte_bienestar=payload.reporte_bienestar,
    )
    db.add(intervention)
    db.commit()
    db.refresh(intervention)

    # Enviar correo a Bienestar Estudiantil si se solicitó derivación
    if payload.derivar_bienestar:
        from ..services.email import send_bienestar_report

        student_data = {
            "nombre": student.nombre,
            "cedula": student.cedula,
            "correo": student.correo,
            "correo_institucional": student.correo_institucional,
            "telefono": student.telefono,
            "whatsapp": getattr(student, "whatsapp", None),
            "carrera": student.carrera,
            "sede": student.sede,
        }
        intervention_data = {
            "tipo_evento_critico": payload.tipo_evento_critico,
            "reporte_bienestar": payload.reporte_bienestar,
            "motivo": payload.motivo,
            "observacion": payload.observacion,
        }
        email_ok = send_bienestar_report(student_data, intervention_data, current_user.nombre)
        intervention.email_enviado = email_ok
        db.commit()
        db.refresh(intervention)

    return intervention


@router.patch("/{intervention_id}", response_model=InterventionResponse)
def update_intervention(
    intervention_id: int,
    payload: InterventionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Actualiza una intervención existente (estado, resultado, observación, etc.)."""
    intervention = db.query(Intervention).filter(Intervention.id == intervention_id).first()
    if not intervention:
        raise HTTPException(status_code=404, detail="Intervención no encontrada")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(intervention, field, value)

    db.commit()
    db.refresh(intervention)

    # Si se activa derivación a bienestar y aún no se envió correo
    if intervention.derivar_bienestar and not intervention.email_enviado:
        from ..services.email import send_bienestar_report

        student = db.query(Student).filter(Student.id == intervention.student_id).first()
        if student:
            student_data = {
                "nombre": student.nombre,
                "cedula": student.cedula,
                "correo": student.correo,
                "correo_institucional": student.correo_institucional,
                "telefono": student.telefono,
                "whatsapp": getattr(student, "whatsapp", None),
                "carrera": student.carrera,
                "sede": student.sede,
            }
            intervention_data = {
                "tipo_evento_critico": intervention.tipo_evento_critico,
                "reporte_bienestar": intervention.reporte_bienestar,
                "motivo": intervention.motivo,
                "observacion": intervention.observacion,
            }
            email_ok = send_bienestar_report(student_data, intervention_data, current_user.nombre)
            intervention.email_enviado = email_ok
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


@router.get("/dashboard")
def interventions_dashboard(
    carrera: Optional[str] = None,
    motivo: Optional[str] = None,
    estado: Optional[str] = None,
    resultado: Optional[str] = None,
    seguimiento: Optional[str] = None,
    limit: int = 500,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Dashboard de intervenciones: lista completa con datos del estudiante,
    tarjetas resumen por carrera, y filtros avanzados.
    """
    from sqlalchemy import func, distinct

    # --- Query principal: intervenciones + datos de estudiante ---
    query = (
        db.query(Intervention, Student.nombre, Student.carrera, Student.nivel_riesgo)
        .join(Student, Intervention.student_id == Student.id)
    )
    if carrera:
        query = query.filter(Student.carrera == carrera)
    if motivo:
        query = query.filter(Intervention.motivo == motivo)
    if estado:
        query = query.filter(Intervention.estado == estado)
    if resultado:
        query = query.filter(Intervention.resultado == resultado)
    if seguimiento:
        query = query.filter(Intervention.requiere_seguimiento == seguimiento)

    rows = query.order_by(Intervention.created_at.desc()).limit(limit).all()

    items = []
    for inv, nombre, car, riesgo in rows:
        items.append({
            "id": inv.id,
            "student_id": inv.student_id,
            "nombre": nombre,
            "carrera": car or inv.carrera,
            "nivel_riesgo": riesgo,
            "medio": inv.medio,
            "motivo": inv.motivo,
            "estado": inv.estado,
            "asignatura": inv.asignatura,
            "resultado": inv.resultado,
            "requiere_seguimiento": inv.requiere_seguimiento,
            "observacion": inv.observacion,
            "derivar_bienestar": inv.derivar_bienestar,
            "tipo_evento_critico": inv.tipo_evento_critico,
            "email_enviado": inv.email_enviado,
            "monitor_nombre": inv.monitor_nombre,
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
        })

    # --- Resumen ---
    total = db.query(func.count(Intervention.id)).scalar() or 0
    estudiantes_intervenidos = (
        db.query(func.count(distinct(Intervention.student_id))).scalar() or 0
    )
    pendientes_seguimiento = (
        db.query(func.count(Intervention.id))
        .filter(Intervention.requiere_seguimiento == "si")
        .scalar() or 0
    )

    # Por carrera
    por_carrera = (
        db.query(
            Student.carrera,
            func.count(distinct(Intervention.student_id)).label("estudiantes"),
            func.count(Intervention.id).label("intervenciones"),
        )
        .join(Student, Intervention.student_id == Student.id)
        .group_by(Student.carrera)
        .all()
    )

    return {
        "items": items,
        "resumen": {
            "total_intervenciones": total,
            "estudiantes_intervenidos": estudiantes_intervenidos,
            "pendientes_seguimiento": pendientes_seguimiento,
            "por_carrera": [
                {"carrera": r.carrera or "Sin carrera", "estudiantes": r.estudiantes, "intervenciones": r.intervenciones}
                for r in por_carrera
            ],
        },
    }
