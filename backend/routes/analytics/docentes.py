"""
Módulo 8.3: Analítica Docente.
Separado de analytics.py monolítico — [ARCH-03] Remediación.
"""
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from pydantic import BaseModel

from ...database import get_db
from ...models import Student, Grade, Intervention
from ...auth.jwt import get_current_user
from ...models.user import User
from ._helpers import apply_periodo_filter

router = APIRouter(prefix="/analytics", tags=["analytics"])


class DocenteAnalytics(BaseModel):
    docente: str
    total_asignaturas: int = 0
    total_estudiantes: int = 0
    carreras: list[str] = []
    niveles: list[int] = []
    promedio_general: Optional[float] = None
    porcentaje_aprobacion: Optional[float] = None
    porcentaje_reprobacion: Optional[float] = None
    estudiantes_riesgo_alto: int = 0
    estudiantes_riesgo_medio: int = 0
    estudiantes_riesgo_bajo: int = 0
    promedio_compromiso: Optional[float] = None
    total_intervenciones: int = 0
    asignaturas: list[str] = []

    class Config:
        from_attributes = True


@router.get("/docentes", response_model=list[DocenteAnalytics])
def get_docentes_analytics(
    carrera: Optional[str] = None,
    periodo: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Vista agregada por docente. Framework §8.3."""
    docente_query = (
        db.query(Grade.docente).filter(Grade.docente.isnot(None), Grade.docente != "")
    )
    docente_query, _ = apply_periodo_filter(docente_query, periodo)
    docente_query = docente_query.distinct()

    _carrera_sids = None
    if carrera:
        _carrera_sids = [s_id for (s_id,) in db.query(Student.id).filter(
            func.lower(Student.carrera).contains(carrera.lower())
        ).all()]
        if _carrera_sids:
            docente_query = docente_query.filter(Grade.student_id.in_(_carrera_sids))
        else:
            return []

    docentes = [d.docente for d in docente_query.all()]

    output = []
    for docente_name in docentes:
        grades_q = db.query(Grade).filter(Grade.docente == docente_name)
        grades_q, _ = apply_periodo_filter(grades_q, periodo)
        if carrera and _carrera_sids:
            grades_q = grades_q.filter(Grade.student_id.in_(_carrera_sids))

        all_grades = grades_q.all()
        if not all_grades:
            continue

        asignaturas = list(set(g.asignatura for g in all_grades))
        carreras_set = list(set(g.carrera for g in all_grades if g.carrera))
        niveles_set = sorted(set(g.nivel for g in all_grades if g.nivel))
        student_ids = list(set(g.student_id for g in all_grades))
        notas = [g.nota_final for g in all_grades if g.nota_final is not None]
        promedio = round(sum(notas) / max(len(notas), 1), 1) if notas else None
        aprobados = sum(1 for n in notas if n >= 70)
        pct_aprob = round((aprobados / max(len(notas), 1)) * 100, 1) if notas else None
        pct_reprob = round(((len(notas) - aprobados) / max(len(notas), 1)) * 100, 1) if notas else None

        risk_counts = db.query(Student.nivel_riesgo, func.count(Student.id)).filter(
            Student.id.in_(student_ids)).group_by(Student.nivel_riesgo).all()
        risk_map = {r[0]: r[1] for r in risk_counts}

        avg_comp = db.query(func.avg(Student.indice_compromiso)).filter(
            Student.id.in_(student_ids)).scalar()

        total_interv = db.query(func.count(Intervention.id)).filter(
            Intervention.docente == docente_name).scalar() or 0

        output.append(DocenteAnalytics(
            docente=docente_name, total_asignaturas=len(asignaturas),
            total_estudiantes=len(student_ids), carreras=carreras_set,
            niveles=niveles_set, promedio_general=promedio,
            porcentaje_aprobacion=pct_aprob, porcentaje_reprobacion=pct_reprob,
            estudiantes_riesgo_alto=risk_map.get("Alto", 0),
            estudiantes_riesgo_medio=risk_map.get("Medio", 0),
            estudiantes_riesgo_bajo=risk_map.get("Bajo", 0),
            promedio_compromiso=round(avg_comp, 2) if avg_comp else None,
            total_intervenciones=total_interv, asignaturas=sorted(asignaturas),
        ))

    output.sort(key=lambda x: x.estudiantes_riesgo_alto, reverse=True)
    return output


@router.get("/docentes/{docente_nombre}/detalle")
def get_docente_detalle(
    docente_nombre: str,
    periodo: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ficha detallada del docente."""
    grades_q = db.query(Grade).filter(Grade.docente == docente_nombre)
    grades_q, _ = apply_periodo_filter(grades_q, periodo)
    grades = grades_q.all()
    if not grades:
        return {"docente": docente_nombre, "asignaturas_detalle": [], "total_estudiantes": 0}

    asig_map = {}
    for g in grades:
        asig_map.setdefault(g.asignatura, {"asignatura": g.asignatura, "carrera": g.carrera, "nivel": g.nivel, "grades": []})
        asig_map[g.asignatura]["grades"].append(g)

    all_student_ids = list(set(g.student_id for g in grades))
    students = db.query(Student).filter(Student.id.in_(all_student_ids)).all()
    student_map = {s.id: s for s in students}

    asignaturas_detalle = []
    for key, data in sorted(asig_map.items()):
        gs = data["grades"]
        notas = [g.nota_final for g in gs if g.nota_final is not None]
        est_list = []
        for g in gs:
            s = student_map.get(g.student_id)
            if s:
                est_list.append({
                    "student_id": s.id, "nombre": s.nombre,
                    "nota_final": g.nota_final, "nivel_riesgo": s.nivel_riesgo,
                    "indice_compromiso": s.indice_compromiso, "dias_sin_acceso": s.dias_sin_acceso,
                })
        aprobados = sum(1 for n in notas if n >= 70)
        total = len(notas) if notas else 1
        asignaturas_detalle.append({
            "asignatura": data["asignatura"], "carrera": data["carrera"], "nivel": data["nivel"],
            "total_estudiantes": len(gs),
            "promedio": round(sum(notas) / max(total, 1), 1) if notas else None,
            "aprobados": aprobados, "reprobados": len(notas) - aprobados,
            "porcentaje_aprobacion": round((aprobados / max(total, 1)) * 100, 1),
            "riesgo_alto": sum(1 for e in est_list if e["nivel_riesgo"] == "Alto"),
            "estudiantes": sorted(est_list, key=lambda x: (x["nota_final"] or 0)),
        })

    return {
        "docente": docente_nombre, "total_asignaturas": len(asignaturas_detalle),
        "total_estudiantes": len(all_student_ids),
        "carreras": list(set(g.carrera for g in grades if g.carrera)),
        "promedio_general": round(
            sum(g.nota_final for g in grades if g.nota_final) / max(sum(1 for g in grades if g.nota_final), 1), 1),
        "asignaturas_detalle": asignaturas_detalle,
    }
