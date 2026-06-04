"""
Módulo de Analítica: Terceras Matrículas (Oyentes Condicionados).

Endpoints para visualizar y gestionar estudiantes en tercera matrícula.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from ...database import get_db
from ...models import Student
from ...models.enrollment import Enrollment
from ...auth.jwt import get_current_user
from ...models.user import User

router = APIRouter(prefix="/analytics", tags=["analytics"])


# ── Schemas ──────────────────────────────────────────────────────────────


class TerceraMatriculaEstudiante(BaseModel):
    student_id: int
    nombre: str
    cedula: Optional[str] = None
    carrera: Optional[str] = None
    nivel_riesgo: Optional[str] = None
    asignaturas: list[dict] = []
    total_asignaturas: int = 0
    tiene_pago_pendiente: bool = False

    class Config:
        from_attributes = True


class TerceraMatriculaResumen(BaseModel):
    total_estudiantes: int = 0
    total_asignaturas: int = 0
    por_carrera: list[dict] = []
    por_estado: dict = {}
    con_pago_pendiente: int = 0
    sin_docente_asignado: int = 0


# ── Endpoints ────────────────────────────────────────────────────────────


@router.get("/terceras-matriculas", response_model=list[TerceraMatriculaEstudiante])
def get_terceras_matriculas(
    carrera: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista de estudiantes con tercera matrícula y sus asignaturas."""
    query = db.query(Student).filter(Student.es_tercera_matricula == True)
    if carrera:
        query = query.filter(Student.carrera == carrera)

    students = query.order_by(Student.nombre).all()

    result = []
    for s in students:
        enrollments = db.query(Enrollment).filter(
            Enrollment.student_id == s.id,
            Enrollment.es_tercera_matricula == True,
        ).all()

        asignaturas = []
        tiene_pago_pendiente = False
        for e in enrollments:
            pago_ok = e.pagado and e.pagado.upper() == "SI"
            if not pago_ok:
                tiene_pago_pendiente = True
            asignaturas.append({
                "asignatura": e.asignatura,
                "codigo_asignatura": e.codigo_asignatura,
                "codigo_grupo": e.codigo_grupo,
                "nivel": e.nivel,
                "docente": e.docente,
                "correo_docente": e.correo_docente,
                "pagado": e.pagado,
                "estado_solicitud": e.estado_solicitud,
                "tipo_aprobacion": e.tipo_aprobacion,
                "bloque": e.bloque,
            })

        result.append(TerceraMatriculaEstudiante(
            student_id=s.id,
            nombre=s.nombre or "",
            cedula=s.cedula,
            carrera=s.carrera,
            nivel_riesgo=s.nivel_riesgo,
            asignaturas=asignaturas,
            total_asignaturas=len(asignaturas),
            tiene_pago_pendiente=tiene_pago_pendiente,
        ))

    return result


@router.get("/terceras-matriculas/resumen", response_model=TerceraMatriculaResumen)
def get_terceras_matriculas_resumen(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resumen estadístico de terceras matrículas."""
    total_est = db.query(Student).filter(
        Student.es_tercera_matricula == True
    ).count()

    if total_est == 0:
        return TerceraMatriculaResumen()

    # Total asignaturas en tercera matrícula
    total_asig = db.query(Enrollment).filter(
        Enrollment.es_tercera_matricula == True
    ).count()

    # Por carrera
    carreras = db.query(
        Student.carrera,
        func.count(Student.id),
    ).filter(
        Student.es_tercera_matricula == True,
        Student.carrera.isnot(None),
    ).group_by(Student.carrera).order_by(func.count(Student.id).desc()).all()

    por_carrera = [{"carrera": c, "total": t} for c, t in carreras]

    # Por estado de solicitud
    estados = db.query(
        Enrollment.estado_solicitud,
        func.count(Enrollment.id),
    ).filter(
        Enrollment.es_tercera_matricula == True,
    ).group_by(Enrollment.estado_solicitud).all()

    por_estado = {(e or "Sin estado"): t for e, t in estados}

    # Con pago pendiente
    students_sin_pago = db.query(
        func.count(func.distinct(Enrollment.student_id))
    ).filter(
        Enrollment.es_tercera_matricula == True,
        Enrollment.pagado.notin_(["SI", "si", "Si"]),
    ).scalar() or 0

    # Sin docente asignado
    sin_docente = db.query(
        func.count(Enrollment.id)
    ).filter(
        Enrollment.es_tercera_matricula == True,
        (Enrollment.docente.is_(None)) | (Enrollment.docente == ""),
    ).scalar() or 0

    return TerceraMatriculaResumen(
        total_estudiantes=total_est,
        total_asignaturas=total_asig,
        por_carrera=por_carrera,
        por_estado=por_estado,
        con_pago_pendiente=students_sin_pago,
        sin_docente_asignado=sin_docente,
    )
