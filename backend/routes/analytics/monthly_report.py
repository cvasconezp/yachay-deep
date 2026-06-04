"""
Épica 4.5: Reporte Mensual Exportable

Genera datos para un reporte mensual consolidado:
KPIs, tendencias, intervenciones, alertas, riesgo por carrera.
El endpoint retorna JSON; la generación PDF se delega a export/.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc, case
from datetime import datetime, timedelta, timezone
from typing import Optional

from ...database import get_db
from ...models.student import Student
from ...models.intervention import Intervention
from ...models.alert_event import AlertEvent
from ...auth.jwt import get_current_user

router = APIRouter(prefix="/analytics/monthly-report", tags=["analytics-monthly-report"])


@router.get("")
def get_monthly_report_data(
    periodo: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Datos consolidados para el reporte mensual."""

    now = datetime.now(timezone.utc)
    month_ago = now - timedelta(days=30)

    # -- Estudiantes --
    student_q = db.query(Student)
    if periodo:
        student_q = student_q.filter(Student.periodo == periodo)

    total = student_q.count()
    if total == 0:
        return {"periodo": periodo, "generado": now.isoformat(), "total_estudiantes": 0}

    alto = student_q.filter(Student.nivel_riesgo == "Alto").count()
    medio = student_q.filter(Student.nivel_riesgo == "Medio").count()
    bajo = student_q.filter(Student.nivel_riesgo == "Bajo").count()
    avg_compromiso = student_q.with_entities(sqlfunc.avg(Student.indice_compromiso)).scalar()
    avg_tareas = student_q.with_entities(sqlfunc.avg(Student.porcentaje_tareas)).scalar()

    # -- Intervenciones último mes --
    inv_q = db.query(Intervention)
    if periodo:
        inv_q = inv_q.filter(Intervention.periodo == periodo)

    total_intervenciones = inv_q.count()
    nuevas_mes = inv_q.filter(Intervention.created_at >= month_ago).count()
    resueltas = inv_q.filter(Intervention.estado_workflow == "resuelto").count()
    overdue = inv_q.filter(Intervention.overdue == True).count()

    # Por medio
    por_medio = inv_q.with_entities(
        Intervention.medio, sqlfunc.count(Intervention.id)
    ).group_by(Intervention.medio).all()

    # -- Alertas último mes --
    alert_q = db.query(AlertEvent)
    total_alertas = alert_q.filter(AlertEvent.created_at >= month_ago).count() if hasattr(AlertEvent, 'created_at') else 0

    # -- Riesgo por carrera --
    carrera_stats = student_q.with_entities(
        Student.carrera,
        sqlfunc.count(Student.id).label("total"),
        sqlfunc.count(case((Student.nivel_riesgo == "Alto", 1))).label("alto"),
        sqlfunc.avg(Student.indice_compromiso).label("compromiso"),
    ).filter(Student.carrera.isnot(None)).group_by(Student.carrera).all()

    carreras = [{
        "carrera": c.carrera,
        "total": c.total,
        "riesgo_alto": c.alto,
        "tasa_riesgo": round(c.alto / c.total * 100, 1) if c.total else 0,
        "compromiso": round(float(c.compromiso or 0), 3),
    } for c in carrera_stats]
    carreras.sort(key=lambda x: x["tasa_riesgo"], reverse=True)

    return {
        "periodo": periodo,
        "generado": now.isoformat(),
        "total_estudiantes": total,
        "resumen_riesgo": {
            "alto": alto,
            "medio": medio,
            "bajo": bajo,
            "tasa_riesgo_alto": round(alto / total * 100, 1),
        },
        "indicadores": {
            "compromiso_promedio": round(float(avg_compromiso or 0), 3),
            "tareas_promedio": round(float(avg_tareas or 0), 1),
            "retencion_estimada": round((1 - alto / total) * 100, 1),
        },
        "intervenciones": {
            "total": total_intervenciones,
            "nuevas_ultimo_mes": nuevas_mes,
            "resueltas": resueltas,
            "overdue": overdue,
            "tasa_resolucion": round(resueltas / total_intervenciones * 100, 1) if total_intervenciones else 0,
            "por_medio": [{
                "medio": m or "Sin especificar",
                "cantidad": c,
            } for m, c in por_medio],
        },
        "alertas_ultimo_mes": total_alertas,
        "riesgo_por_carrera": carreras,
    }
