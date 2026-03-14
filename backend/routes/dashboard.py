"""
Dashboard de riesgo — equivalente a la hoja EstudiantesEnRiesgo del Excel.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_
from pydantic import BaseModel

from ..database import get_db
from ..models import Student, Intervention
from ..auth.jwt import get_current_user
from ..models.user import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class RiskStudentOut(BaseModel):
    id: int
    nombre: str
    correo_institucional: Optional[str]
    cedula: Optional[str]
    carrera: Optional[str]
    nivel_riesgo: Optional[str]
    indice_compromiso: Optional[float]
    dias_sin_acceso: Optional[int]
    porcentaje_tareas: Optional[float]
    promedio_calificaciones: Optional[float]
    estado_matricula: Optional[str]
    total_intervenciones: int
    ultima_intervencion: Optional[str]

    class Config:
        from_attributes = True


@router.get("/risk", response_model=list[RiskStudentOut])
def get_risk_dashboard(
    carrera: Optional[str] = None,
    nivel_riesgo: Optional[str] = None,
    solo_sin_intervencion: bool = False,
    offset: int = Query(0, ge=0),
    limit: int = Query(500, le=2500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lista de estudiantes en riesgo con sus indicadores.
    Equivalente a EstudiantesEnRiesgo, pero filtrable y paginada.
    """
    # Subquery: contar intervenciones y última intervención por estudiante
    interv_sq = (
        db.query(
            Intervention.student_id,
            func.count(Intervention.id).label("total_intervenciones"),
            func.max(Intervention.created_at).label("ultima_intervencion"),
        )
        .group_by(Intervention.student_id)
        .subquery()
    )

    query = (
        db.query(Student, interv_sq.c.total_intervenciones, interv_sq.c.ultima_intervencion)
        .outerjoin(interv_sq, Student.id == interv_sq.c.student_id)
        .filter(Student.nivel_riesgo.isnot(None))
    )

    if carrera:
        query = query.filter(func.lower(Student.carrera).contains(carrera.lower()))
    if nivel_riesgo:
        query = query.filter(Student.nivel_riesgo == nivel_riesgo)
    if solo_sin_intervencion:
        query = query.filter(interv_sq.c.total_intervenciones.is_(None))

    # Ordenar: riesgo Alto primero, luego Medio, luego Bajo
    risk_order = case(
        (Student.nivel_riesgo == "Alto", 0),
        (Student.nivel_riesgo == "Medio", 1),
        (Student.nivel_riesgo == "Bajo", 2),
        else_=3,
    )
    results = (
        query
        .order_by(
            risk_order,
            Student.dias_sin_acceso.desc().nullslast(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    output = []
    for student, total_interv, ultima_interv in results:
        output.append(RiskStudentOut(
            id=student.id,
            nombre=student.nombre,
            correo_institucional=student.correo_institucional,
            cedula=student.cedula,
            carrera=student.carrera,
            nivel_riesgo=student.nivel_riesgo,
            indice_compromiso=student.indice_compromiso,
            dias_sin_acceso=student.dias_sin_acceso,
            porcentaje_tareas=student.porcentaje_tareas,
            promedio_calificaciones=student.promedio_calificaciones,
            estado_matricula=student.estado_matricula,
            total_intervenciones=total_interv or 0,
            ultima_intervencion=ultima_interv.isoformat() if ultima_interv else None,
        ))
    return output


@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resumen institucional: totales por riesgo, carreras, etc."""
    total = db.query(func.count(Student.id)).scalar()
    por_riesgo = (
        db.query(Student.nivel_riesgo, func.count(Student.id).label("total"))
        .filter(Student.nivel_riesgo.isnot(None))
        .group_by(Student.nivel_riesgo)
        .all()
    )
    por_carrera = (
        db.query(Student.carrera, func.count(Student.id).label("total"))
        .filter(Student.carrera.isnot(None))
        .group_by(Student.carrera)
        .order_by(func.count(Student.id).desc())
        .limit(20)
        .all()
    )
    total_intervenciones = db.query(func.count(Intervention.id)).scalar()
    estudiantes_intervenidos = db.query(func.count(func.distinct(Intervention.student_id))).scalar()

    return {
        "total_estudiantes": total,
        "por_nivel_riesgo": [{"nivel": r.nivel_riesgo, "total": r.total} for r in por_riesgo],
        "por_carrera": [{"carrera": r.carrera, "total": r.total} for r in por_carrera],
        "total_intervenciones": total_intervenciones,
        "estudiantes_intervenidos": estudiantes_intervenidos,
    }


@router.get("/carreras")
def get_carreras(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista única de carreras para filtros del dashboard."""
    carreras = (
        db.query(Student.carrera)
        .filter(Student.carrera.isnot(None), Student.carrera != "")
        .distinct()
        .order_by(Student.carrera)
        .all()
    )
    return [c.carrera for c in carreras]
