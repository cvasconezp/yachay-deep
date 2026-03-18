"""
Módulo 8.4: Tutorías por Asignatura.
Separado de analytics.py monolítico — [ARCH-03] Remediación.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from ...database import get_db
from ...models import Student, Grade, Intervention
from ...auth.jwt import get_current_user
from ...models.user import User
from ._helpers import apply_periodo_filter

router = APIRouter(prefix="/analytics", tags=["analytics"])


class TutoriaAsignatura(BaseModel):
    asignatura: str
    docente: Optional[str] = None
    carrera: Optional[str] = None
    nivel: Optional[int] = None
    total_en_riesgo: int = 0
    estudiantes: list = []

    class Config:
        from_attributes = True


@router.get("/tutorias/por-asignatura", response_model=list[TutoriaAsignatura])
def get_tutorias_por_asignatura(
    carrera: Optional[str] = None,
    nivel_riesgo: str = Query("Alto", description="Alto, Medio, o Alto,Medio"),
    periodo: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Framework §8.4 — Listas de tutoría por asignatura."""
    niveles_filtro = [n.strip() for n in nivel_riesgo.split(",")]

    risk_students = db.query(Student).filter(Student.nivel_riesgo.in_(niveles_filtro))
    if carrera:
        risk_students = risk_students.filter(func.lower(Student.carrera).contains(carrera.lower()))
    risk_students = risk_students.all()
    if not risk_students:
        return []

    risk_ids = [s.id for s in risk_students]
    student_map = {s.id: s for s in risk_students}

    grades_q = db.query(Grade).filter(Grade.student_id.in_(risk_ids))
    grades_q, _ = apply_periodo_filter(grades_q, periodo)
    grades = grades_q.all()

    existing_interv = dict(
        db.query(Intervention.student_id, func.count(Intervention.id))
        .filter(Intervention.student_id.in_(risk_ids))
        .group_by(Intervention.student_id).all()
    )

    asig_map = {}
    for g in grades:
        key = g.asignatura
        if key not in asig_map:
            asig_map[key] = {
                "asignatura": g.asignatura, "docente": g.docente,
                "carrera": g.carrera, "nivel": g.nivel, "estudiantes": [],
            }
        s = student_map.get(g.student_id)
        if not s:
            continue

        motivos = []
        if s.dias_sin_acceso and s.dias_sin_acceso > 14:
            motivos.append("Inactividad AVAC")
        if s.porcentaje_tareas is not None and s.porcentaje_tareas < 50:
            motivos.append("Tareas no entregadas")
        if g.nota_final is not None and g.nota_final < 70:
            motivos.append("Bajo rendimiento")
        if s.indice_compromiso is not None and s.indice_compromiso < 0.4:
            motivos.append("Bajo compromiso")
        if not motivos:
            motivos.append("Riesgo general")

        asig_map[key]["estudiantes"].append({
            "student_id": s.id, "nombre": s.nombre,
            "correo_institucional": s.correo_institucional,
            "telefono": s.telefono, "whatsapp": s.whatsapp,
            "nivel_riesgo": s.nivel_riesgo, "nota_asignatura": g.nota_final,
            "indice_compromiso": s.indice_compromiso,
            "dias_sin_acceso": s.dias_sin_acceso,
            "motivos_riesgo": motivos,
            "intervenciones_previas": existing_interv.get(s.id, 0),
        })

    output = []
    for data in asig_map.values():
        data["total_en_riesgo"] = len(data["estudiantes"])
        data["estudiantes"].sort(
            key=lambda x: (0 if x["nivel_riesgo"] == "Alto" else 1, x["nota_asignatura"] or 0)
        )
        output.append(TutoriaAsignatura(**data))

    output.sort(key=lambda x: x.total_en_riesgo, reverse=True)
    return output
