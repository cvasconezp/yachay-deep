"""
Endpoints de intervenciones — equivalente a GuardarMonitoreoEnReporte() del VBA.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

from ..database import get_db
from ..models import Intervention, Student, Grade
from ..models.enrollment import Enrollment
from ..models.user import User
from ..auth.jwt import get_current_user

router = APIRouter(prefix="/interventions", tags=["interventions"])


def _strip_str(v):
    """Sanitiza campos de texto: strip whitespace."""
    if isinstance(v, str):
        return v.strip()
    return v


class InterventionCreate(BaseModel):
    student_id: int
    medio: str = Field(..., max_length=100)
    motivo: str = Field(..., max_length=200)
    estado: str = Field(..., max_length=100)
    asignatura: Optional[str] = Field(None, max_length=200)
    docente: Optional[str] = Field(None, max_length=200)
    observacion: Optional[str] = Field(None, max_length=2000)
    resultado: Optional[str] = Field(None, max_length=200)
    requiere_seguimiento: Optional[str] = Field(None, max_length=10)
    derivar_bienestar: Optional[bool] = False
    derivar_financiero: Optional[bool] = False
    derivar_coordinacion: Optional[bool] = False
    derivar_docente: Optional[bool] = False
    tipo_evento_critico: Optional[str] = Field(None, max_length=200)
    reporte_bienestar: Optional[str] = Field(None, max_length=5000)
    reporte_derivacion: Optional[str] = Field(None, max_length=5000)
    periodo: Optional[str] = Field(None, max_length=20)

    @field_validator("medio", "motivo", "estado", "asignatura", "docente",
                     "observacion", "resultado", "tipo_evento_critico", "reporte_bienestar",
                     "reporte_derivacion", mode="before")
    @classmethod
    def strip_whitespace(cls, v):
        return _strip_str(v)


class BulkInterventionCreate(BaseModel):
    student_ids: list[int]
    medio: str = Field(..., max_length=100)
    motivo: str = Field(..., max_length=200)
    estado: str = Field(..., max_length=100)
    asignatura: Optional[str] = Field(None, max_length=200)
    docente: Optional[str] = Field(None, max_length=200)
    observacion: Optional[str] = Field(None, max_length=2000)
    resultado: Optional[str] = Field(None, max_length=200)
    requiere_seguimiento: Optional[str] = Field(None, max_length=10)
    derivar_bienestar: Optional[bool] = False
    derivar_financiero: Optional[bool] = False
    derivar_coordinacion: Optional[bool] = False
    derivar_docente: Optional[bool] = False
    tipo_evento_critico: Optional[str] = Field(None, max_length=200)
    reporte_bienestar: Optional[str] = Field(None, max_length=5000)
    reporte_derivacion: Optional[str] = Field(None, max_length=5000)
    periodo: Optional[str] = Field(None, max_length=20)

    @field_validator("medio", "motivo", "estado", "asignatura", "docente",
                     "observacion", "resultado", "tipo_evento_critico", "reporte_bienestar",
                     "reporte_derivacion", mode="before")
    @classmethod
    def strip_whitespace(cls, v):
        return _strip_str(v)


class InterventionUpdate(BaseModel):
    medio: Optional[str] = Field(None, max_length=100)
    motivo: Optional[str] = Field(None, max_length=200)
    estado: Optional[str] = Field(None, max_length=100)
    asignatura: Optional[str] = Field(None, max_length=200)
    docente: Optional[str] = Field(None, max_length=200)
    observacion: Optional[str] = Field(None, max_length=2000)
    resultado: Optional[str] = Field(None, max_length=200)
    requiere_seguimiento: Optional[str] = Field(None, max_length=10)
    nota_cierre: Optional[str] = Field(None, max_length=2000)
    derivar_bienestar: Optional[bool] = None
    derivar_financiero: Optional[bool] = None
    derivar_coordinacion: Optional[bool] = None
    derivar_docente: Optional[bool] = None
    tipo_evento_critico: Optional[str] = Field(None, max_length=200)
    reporte_bienestar: Optional[str] = Field(None, max_length=5000)
    reporte_derivacion: Optional[str] = Field(None, max_length=5000)
    periodo: Optional[str] = Field(None, max_length=20)

    @field_validator("medio", "motivo", "estado", "asignatura", "docente",
                     "observacion", "resultado", "tipo_evento_critico", "reporte_bienestar",
                     "reporte_derivacion", "nota_cierre", mode="before")
    @classmethod
    def strip_whitespace(cls, v):
        return _strip_str(v)


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
    nota_cierre: Optional[str]
    derivar_bienestar: Optional[bool]
    derivar_financiero: Optional[bool]
    derivar_coordinacion: Optional[bool]
    derivar_docente: Optional[bool]
    tipo_evento_critico: Optional[str]
    reporte_bienestar: Optional[str]
    reporte_derivacion: Optional[str]
    email_enviado: Optional[bool]
    periodo: Optional[str]
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

    # Auto-poblar periodo desde SemesterConfig si no se envía
    _periodo = payload.periodo
    if not _periodo:
        from ..models.course_config import SemesterConfig
        semconfig = db.query(SemesterConfig).order_by(SemesterConfig.id.desc()).first()
        if semconfig:
            _periodo = semconfig.semestre

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
        derivar_financiero=payload.derivar_financiero,
        derivar_coordinacion=payload.derivar_coordinacion,
        derivar_docente=payload.derivar_docente,
        tipo_evento_critico=payload.tipo_evento_critico,
        reporte_bienestar=payload.reporte_bienestar,
        reporte_derivacion=payload.reporte_derivacion,
        periodo=_periodo,
        # [GAP-F5-01] Snapshot de indicadores al momento de la intervención
        snapshot_compromiso=student.indice_compromiso,
        snapshot_dias_sin_acceso=student.dias_sin_acceso,
        snapshot_porcentaje_tareas=student.porcentaje_tareas,
        snapshot_prob_desercion=student.prob_desercion,
        snapshot_prob_reprobacion=student.prob_reprobacion,
        snapshot_nivel_riesgo=student.nivel_riesgo,
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


@router.post("/bulk")
def bulk_create_interventions(
    payload: BulkInterventionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Crea la misma intervención para múltiples estudiantes a la vez.
    Retorna el conteo de creadas y una lista de errores (si los hay).
    """
    # Auto-poblar periodo desde SemesterConfig si no se envía
    _periodo = payload.periodo
    if not _periodo:
        from ..models.course_config import SemesterConfig
        semconfig = db.query(SemesterConfig).order_by(SemesterConfig.id.desc()).first()
        if semconfig:
            _periodo = semconfig.semestre

    created = 0
    errors = []

    for student_id in payload.student_ids:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            errors.append({"student_id": student_id, "detail": "Estudiante no encontrado"})
            continue

        try:
            intervention = Intervention(
                student_id=student_id,
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
                derivar_financiero=payload.derivar_financiero,
                derivar_coordinacion=payload.derivar_coordinacion,
                derivar_docente=payload.derivar_docente,
                tipo_evento_critico=payload.tipo_evento_critico,
                reporte_bienestar=payload.reporte_bienestar,
                reporte_derivacion=payload.reporte_derivacion,
                periodo=_periodo,
                snapshot_compromiso=student.indice_compromiso,
                snapshot_dias_sin_acceso=student.dias_sin_acceso,
                snapshot_porcentaje_tareas=student.porcentaje_tareas,
                snapshot_prob_desercion=student.prob_desercion,
                snapshot_prob_reprobacion=student.prob_reprobacion,
                snapshot_nivel_riesgo=student.nivel_riesgo,
            )
            db.add(intervention)
            db.flush()

            # Enviar correo a Bienestar si se solicitó derivación
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

            created += 1
        except Exception as e:
            errors.append({"student_id": student_id, "detail": str(e)})

    db.commit()
    return {"created": created, "errors": errors}


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

    # Solo el monitor que creó la intervención o un admin pueden editarla
    if intervention.monitor_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo puedes editar tus propias intervenciones")

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


