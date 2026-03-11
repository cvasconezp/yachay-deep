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
from ..auth.jwt import get_current_user
from ..models.user import User

router = APIRouter(prefix="/students", tags=["students"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class StudentSummary(BaseModel):
    id: int
    cedula: Optional[str]
    nombre: str
    correo_institucional: Optional[str]
    carrera: Optional[str]
    nivel_riesgo: Optional[str]
    indice_compromiso: Optional[float]
    dias_sin_acceso: Optional[int]
    porcentaje_tareas: Optional[float]

    class Config:
        from_attributes = True


class TaskSubmissionOut(BaseModel):
    codigo_curso: str
    unidad: str
    estado: Optional[str]
    calificacion: Optional[float]
    calificacion_maxima: Optional[float]
    calificacion_final: Optional[float]
    entregada: bool
    calificada: bool
    retrasada: bool
    fecha_entrega_texto: Optional[str]

    class Config:
        from_attributes = True


class AvacAccessOut(BaseModel):
    codigo_curso: str
    ultimo_acceso_texto: Optional[str]
    dias_sin_acceso: Optional[float]
    estado_avac: Optional[str]
    fecha_extraccion: Optional[datetime]

    class Config:
        from_attributes = True


class GradeOut(BaseModel):
    asignatura: str
    nota_final: Optional[float]
    docente: Optional[str]
    grupo: Optional[str]

    class Config:
        from_attributes = True


class InterventionOut(BaseModel):
    id: int
    monitor_nombre: Optional[str]
    medio: Optional[str]
    motivo: Optional[str]
    estado: Optional[str]
    asignatura: Optional[str]
    observacion: Optional[str]
    resultado: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class FichaEstudiante(BaseModel):
    # Datos del estudiante
    id: int
    cedula: Optional[str]
    nombre: str
    correo_institucional: Optional[str]
    correo: Optional[str]
    telefono: Optional[str]
    carrera: Optional[str]
    sede: Optional[str]
    estado_matricula: Optional[str]

    # Indicadores de riesgo
    nivel_riesgo: Optional[str]
    indice_compromiso: Optional[float]
    dias_sin_acceso: Optional[int]
    porcentaje_tareas: Optional[float]
    promedio_calificaciones: Optional[float]

    # Datos relacionados
    accesos_avac: list[AvacAccessOut]
    tareas: list[TaskSubmissionOut]
    calificaciones: list[GradeOut]
    intervenciones: list[InterventionOut]

    # Resumen
    total_intervenciones: int
    ultima_intervencion: Optional[datetime]

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
        accesos_avac=accesos,
        tareas=tareas,
        calificaciones=calificaciones,
        intervenciones=intervenciones,
        total_intervenciones=len(intervenciones),
        ultima_intervencion=ultima_intervencion,
    )
