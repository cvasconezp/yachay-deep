"""
Dashboard de riesgo — equivalente a la hoja EstudiantesEnRiesgo del Excel.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from pydantic import BaseModel

from sqlalchemy import distinct as sa_distinct

from ..database import get_db
from ..models import Student, Intervention, Grade
from ..models.enrollment import Enrollment
from ..auth.jwt import get_current_user
from ..models.user import User


def _period_student_ids(db: Session, periodo: Optional[str]):
    """Subquery de student_ids filtrados por período (Grades + Enrollments)."""
    from sqlalchemy import or_
    pf = periodo if periodo else "actual"

    grade_sq = db.query(Grade.student_id).distinct()
    enroll_sq = db.query(Enrollment.student_id).distinct()

    if pf == "actual":
        grade_sq = grade_sq.filter(Grade.periodo.is_(None))
        enroll_sq = enroll_sq.filter(Enrollment.periodo.is_(None))
    elif pf != "todos":
        # Dual format: "P68" <-> "68"
        if pf.startswith("P"):
            grade_sq = grade_sq.filter(or_(Grade.periodo == pf, Grade.periodo == pf[1:]))
            enroll_sq = enroll_sq.filter(or_(Enrollment.periodo == pf, Enrollment.periodo == pf[1:]))
        else:
            grade_sq = grade_sq.filter(or_(Grade.periodo == pf, Grade.periodo == f"P{pf}"))
            enroll_sq = enroll_sq.filter(or_(Enrollment.periodo == pf, Enrollment.periodo == f"P{pf}"))

    sq = grade_sq.union(enroll_sq)
    return sq, pf


def _period_has_grades(db: Session, periodo: Optional[str]) -> bool:
    """Verifica si existen calificaciones reales para el período dado."""
    from sqlalchemy import or_
    pf = periodo if periodo else "actual"
    q = db.query(Grade.id)
    if pf == "actual":
        q = q.filter(Grade.periodo.is_(None))
    elif pf == "todos":
        return True
    else:
        if pf.startswith("P"):
            q = q.filter(or_(Grade.periodo == pf, Grade.periodo == pf[1:]))
        else:
            q = q.filter(or_(Grade.periodo == pf, Grade.periodo == f"P{pf}"))
    return q.limit(1).first() is not None

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
    prob_desercion: Optional[float] = None
    prob_reprobacion: Optional[float] = None
    total_intervenciones: int
    ultima_intervencion: Optional[str]

    class Config:
        from_attributes = True


@router.get("/risk", response_model=list[RiskStudentOut])
def get_risk_dashboard(
    carrera: Optional[str] = None,
    nivel_riesgo: Optional[str] = None,
    solo_sin_intervencion: bool = False,
    periodo: Optional[str] = None,
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

    # Filtrar por período: solo estudiantes que tienen calificaciones en ese período
    period_sq, _ = _period_student_ids(db, periodo)
    query = query.filter(Student.id.in_(period_sq))

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
            prob_desercion=student.prob_desercion,
            prob_reprobacion=student.prob_reprobacion,
            total_intervenciones=total_interv or 0,
            ultima_intervencion=ultima_interv.isoformat() if ultima_interv else None,
        ))
    return output


@router.get("/stats")
def get_stats(
    periodo: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resumen institucional: totales por riesgo, carreras, etc."""
    period_sq, _ = _period_student_ids(db, periodo)
    base = db.query(Student).filter(Student.id.in_(period_sq))

    total = base.count()
    por_riesgo = (
        base.with_entities(Student.nivel_riesgo, func.count(Student.id).label("total"))
        .filter(Student.nivel_riesgo.isnot(None))
        .group_by(Student.nivel_riesgo)
        .all()
    )
    por_carrera = (
        base.with_entities(Student.carrera, func.count(Student.id).label("total"))
        .filter(Student.carrera.isnot(None))
        .group_by(Student.carrera)
        .order_by(func.count(Student.id).desc())
        .limit(20)
        .all()
    )
    total_intervenciones = db.query(func.count(Intervention.id)).scalar()
    estudiantes_intervenidos = db.query(func.count(func.distinct(Intervention.student_id))).scalar()

    # Detectar si hay datos reales (grades) para el periodo
    has_grades = _period_has_grades(db, periodo)

    return {
        "total_estudiantes": total,
        "por_nivel_riesgo": [{"nivel": r.nivel_riesgo, "total": r.total} for r in por_riesgo],
        "por_carrera": [{"carrera": r.carrera, "total": r.total} for r in por_carrera],
        "total_intervenciones": total_intervenciones,
        "estudiantes_intervenidos": estudiantes_intervenidos,
        "tiene_datos_periodo": has_grades,
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