@router.delete("/{intervention_id}")
def delete_intervention(
    intervention_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Elimina una intervención creada por error."""
    intervention = db.query(Intervention).filter(Intervention.id == intervention_id).first()
    if not intervention:
        raise HTTPException(status_code=404, detail="Intervención no encontrada")

    # Solo el monitor creador o un admin pueden eliminar
    if intervention.monitor_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo puedes eliminar tus propias intervenciones")

    db.delete(intervention)
    db.commit()
    return {"message": "Intervención eliminada", "id": intervention_id}


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
    periodo: Optional[str] = None,
    limit: int = 500,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Dashboard de intervenciones: lista completa con datos del estudiante,
    tarjetas resumen por carrera, y filtros avanzados.
    """
    from sqlalchemy import func, distinct

    # --- Filtro por período: estudiantes del período (Grades OR Enrollments OR Interventions) ---
    from sqlalchemy import or_, union
    pf = periodo if periodo else "actual"

    # Students with grades in the period
    grade_sq = db.query(Grade.student_id).distinct()
    # Students with enrollments in the period
    enroll_sq = db.query(Enrollment.student_id).distinct()
    # Students with interventions in the period (even if not enrolled/graded)
    interv_sq = db.query(Intervention.student_id).distinct()

    if pf == "actual":
        grade_sq = grade_sq.filter(Grade.periodo.is_(None))
        enroll_sq = enroll_sq.filter(Enrollment.periodo.is_(None))
        interv_sq = interv_sq.filter(Intervention.periodo.is_(None))
    elif pf != "todos":
        if pf.startswith("P"):
            grade_sq = grade_sq.filter(or_(Grade.periodo == pf, Grade.periodo == pf[1:]))
            enroll_sq = enroll_sq.filter(or_(Enrollment.periodo == pf, Enrollment.periodo == pf[1:]))
            interv_sq = interv_sq.filter(or_(Intervention.periodo == pf, Intervention.periodo == pf[1:]))
        else:
            grade_sq = grade_sq.filter(or_(Grade.periodo == pf, Grade.periodo == f"P{pf}"))
            enroll_sq = enroll_sq.filter(or_(Enrollment.periodo == pf, Enrollment.periodo == f"P{pf}"))
            interv_sq = interv_sq.filter(or_(Intervention.periodo == pf, Intervention.periodo == f"P{pf}"))

    # Combine: students from grades OR enrollments OR interventions
    period_sq = grade_sq.union(enroll_sq).union(interv_sq)

    # --- Query principal: intervenciones + datos de estudiante ---
    query = (
        db.query(Intervention, Student.nombre, Student.carrera, Student.nivel_riesgo)
        .join(Student, Intervention.student_id == Student.id)
        .filter(Intervention.student_id.in_(period_sq))
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
            "nota_cierre": inv.nota_cierre,
            "derivar_bienestar": inv.derivar_bienestar,
            "derivar_financiero": inv.derivar_financiero,
            "derivar_coordinacion": inv.derivar_coordinacion,
            "derivar_docente": inv.derivar_docente,
            "tipo_evento_critico": inv.tipo_evento_critico,
            "email_enviado": inv.email_enviado,
            "monitor_nombre": inv.monitor_nombre,
            "periodo": inv.periodo,
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
        })

    # --- Resumen (filtrado por período) ---
    base_resumen = db.query(Intervention).filter(Intervention.student_id.in_(period_sq))
    total = base_resumen.count()
    estudiantes_intervenidos = (
        db.query(func.count(distinct(Intervention.student_id)))
        .filter(Intervention.student_id.in_(period_sq))
        .scalar() or 0
    )
    pendientes_seguimiento = (
        base_resumen
        .filter(Intervention.requiere_seguimiento == "si")
        .count()
    )

    # Por carrera
    por_carrera = (
        db.query(
            Student.carrera,
            func.count(distinct(Intervention.student_id)).label("estudiantes"),
            func.count(Intervention.id).label("intervenciones"),
        )
        .join(Student, Intervention.student_id == Student.id)
        .filter(Intervention.student_id.in_(period_sq))
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


@router.get("/{intervention_id}/impact")
def get_intervention_impact(
    intervention_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    [GAP-F5-01] Mide el impacto de una intervención:
    compara los indicadores snapshot (al crear) vs los actuales del estudiante.
    Esto cierra el ciclo: detección → intervención → evaluación de impacto.
    """
    intervention = db.query(Intervention).filter(Intervention.id == intervention_id).first()
    if not intervention:
        raise HTTPException(status_code=404, detail="Intervención no encontrada")

    student = db.query(Student).filter(Student.id == intervention.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")

    # Si no hay snapshot, la intervención fue creada antes de esta feature
    if intervention.snapshot_compromiso is None and intervention.snapshot_dias_sin_acceso is None:
        return {
            "intervention_id": intervention_id,
            "student_id": student.id,
            "mensaje": "Sin datos de snapshot — intervención creada antes de esta funcionalidad",
            "disponible": False,
        }

    def _delta(antes, ahora):
        if antes is None or ahora is None:
            return None
        return round(ahora - antes, 4)

    antes = {
        "compromiso": intervention.snapshot_compromiso,
        "dias_sin_acceso": intervention.snapshot_dias_sin_acceso,
        "porcentaje_tareas": intervention.snapshot_porcentaje_tareas,
        "prob_desercion": intervention.snapshot_prob_desercion,
        "prob_reprobacion": intervention.snapshot_prob_reprobacion,
        "nivel_riesgo": intervention.snapshot_nivel_riesgo,
    }
    ahora = {
        "compromiso": student.indice_compromiso,
        "dias_sin_acceso": student.dias_sin_acceso,
        "porcentaje_tareas": student.porcentaje_tareas,
        "prob_desercion": student.prob_desercion,
        "prob_reprobacion": student.prob_reprobacion,
        "nivel_riesgo": student.nivel_riesgo,
    }
    cambio = {
        "compromiso": _delta(antes["compromiso"], ahora["compromiso"]),
        "dias_sin_acceso": _delta(antes["dias_sin_acceso"], ahora["dias_sin_acceso"]),
        "porcentaje_tareas": _delta(antes["porcentaje_tareas"], ahora["porcentaje_tareas"]),
        "prob_desercion": _delta(antes["prob_desercion"], ahora["prob_desercion"]),
        "prob_reprobacion": _delta(antes["prob_reprobacion"], ahora["prob_reprobacion"]),
    }

    # Determinar si hubo mejora general
    mejoras = 0
    total_evaluados = 0
    if cambio["compromiso"] is not None:
        total_evaluados += 1
        if cambio["compromiso"] > 0:
            mejoras += 1
    if cambio["dias_sin_acceso"] is not None:
        total_evaluados += 1
        if cambio["dias_sin_acceso"] < 0:  # menos días sin acceso = mejora
            mejoras += 1
    if cambio["porcentaje_tareas"] is not None:
        total_evaluados += 1
        if cambio["porcentaje_tareas"] > 0:
            mejoras += 1
    if cambio["prob_desercion"] is not None:
        total_evaluados += 1
        if cambio["prob_desercion"] < 0:  # menor prob = mejora
            mejoras += 1

    mejoro = mejoras > (total_evaluados / 2) if total_evaluados > 0 else None

    return {
        "intervention_id": intervention_id,
        "student_id": student.id,
        "nombre": student.nombre,
        "fecha_intervencion": intervention.created_at.isoformat() if intervention.created_at else None,
        "antes": antes,
        "ahora": ahora,
        "cambio": cambio,
        "mejoro": mejoro,
        "indicadores_mejorados": mejoras,
        "indicadores_evaluados": total_evaluados,
        "disponible": True,
    }
