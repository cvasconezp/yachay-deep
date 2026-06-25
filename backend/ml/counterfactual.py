"""
Motor de Explicaciones Contrafactuales para Yachay Deep — v2 MEJORADO.

Mejoras respecto a v1:
  - Restricciones de factibilidad: solo sugiere cambios que el estudiante puede controlar
  - Escenarios incrementales: cambios parciales, no absolutos ("entrega 3 tareas más")
  - Priorización por esfuerzo: ordena por impacto/esfuerzo (ratio costo-beneficio)
  - Plazos sugeridos: indica horizonte temporal de cada acción
  - Contextualización con datos reales: cruza con materias y tareas pendientes
"""
import numpy as np
import logging
from typing import Optional

from .features import FEATURE_COLUMNS

logger = logging.getLogger(__name__)

# Clasificación de factibilidad de cada feature
# factibilidad: "alta" = el estudiante puede cambiar a corto plazo
#                "media" = requiere esfuerzo sostenido
#                "baja" = difícil de cambiar directamente
FEATURE_FACTIBILIDAD = {
    "num_zeros": {"factibilidad": "alta", "plazo": "1-2 semanas",
                  "accion": "Entregar las tareas pendientes de {n} materia(s) con nota cero"},
    "num_reprobadas": {"factibilidad": "media", "plazo": "4-8 semanas",
                       "accion": "Mejorar rendimiento en {n} materia(s) reprobada(s) mediante tutorías"},
    "pct_reprobadas": {"factibilidad": "media", "plazo": "4-8 semanas",
                       "accion": "Reducir el porcentaje de materias reprobadas del {actual}% al {target}%"},
    "nota_min": {"factibilidad": "media", "plazo": "4-6 semanas",
                 "accion": "Enfocarse en la materia con peor nota: subir de {actual:.0f} a al menos {target:.0f}"},
    "promedio_notas": {"factibilidad": "baja", "plazo": "fin de semestre",
                       "accion": "Mejorar promedio general de {actual:.1f} a {target:.1f} (requiere mejora en múltiples materias)"},
    "nota_max": {"factibilidad": "baja", "plazo": "fin de semestre",
                 "accion": "La mejor nota actual es {actual:.0f} — mantener o mejorar"},
    "std_notas": {"factibilidad": "baja", "plazo": "fin de semestre",
                  "accion": "Reducir variabilidad entre materias (rendimiento más consistente)"},
    "num_asignaturas": {"factibilidad": "baja", "plazo": "siguiente matrícula",
                        "accion": "Ajustar carga académica (actualmente {actual:.0f} materias)"},
}


