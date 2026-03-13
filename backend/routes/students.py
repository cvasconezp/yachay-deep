"""
Endpoints de estudiantes — equivalente a la lógica de FichaEst.
Búsqueda por nombre/correo/cédula y vista de ficha completa.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from pydantic import BaseModel
from datetime import datetime

from ..database import get_db
from ..models import Student, AvacAccess, TaskSubmission, Grade, Intervention
from ..models.course import Course
from ..auth.jwt import get_current_user
from ..models.user import User

router = APIRouter(prefix="/students", tags=["students"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class StudentSummary(BaseModel):
    id: int
    cedula: Optional[str] = None
    nombre: Optional[str] = None
    correo_institucional: Optional[str] = None
    carrera: Optional[str] = None
    nivel_riesgo: Optional[str] = None
    indice_compromiso: Optional[float] = None
    dias_sin_acceso: Optional[int] = None
    porcentaje_tareas: Optional[float] = None

    class Config:
        from_attributes = True


class TaskSubmissionOut(BaseModel):
    codigo_curso: str
    nombre_curso: Optional[str] = None   # enriquecido desde Course.nombre
    unidad: Optional[str] = None
    estado: Optional[str] = None
    calificacion: Optional[float] = None
    calificacion_maxima: Optional[float] = None
    calificacion_final: Optional[float] = None
    entregada: bool = False
    calificada: bool = False
    retrasada: bool = False

    class Config:
        from_attributes = True


class AvacAccessOut(BaseModel):
    codigo_curso: str
    nombre_curso: Optional[str] = None   # enriquecido desde Course.nombre
    docente: Optional[str] = None         # enriquecido desde Course.docente
    grupo: Optional[str] = None           # enriquecido desde Course.grupo
    ultimo_acceso_texto: Optional[str] = None
    dias_sin_acceso: Optional[float] = None
    estado_avac: Optional[str] = None
    fecha_extraccion: Optional[datetime] = None

    class Config:
        from_attributes = True


class GradeOut(BaseModel):
    asignatura: str
    nota_final: Optional[float] = None
    docente: Optional[str] = None
    grupo: Optional[str] = None

    class Config:
        from_attributes = True


class InterventionOut(BaseModel):
    id: int
    monitor_nombre: Optional[str] = None
    medio: Optional[str] = None
    motivo: Optional[str] = None
    estado: Optional[str] = None
    asignatura: Optional[str] = None
    observacion: Optional[str] = None
    resultado: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FichaEstudiante(BaseModel):
    # Datos del estudiante
    id: int
    cedula: Optional[str] = None
    nombre: Optional[str] = None
    correo_institucional: Optional[str] = None
    correo: Optional[str] = None
    telefono: Optional[str] = None
    carrera: Optional[str] = None
    sede: Optional[str] = None
    estado_matricula: Optional[str] = None

    # Indicadores de riesgo
    nivel_riesgo: Optional[str] = None
    indice_compromiso: Optional[float] = None
    dias_sin_acceso: Optional[int] = None
    porcentaje_tareas: Optional[float] = None
    promedio_calificaciones: Optional[float] = None

    # Datos relacionados
    accesos_avac: list[AvacAccessOut] = []
    tareas: list[TaskSubmissionOut] = []
    calificaciones: list[GradeOut] = []
    intervenciones: list[InterventionOut] = []

    # Resumen
    total_intervenciones: int = 0
    ultima_intervencion: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/search", response_model=list[StudentSummary])
def search_students(
    q: str = Query(..., min_length=2, description="Nombre, correo institucional, cédula o teléfono"),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Búsqueda triple: nombre / correo / cédula.
    Replica el LET(resultado, UNIQUE(FILTER(...))) de FichaEst.
    """
    q_lower = q.lower().strip()
    results = (
        db.query(Student)
        .filter(
            or_(
                func.lower(Student.nombre).contains(q_lower),
                func.lower(Student.correo_institucional).contains(q_lower),
                Student.cedula == q.strip(),
                func.lower(Student.telefono).contains(q_lower),
            )
        )
        .limit(limit)
        .all()
    )
    return results


