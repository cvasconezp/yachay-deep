"""
Score de Recuperabilidad — Épica 1.4

Calcula un puntaje 0-100 que indica qué tan probable es que un estudiante
en riesgo pueda recuperarse si recibe intervención oportuna.

Factores (pesos configurables):
  - Actividad reciente (30%): menos días sin acceso = más recuperable
  - Tareas entregadas (25%): mayor % = más recuperable
  - Calificaciones (20%): mejor promedio = más recuperable
  - Historial de matrícula (15%): menos repitencias = más recuperable
  - Tendencia de compromiso (10%): compromiso mejorando = más recuperable

El score se persiste en Student.score_recuperabilidad y se recalcula
cada vez que se ejecuta el ETL o se invoca manualmente.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from ..models.student import Student
from ..models.avac_access import AvacAccess
from ..models.enrollment import Enrollment
from ..models.course_config import SemesterConfig


# ── Pesos por defecto ──────────────────────────────────────────────
DEFAULT_WEIGHTS = {
    "actividad": 0.30,
    "tareas": 0.25,
    "calificaciones": 0.20,
    "historial": 0.15,
    "tendencia": 0.10,
}

# ── Umbrales de mapeo ──────────────────────────────────────────────
MAX_DIAS_INACTIVIDAD = 60   # >= 60 días → componente actividad = 0
MAX_REPITENCIAS = 3          # >= 3 repitencias → componente historial = 0


def _score_actividad(dias_sin_acceso: Optional[float]) -> float:
    """0-100: menos días sin acceso = mejor score."""
    if dias_sin_acceso is None:
        return 50.0  # sin datos → neutro
    if dias_sin_acceso <= 0:
        return 100.0
    if dias_sin_acceso >= MAX_DIAS_INACTIVIDAD:
        return 0.0
    return round(100.0 * (1 - dias_sin_acceso / MAX_DIAS_INACTIVIDAD), 1)


def _score_tareas(porcentaje_tareas: Optional[float]) -> float:
    """0-100: directamente proporcional al % de tareas entregadas."""
    if porcentaje_tareas is None:
        return 50.0
    return round(max(0.0, min(100.0, porcentaje_tareas)), 1)


def _score_calificaciones(promedio: Optional[float]) -> float:
    """0-100: mapea promedio (0-10 escala) a score.
    >= 7 = 100, 0 = 0, lineal entre medias."""
    if promedio is None:
        return 50.0
    if promedio >= 7.0:
        return 100.0
    if promedio <= 0:
        return 0.0
    return round(100.0 * promedio / 7.0, 1)


def _score_historial(student_id: int, db: Session) -> float:
    """0-100: basado en repitencias. Menos repitencias = más recuperable."""
    max_rep = db.query(sqlfunc.max(Enrollment.numero_repitencias)).filter(
        Enrollment.student_id == student_id
    ).scalar()
    if max_rep is None or max_rep == 0:
        return 100.0
    if max_rep >= MAX_REPITENCIAS:
        return 0.0
    return round(100.0 * (1 - max_rep / MAX_REPITENCIAS), 1)


def _score_tendencia(student_id: int, db: Session) -> float:
    """0-100: analiza si el compromiso (días sin acceso) está mejorando o
    empeorando comparando los últimos 2 snapshots.
    Mejorando (menos días) = 100, empeorando = 0, estable = 50."""
    snapshots = (
        db.query(AvacAccess.dias_sin_acceso, AvacAccess.snapshot_date)
        .filter(
            AvacAccess.student_id == student_id,
            AvacAccess.dias_sin_acceso.isnot(None),
            AvacAccess.snapshot_date.isnot(None),
        )
        .order_by(AvacAccess.snapshot_date.desc())
        .limit(3)
        .all()
    )
    if len(snapshots) < 2:
        return 50.0  # sin tendencia → neutro

    # Comparar el snapshot más reciente vs el anterior
    reciente = snapshots[0].dias_sin_acceso
    anterior = snapshots[1].dias_sin_acceso

    if anterior == 0 and reciente == 0:
        return 80.0  # consistentemente activo
    if anterior == 0:
        return 20.0  # empeoró desde activo

    delta_pct = (anterior - reciente) / max(anterior, 1)
    # delta_pct > 0 → mejorando, < 0 → empeorando
    score = 50.0 + (delta_pct * 50.0)
    return round(max(0.0, min(100.0, score)), 1)


def calcular_score_estudiante(
    student: Student,
    db: Session,
    weights: Optional[dict] = None,
) -> dict:
    """Calcula el score de recuperabilidad para un estudiante.

    Retorna dict con:
      - score_total: float 0-100
      - nivel: str "alto" | "medio" | "bajo"
      - componentes: dict con cada factor y su score individual
      - recomendacion: str con texto de acción sugerida
    """
    w = weights or DEFAULT_WEIGHTS

    comp_actividad = _score_actividad(student.dias_sin_acceso)
    comp_tareas = _score_tareas(student.porcentaje_tareas)
    comp_calif = _score_calificaciones(student.promedio_calificaciones)
    comp_historial = _score_historial(student.id, db)
    comp_tendencia = _score_tendencia(student.id, db)

    score_total = round(
        comp_actividad * w["actividad"]
        + comp_tareas * w["tareas"]
        + comp_calif * w["calificaciones"]
        + comp_historial * w["historial"]
        + comp_tendencia * w["tendencia"],
        1,
    )

    # Clasificación
    if score_total >= 65:
        nivel = "alto"
        recomendacion = "Intervención oportuna tiene alta probabilidad de éxito. Contactar al estudiante lo antes posible."
    elif score_total >= 35:
        nivel = "medio"
        recomendacion = "Recuperación posible con intervención sostenida. Priorizar seguimiento semanal."
    else:
        nivel = "bajo"
        recomendacion = "Recuperación difícil. Evaluar derivación a tutoría especializada o consejería."

    return {
        "score_total": score_total,
        "nivel": nivel,
        "componentes": {
            "actividad": {"score": comp_actividad, "peso": w["actividad"], "dias_sin_acceso": student.dias_sin_acceso},
            "tareas": {"score": comp_tareas, "peso": w["tareas"], "porcentaje": student.porcentaje_tareas},
            "calificaciones": {"score": comp_calif, "peso": w["calificaciones"], "promedio": student.promedio_calificaciones},
            "historial": {"score": comp_historial, "peso": w["historial"]},
            "tendencia": {"score": comp_tendencia, "peso": w["tendencia"]},
        },
        "recomendacion": recomendacion,
    }


def calcular_scores_batch(db: Session, weights: Optional[dict] = None) -> dict:
    """Recalcula score de recuperabilidad para TODOS los estudiantes.

    Persiste el resultado en Student.score_recuperabilidad y
    Student.nivel_recuperabilidad.

    Retorna dict con stats: total_calculados, distribucion {alto, medio, bajo}.
    """
    students = db.query(Student).all()
    stats = {"alto": 0, "medio": 0, "bajo": 0}
    total = 0

    for student in students:
        result = calcular_score_estudiante(student, db, weights)
        student.score_recuperabilidad = result["score_total"]
        student.nivel_recuperabilidad = result["nivel"]
        stats[result["nivel"]] += 1
        total += 1

    db.commit()
    return {
        "total_calculados": total,
        "distribucion": stats,
    }
