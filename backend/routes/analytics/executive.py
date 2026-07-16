"""
Épica 4.1: Dashboard Ejecutivo Institucional

Endpoint /analytics/executive con KPIs institucionales:
- Retención estimada
- Distribución de riesgo global
- Cobertura de intervención
- Efectividad de intervenciones
- Tendencia de compromiso
- Semáforo por carrera
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc, case, and_

from ...database import get_db
from ...models.student import Student
from ...models.intervention import Intervention
from ...auth.jwt import get_current_user
from ...services.retiro import filtrar_activos

router = APIRouter(prefix="/analytics/executive", tags=["analytics-executive"])


@router.get("")
def get_executive_dashboard(
    periodo: str = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """KPIs institucionales para el dashboard ejecutivo."""

    # Filtro base por período
    student_q = filtrar_activos(db.query(Student))
    intervention_q = db.query(Intervention)
    if periodo:
        student_q = student_q.filter(Student.periodo == periodo)
        intervention_q = intervention_q.filter(Intervention.periodo == periodo)

    # 1. Total estudiantes
    total_students = student_q.count()
    if total_students == 0:
        return {
            "total_estudiantes": 0,
            "kpis": {},
            "distribucion_riesgo": {},
            "semaforo_carreras": [],
            "tendencia_compromiso": [],
        }

    # 2. Distribución de riesgo
    risk_counts = student_q.with_entities(
        Student.nivel_riesgo, sqlfunc.count(Student.id)
    ).group_by(Student.nivel_riesgo).all()
    risk_map = {r or "Sin clasificar": c for r, c in risk_counts}
    alto = risk_map.get("Alto", 0)
    medio = risk_map.get("Medio", 0)
    bajo = risk_map.get("Bajo", 0)

    # 3. Retención estimada (% estudiantes NO en riesgo alto)
    retencion = round((1 - alto / total_students) * 100, 1) if total_students else 0

    # 4. Cobertura de intervención (% de estudiantes riesgo alto con al menos 1 intervención)
    students_alto = student_q.filter(Student.nivel_riesgo == "Alto").all()
    ids_alto = [s.id for s in students_alto]
    if ids_alto:
        intervenidos = intervention_q.filter(
            Intervention.student_id.in_(ids_alto)
        ).with_entities(Intervention.student_id).distinct().count()
        cobertura = round(intervenidos / len(ids_alto) * 100, 1)
    else:
        cobertura = 100.0

    # 5. Efectividad global (% intervenciones resueltas vs total cerradas/resueltas)
    total_cerradas = intervention_q.filter(
        Intervention.estado_workflow.in_(["resuelto", "cerrado"])
    ).count()
    resueltas = intervention_q.filter(Intervention.estado_workflow == "resuelto").count()
    efectividad = round(resueltas / total_cerradas * 100, 1) if total_cerradas else 0

    # 6. Promedio compromiso
    avg_compromiso = student_q.with_entities(
        sqlfunc.avg(Student.indice_compromiso)
    ).scalar()
    avg_compromiso = round(float(avg_compromiso or 0), 3)

    # 7. Intervenciones activas
    intervenciones_activas = intervention_q.filter(
        Intervention.estado_workflow.notin_(["resuelto", "cerrado"])
    ).count()

    # 8. Semáforo por carrera
    carrera_stats = student_q.with_entities(
        Student.carrera,
        sqlfunc.count(Student.id).label("total"),
        sqlfunc.count(case((Student.nivel_riesgo == "Alto", 1))).label("alto"),
        sqlfunc.count(case((Student.nivel_riesgo == "Medio", 1))).label("medio"),
        sqlfunc.avg(Student.indice_compromiso).label("avg_compromiso"),
    ).filter(Student.carrera.isnot(None)).group_by(Student.carrera).all()

    semaforo = []
    for row in carrera_stats:
        tasa_alto = row.alto / row.total * 100 if row.total else 0
        if tasa_alto >= 30:
            color = "rojo"
        elif tasa_alto >= 15:
            color = "amarillo"
        else:
            color = "verde"
        semaforo.append({
            "carrera": row.carrera,
            "total": row.total,
            "alto": row.alto,
            "medio": row.medio,
            "bajo": row.total - row.alto - row.medio,
            "tasa_riesgo_alto": round(tasa_alto, 1),
            "compromiso_promedio": round(float(row.avg_compromiso or 0), 3),
            "semaforo": color,
        })
    semaforo.sort(key=lambda x: x["tasa_riesgo_alto"], reverse=True)

    # 9. Tendencia de compromiso por período (últimos períodos disponibles)
    tendencia = db.query(
        Student.periodo,
        sqlfunc.avg(Student.indice_compromiso).label("compromiso"),
        sqlfunc.count(Student.id).label("total"),
        sqlfunc.count(case((Student.nivel_riesgo == "Alto", 1))).label("alto"),
    ).filter(Student.periodo.isnot(None)).group_by(Student.periodo).order_by(Student.periodo).all()

    tendencia_list = [{
        "periodo": t.periodo,
        "compromiso_promedio": round(float(t.compromiso or 0), 3),
        "total_estudiantes": t.total,
        "riesgo_alto": t.alto,
        "tasa_riesgo_alto": round(t.alto / t.total * 100, 1) if t.total else 0,
    } for t in tendencia]

    return {
        "total_estudiantes": total_students,
        "kpis": {
            "retencion_estimada": retencion,
            "cobertura_intervencion": cobertura,
            "efectividad_intervenciones": efectividad,
            "compromiso_promedio": avg_compromiso,
            "intervenciones_activas": intervenciones_activas,
            "estudiantes_riesgo_alto": alto,
        },
        "distribucion_riesgo": risk_map,
        "semaforo_carreras": semaforo,
        "tendencia_periodos": tendencia_list,
    }