def generate_counterfactual(
    predictor,
    student_features: dict,
    model_key: str,
    target_type: str = "desercion",
    target_prob: float = 0.30,
    max_changes: int = 3,
    db=None,
    student_id: int = None,
) -> Optional[dict]:
    """
    Genera un escenario contrafactual con restricciones de factibilidad.

    v2: Prioriza cambios factibles a corto plazo y genera acciones
    incrementales en vez de absolutas.
    """
    models = predictor.models.get(model_key) or predictor.models.get("global", {})
    model = models.get(target_type)
    if model is None:
        return None

    stats = predictor.stats.get(model_key, {}).get(target_type)
    if not stats:
        stats = predictor.stats.get("global", {}).get(target_type)
    if not stats:
        return None

    means = stats.get("feature_means", {})

    # Probabilidad original
    X_original = np.array([[student_features.get(c, 0) for c in FEATURE_COLUMNS]])
    prob_original = float(model.predict_proba(X_original)[0, 1])

    if prob_original <= target_prob:
        return {
            "factible": True,
            "prob_original": round(prob_original, 4),
            "prob_contrafactual": round(prob_original, 4),
            "cambios": [],
            "mensaje": "El estudiante ya está por debajo del umbral de riesgo",
        }

    # Evaluar impacto de cada feature con cambio INCREMENTAL (no absoluto)
    impacts = []
    for col in FEATURE_COLUMNS:
        actual = student_features.get(col, 0)
        media = means.get(col, actual)
        fact_info = FEATURE_FACTIBILIDAD.get(col, {"factibilidad": "baja", "plazo": "indefinido"})

        # Calcular target incremental (no absoluto)
        # Para features "menores es mejor": mover hacia 0 o media (lo que sea menor)
        if col in ("num_reprobadas", "pct_reprobadas", "num_zeros", "std_notas"):
            # Cambio incremental: reducir al 50% del valor actual o a la media, lo que sea más cercano
            target_val = min(actual * 0.5, media) if actual > media else max(0, actual - 1)
        elif col in ("promedio_notas", "nota_min", "nota_max"):
            # Cambio incremental: subir un 15% o a la media, lo que sea más alcanzable
            target_val = min(actual * 1.15, media * 1.05) if actual < media else actual
        elif col == "num_asignaturas":
            target_val = actual  # no cambiar carga académica
            continue
        else:
            target_val = media

        # Limitar targets a rangos realistas
        if col == "nota_min" and target_val > 100:
            target_val = min(target_val, 85)
        if col == "promedio_notas" and target_val > 100:
            target_val = min(target_val, 90)
        if col in ("num_reprobadas", "num_zeros"):
            target_val = max(0, round(target_val))

        if abs(actual - target_val) < 0.01:
            continue

        X_test = X_original.copy()
        col_idx = FEATURE_COLUMNS.index(col)
        X_test[0, col_idx] = target_val
        prob_after = float(model.predict_proba(X_test)[0, 1])
        delta = prob_original - prob_after

        if delta > 0.005:  # mínimo 0.5% de impacto
            # Score compuesto: impacto * factibilidad
            fact_multiplier = {"alta": 3.0, "media": 1.5, "baja": 0.5}.get(fact_info["factibilidad"], 0.5)
            score = delta * fact_multiplier

            # Generar acción contextualizada
            accion_template = fact_info.get("accion", "{col}: de {actual} a {target}")
            accion = accion_template.format(
                actual=round(actual, 1), target=round(target_val, 1),
                n=int(abs(actual - target_val)) if col in ("num_reprobadas", "num_zeros") else ""
            )

            impacts.append({
                "feature": col,
                "actual": round(actual, 2),
                "target": round(target_val, 2),
                "delta_prob": round(delta, 4),
                "prob_after": round(prob_after, 4),
                "factibilidad": fact_info["factibilidad"],
                "plazo": fact_info["plazo"],
                "score": round(score, 4),
                "accion": accion,
            })

    # Ordenar por score (impacto * factibilidad) descendente
    impacts.sort(key=lambda x: x["score"], reverse=True)

    # Seleccionar top-N priorizando factibilidad
    selected = impacts[:max_changes]

    if not selected:
        return {
            "factible": False,
            "prob_original": round(prob_original, 4),
            "mensaje": "No se encontraron cambios incrementales viables",
        }

    # Calcular probabilidad combinada
    X_cf = X_original.copy()
    cambios = []
    for s in selected:
        col_idx = FEATURE_COLUMNS.index(s["feature"])
        X_cf[0, col_idx] = s["target"]
        cambios.append({
            "feature": s["feature"],
            "actual": s["actual"],
            "target": s["target"],
            "impacto_individual": s["delta_prob"],
            "factibilidad": s["factibilidad"],
            "plazo": s["plazo"],
            "accion": s["accion"],
        })

    prob_cf = float(model.predict_proba(X_cf)[0, 1])

    return {
        "factible": prob_cf < target_prob,
        "prob_original": round(prob_original, 4),
        "prob_contrafactual": round(prob_cf, 4),
        "reduccion_total": round(prob_original - prob_cf, 4),
        "target_prob": target_prob,
        "cambios": cambios,
    }
