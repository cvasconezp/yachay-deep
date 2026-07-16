"""
Épica 4.2: Análisis de Efectividad de Intervenciones

Compara snapshots pre-intervención con estado actual post-intervención
para medir el impacto real de las intervenciones.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc, case, and_

from ...database import get_db
from ...models.student import Student
from ...models.intervention import Intervention
from ...auth.jwt import get_current_user
from ...services.intervention_metrics import evaluar, INDICADORES

router = APIRouter(prefix="/analytics/effectiveness", tags=["analytics-effectiveness"])


def _calcular_efectividad_intervencion(inv, student) -> dict:
    """Calcula el delta de indicadores para una intervención cerrada."""
    result = {
        "intervention_id": inv.id,
        "student_id": inv.student_id,
        "medio": inv.medio,
        "motivo": inv.motivo,
        "resultado": inv.resultado,
        "estado_workflow": inv.estado_workflow,
        "carrera": inv.carrera,
    }

    # Deltas: comparar snapshot (momento de intervención) con estado actual
    if inv.snapshot_compromiso is not None and student and student.indice_compromiso is not None:
        result["delta_compromiso"] = round(student.indice_compromiso - inv.snapshot_compromiso, 3)
    else:
        result["delta_compromiso"] = None

    if inv.snapshot_porcentaje_tareas is not None and student and student.porcentaje_tareas is not None:
        result["delta_tareas"] = round(student.porcentaje_tareas - inv.snapshot_porcentaje_tareas, 1)
    else:
        result["delta_tareas"] = None

    if inv.snapshot_prob_desercion is not None and student and student.prob_desercion is not None:
        result["delta_prob_desercion"] = round(student.prob_desercion - inv.snapshot_prob_desercion, 3)
    else:
        result["delta_prob_desercion"] = None

    # Días sin acceso: también entra en la evaluación (bajar es mejorar)
    if inv.snapshot_dias_sin_acceso is not None and student and student.dias_sin_acceso is not None:
        result["delta_dias_sin_acceso"] = student.dias_sin_acceso - inv.snapshot_dias_sin_acceso
    else:
        result["delta_dias_sin_acceso"] = None

    # Éxito con UMBRALES de significancia (mismos que el panel individual).
    # Antes bastaba con delta>0, así que el ruido contaba como mejora.
    ev = evaluar({
        "compromiso": result["delta_compromiso"],
        "dias_sin_acceso": result["delta_dias_sin_acceso"],
        "porcentaje_tareas": result["delta_tareas"],
        "prob_desercion": result["delta_prob_desercion"],
    })
    result["exitosa"] = ev["exitosa"]
    result["concluyente"] = ev["concluyente"]
    result["mejoras"] = ev["mejoras"]
    result["empeoramientos"] = ev["empeoramientos"]
    result["detalle"] = ev["detalle"]

    return result


@router.get("")
def get_effectiveness(
    periodo: str = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Análisis de efectividad de intervenciones cerradas/resueltas."""

    q = db.query(Intervention).filter(
        Intervention.estado_workflow.in_(["resuelto", "cerrado"])
    )
    if periodo:
        q = q.filter(Intervention.periodo == periodo)

    intervenciones = q.all()

    if not intervenciones:
        return {
            "total_analizadas": 0,
            "tasa_exito_global": 0,
            "por_medio": [],
            "por_motivo": [],
            "por_carrera": [],
            "ranking_medios": [],
        }

    # Obtener estudiantes para comparación
    student_ids = list({inv.student_id for inv in intervenciones if inv.student_id})
    students_map = {}
    if student_ids:
        students = db.query(Student).filter(Student.id.in_(student_ids)).all()
        students_map = {s.id: s for s in students}

    # Calcular efectividad individual
    resultados = []
    for inv in intervenciones:
        student = students_map.get(inv.student_id)
        resultados.append(_calcular_efectividad_intervencion(inv, student))

    total = len(resultados)
    concluyentes = [r for r in resultados if r.get("concluyente")]
    exitosas = sum(1 for r in concluyentes if r["exitosa"])
    # Denominador = solo las que tienen datos suficientes. Una intervención sin datos
    # no es un fracaso; contarla como tal hundiría la tasa artificialmente.
    tasa_global = round(exitosas / len(concluyentes) * 100, 1) if concluyentes else 0

    # Agrupación por medio
    por_medio = _agrupar_por(resultados, "medio")
    # Agrupación por motivo
    por_motivo = _agrupar_por(resultados, "motivo")
    # Agrupación por carrera
    por_carrera = _agrupar_por(resultados, "carrera")

    # Ranking de medios más efectivos — solo los que tienen muestra suficiente.
    # Ordenar por tasa sin filtrar dejaba arriba a grupos de 2 o 3 casos.
    ranking = sorted(
        [m for m in por_medio if m["muestra_suficiente"]],
        key=lambda x: x["tasa_exito"], reverse=True,
    )

    return {
        "total_analizadas": total,
        "analizadas_concluyentes": len(concluyentes),
        "tasa_exito_global": tasa_global,
        "exitosas": exitosas,
        "por_medio": por_medio,
        "por_motivo": por_motivo,
        "por_carrera": por_carrera,
        "ranking_medios": ranking,
        "umbrales": {k: v["umbral"] for k, v in INDICADORES.items()},
        "advertencia": (
            "Mide la evolución de los estudiantes intervenidos, NO el efecto causal de "
            "la intervención. Los intervenidos se eligen por estar en el extremo peor, y "
            "los extremos tienden a mejorar solos (reversión a la media). Para estimar el "
            "efecto atribuible use /analytics/effectiveness/comparado."
        ),
    }


