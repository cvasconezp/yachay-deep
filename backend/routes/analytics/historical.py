"""
Épica 4.3: Análisis Histórico por Asignatura

- Tasa de reprobación por materia y período
- Detección de tendencia negativa (regresión lineal)
- Cruce abandono × asignaturas
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc, case
from typing import Optional
import numpy as np

from ...database import get_db
from ...models.student import Student
from ...models.grade import Grade
from ...models.enrollment import Enrollment
from ...auth.jwt import get_current_user

router = APIRouter(prefix="/analytics/historical", tags=["analytics-historical"])


def _linear_trend(values: list[float]) -> dict:
    """Calcula tendencia lineal simple sobre una serie de valores."""
    if len(values) < 2:
        return {"slope": 0, "tendencia": "estable"}
    x = np.arange(len(values), dtype=float)
    y = np.array(values, dtype=float)
    mask = ~np.isnan(y)
    if mask.sum() < 2:
        return {"slope": 0, "tendencia": "estable"}
    x, y = x[mask], y[mask]
    slope = float(np.polyfit(x, y, 1)[0])
    if slope > 0.02:
        tendencia = "empeorando"
    elif slope < -0.02:
        tendencia = "mejorando"
    else:
        tendencia = "estable"
    return {"slope": round(slope, 4), "tendencia": tendencia}


@router.get("/asignaturas")
def get_historical_asignaturas(
    carrera: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Estadísticas históricas por asignatura con detección de tendencias."""

    q = db.query(
        Grade.asignatura,
        Grade.carrera,
        Grade.periodo,
        Grade.docente,
        sqlfunc.count(Grade.id).label("total_estudiantes"),
        sqlfunc.avg(Grade.nota_final).label("promedio"),
        sqlfunc.count(case((Grade.nota_final < 7.0, 1))).label("reprobados"),
    )

    if carrera:
        q = q.filter(Grade.carrera == carrera)

    q = q.group_by(Grade.asignatura, Grade.carrera, Grade.periodo, Grade.docente)
    rows = q.all()

    if not rows:
        return {"asignaturas": [], "tendencias_negativas": []}

    asig_data = {}
    for r in rows:
        key = r.asignatura or "Sin nombre"
        if key not in asig_data:
            asig_data[key] = {"carrera": r.carrera, "periodos": []}
        tasa_reprobacion = round(r.reprobados / r.total_estudiantes * 100, 1) if r.total_estudiantes else 0
        asig_data[key]["periodos"].append({
            "periodo": r.periodo,
            "total_estudiantes": r.total_estudiantes,
            "promedio": round(float(r.promedio or 0), 2),
            "reprobados": r.reprobados,
            "tasa_reprobacion": tasa_reprobacion,
            "docente": r.docente,
        })

    asignaturas = []
    tendencias_negativas = []
    for nombre, data in asig_data.items():
        periodos = sorted(data["periodos"], key=lambda x: x["periodo"] or "")
        tasas = [p["tasa_reprobacion"] for p in periodos]
        trend = _linear_trend(tasas)
        entry = {
            "asignatura": nombre,
            "carrera": data["carrera"],
            "periodos": periodos,
            "tendencia": trend,
            "total_periodos": len(periodos),
            "tasa_reprobacion_ultima": tasas[-1] if tasas else 0,
        }
        asignaturas.append(entry)
        if trend["tendencia"] == "empeorando":
            tendencias_negativas.append(entry)

    asignaturas.sort(key=lambda x: x["tasa_reprobacion_ultima"], reverse=True)
    tendencias_negativas.sort(key=lambda x: x["tendencia"]["slope"], reverse=True)

    return {
        "asignaturas": asignaturas,
        "tendencias_negativas": tendencias_negativas,
        "total_asignaturas": len(asignaturas),
    }


@router.get("/abandono-asignaturas")
def get_abandono_asignaturas(
    periodo: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Cruce: ¿qué asignaturas cursaban los estudiantes que desertaron?"""

    student_q = db.query(Student).filter(Student.nivel_riesgo == "Alto")
    if periodo:
        student_q = student_q.filter(Student.periodo == periodo)

    desertores = student_q.all()
    desertor_ids = [s.id for s in desertores]

    if not desertor_ids:
        return {"total_desertores": 0, "asignaturas_afectadas": []}

    enrollments = db.query(
        Enrollment.asignatura,
        Enrollment.carrera,
        sqlfunc.count(Enrollment.id).label("desertores_inscritos"),
    ).filter(
        Enrollment.student_id.in_(desertor_ids)
    ).group_by(Enrollment.asignatura, Enrollment.carrera).order_by(
        sqlfunc.count(Enrollment.id).desc()
    ).all()

    return {
        "total_desertores": len(desertor_ids),
        "asignaturas_afectadas": [{
            "asignatura": e.asignatura,
            "carrera": e.carrera,
            "desertores_inscritos": e.desertores_inscritos,
            "porcentaje": round(e.desertores_inscritos / len(desertor_ids) * 100, 1),
        } for e in enrollments[:30]],
    }
