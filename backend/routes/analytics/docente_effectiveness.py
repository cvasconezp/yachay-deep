"""
Épica 4.4: Efectividad Docente

Compara tasas de aprobación por docente usando Grade directamente.
Comparativa multi-período.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc, case
from typing import Optional

from ...database import get_db
from ...models.grade import Grade
from ...auth.jwt import get_current_user

router = APIRouter(prefix="/analytics/docente-effectiveness", tags=["analytics-docente-effectiveness"])


@router.get("")
def get_docente_effectiveness(
    periodo: Optional[str] = Query(None),
    carrera: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Indicadores de efectividad docente basados en calificaciones."""

    q = db.query(
        Grade.docente,
        Grade.periodo,
        Grade.carrera,
        sqlfunc.count(Grade.id).label("total_estudiantes"),
        sqlfunc.avg(Grade.nota_final).label("promedio_notas"),
        sqlfunc.count(case((Grade.nota_final >= 7.0, 1))).label("aprobados"),
        sqlfunc.count(case((Grade.nota_final < 7.0, 1))).label("reprobados"),
    ).filter(Grade.docente.isnot(None))

    if periodo:
        q = q.filter(Grade.periodo == periodo)
    if carrera:
        q = q.filter(Grade.carrera == carrera)

    q = q.group_by(Grade.docente, Grade.periodo, Grade.carrera)
    rows = q.all()

    if not rows:
        return {"docentes": [], "ranking": []}

    docente_data = {}
    for r in rows:
        key = r.docente
        if key not in docente_data:
            docente_data[key] = {"periodos": [], "total_global": 0, "aprobados_global": 0}

        tasa_aprobacion = round(r.aprobados / r.total_estudiantes * 100, 1) if r.total_estudiantes else 0
        docente_data[key]["periodos"].append({
            "periodo": r.periodo,
            "carrera": r.carrera,
            "total_estudiantes": r.total_estudiantes,
            "promedio_notas": round(float(r.promedio_notas or 0), 2),
            "aprobados": r.aprobados,
            "reprobados": r.reprobados,
            "tasa_aprobacion": tasa_aprobacion,
        })
        docente_data[key]["total_global"] += r.total_estudiantes
        docente_data[key]["aprobados_global"] += r.aprobados

    docentes = []
    for nombre, data in docente_data.items():
        periodos = sorted(data["periodos"], key=lambda x: x["periodo"] or "")
        tasas = [p["tasa_aprobacion"] for p in periodos]
        trend = tasas[-1] - tasas[0] if len(tasas) >= 2 else 0
        tasa_global = round(data["aprobados_global"] / data["total_global"] * 100, 1) if data["total_global"] else 0

        docentes.append({
            "docente": nombre,
            "tasa_aprobacion_global": tasa_global,
            "total_estudiantes": data["total_global"],
            "periodos": periodos,
            "tendencia_aprobacion": round(trend, 1),
            "total_periodos": len(periodos),
        })

    ranking = sorted(docentes, key=lambda x: x["tasa_aprobacion_global"], reverse=True)

    return {
        "docentes": docentes,
        "ranking": ranking,
        "total_docentes": len(docentes),
    }