@router.get("/{student_id}/ficha", response_model=FichaEstudiante)
def get_ficha(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retorna la ficha completa del estudiante con todos sus datos.
    Equivalente a la FichaEst del Excel pero para todos los cursos.
    Enriquece accesos_avac y tareas con nombre_curso, docente y grupo
    desde la tabla courses (codigo_avac == codigo_curso).
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")

    accesos = (
        db.query(AvacAccess)
        .filter(AvacAccess.student_id == student_id)
        .order_by(AvacAccess.dias_sin_acceso)
        .all()
    )

    tareas = (
        db.query(TaskSubmission)
        .filter(TaskSubmission.student_id == student_id)
        .order_by(TaskSubmission.codigo_curso, TaskSubmission.unidad)
        .all()
    )

    calificaciones = (
        db.query(Grade)
        .filter(Grade.student_id == student_id)
        .order_by(Grade.asignatura)
        .all()
    )

    intervenciones = (
        db.query(Intervention)
        .filter(Intervention.student_id == student_id)
        .order_by(Intervention.created_at.desc())
        .all()
    )

    # ── Construir mapa codigo_avac → Course para enriquecer accesos y tareas ──
    all_codigos = set(
        [a.codigo_curso for a in accesos] + [t.codigo_curso for t in tareas]
    )
    course_map: dict[str, Course] = {}
    if all_codigos:
        courses = (
            db.query(Course)
            .filter(Course.codigo_avac.in_(all_codigos))
            .all()
        )
        course_map = {c.codigo_avac: c for c in courses}

    # Serializar accesos enriquecidos
    accesos_out = [
        AvacAccessOut(
            codigo_curso=a.codigo_curso,
            nombre_curso=course_map[a.codigo_curso].nombre if a.codigo_curso in course_map else None,
            docente=course_map[a.codigo_curso].docente if a.codigo_curso in course_map else None,
            grupo=course_map[a.codigo_curso].grupo if a.codigo_curso in course_map else None,
            ultimo_acceso_texto=a.ultimo_acceso_texto,
            dias_sin_acceso=a.dias_sin_acceso,
            estado_avac=a.estado_avac,
            fecha_extraccion=a.fecha_extraccion,
        )
        for a in accesos
    ]

    # Serializar tareas enriquecidas
    tareas_out = [
        TaskSubmissionOut(
            codigo_curso=t.codigo_curso,
            nombre_curso=course_map[t.codigo_curso].nombre if t.codigo_curso in course_map else None,
            unidad=t.unidad,
            estado=t.estado,
            calificacion=t.calificacion,
            calificacion_maxima=t.calificacion_maxima,
            calificacion_final=t.calificacion_final,
            entregada=t.entregada or False,
            calificada=t.calificada or False,
            retrasada=t.retrasada or False,
        )
        for t in tareas
    ]

    ultima_intervencion = intervenciones[0].created_at if intervenciones else None

    return FichaEstudiante(
        id=student.id,
        cedula=student.cedula,
        nombre=student.nombre,
        correo_institucional=student.correo_institucional,
        correo=student.correo,
        telefono=student.telefono,
        carrera=student.carrera,
        sede=student.sede,
        estado_matricula=student.estado_matricula,
        nivel_riesgo=student.nivel_riesgo,
        indice_compromiso=student.indice_compromiso,
        dias_sin_acceso=student.dias_sin_acceso,
        porcentaje_tareas=student.porcentaje_tareas,
        promedio_calificaciones=student.promedio_calificaciones,
        accesos_avac=accesos_out,
        tareas=tareas_out,
        calificaciones=calificaciones,
        intervenciones=intervenciones,
        total_intervenciones=len(intervenciones),
        ultima_intervencion=ultima_intervencion,
    )