# Por debajo de este N, una tasa de éxito no significa nada: con 3 casos, uno solo
# mueve la cifra 33 puntos. Se calcula igual pero se marca como no fiable.
MIN_MUESTRA_FIABLE = 10


def _agrupar_por(resultados: list, campo: str) -> list:
    """Agrupa por un campo y calcula la tasa de éxito SOLO sobre las concluyentes."""
    grupos = {}
    for r in resultados:
        key = r.get(campo) or "Sin especificar"
        if key not in grupos:
            grupos[key] = {"total": 0, "concluyentes": 0, "exitosas": 0,
                           "delta_compromiso_sum": 0, "delta_count": 0}
        grupos[key]["total"] += 1
        if r.get("concluyente"):
            grupos[key]["concluyentes"] += 1
            if r["exitosa"]:
                grupos[key]["exitosas"] += 1
        if r.get("delta_compromiso") is not None:
            grupos[key]["delta_compromiso_sum"] += r["delta_compromiso"]
            grupos[key]["delta_count"] += 1

    return [{
        campo: k,
        "total": v["total"],
        "concluyentes": v["concluyentes"],
        "exitosas": v["exitosas"],
        "tasa_exito": round(v["exitosas"] / v["concluyentes"] * 100, 1) if v["concluyentes"] else 0,
        "muestra_suficiente": v["concluyentes"] >= MIN_MUESTRA_FIABLE,
        "delta_compromiso_promedio": round(v["delta_compromiso_sum"] / v["delta_count"], 3) if v["delta_count"] else None,
    } for k, v in sorted(grupos.items(), key=lambda x: x[1]["total"], reverse=True)]


@router.get("/comparado")
def get_effectiveness_comparado(
    periodo: str = Query(None),
    dias_seguimiento: int = Query(30, ge=7, le=180),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Efecto estimado de intervenir, comparando contra no intervenidos comparables.

    A diferencia de /analytics/effectiveness (que solo mira el antes/después de los
    intervenidos), aquí se descuenta lo que habría pasado igualmente. Es lo único que
    permite hablar de efecto atribuible — y aun así es una estimación, no una prueba.
    """
    from ...services.cohort_comparison import comparar_cohortes
    return comparar_cohortes(db, periodo=periodo, dias_seguimiento=dias_seguimiento)
