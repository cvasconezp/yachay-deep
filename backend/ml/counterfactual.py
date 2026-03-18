"""
Motor de Explicaciones Contrafactuales para Yachay Deep.

Inspirado en Dropout-Insight (DiCE framework), implementa una versión
liviana que genera escenarios "¿Qué pasaría si...?" sin depender de dice_ml.

CONCEPTO: Para un estudiante en riesgo, calcula los cambios mínimos en sus
features que reducirían su probabilidad de deserción/reprobación por debajo
del umbral de riesgo.

MÉTODO: Perturbación dirigida — modifica una feature a la vez en dirección
favorable (hacia la media de la carrera) y mide el impacto en la predicción.
Selecciona las combinaciones de cambios más eficientes.
"""
import numpy as np
import logging
from typing import Optional

from .features import FEATURE_COLUMNS

logger = logging.getLogger(__name__)

# Etiquetas legibles para las recomendaciones contrafactuales
FEATURE_ACTION_TEMPLATES = {
    "promedio_notas": "Subir el promedio de notas de {actual:.1f} a {target:.1f}",
    "num_reprobadas": "Reducir materias reprobadas de {actual:.0f} a {target:.0f}",
    "pct_reprobadas": "Reducir el porcentaje de reprobadas de {actual:.0f}% a {target:.0f}%",
    "nota_min": "Mejorar la nota mínima de {actual:.1f} a {target:.1f}",
    "nota_max": "Mantener o subir la nota máxima a {target:.1f}",
    "std_notas": "Reducir la dispersión de notas (más consistencia) de {actual:.1f} a {target:.1f}",
    "num_zeros": "Eliminar materias con nota cero: de {actual:.0f} a {target:.0f}",
    "num_asignaturas": "Ajustar la carga académica a {target:.0f} materias",
}


def generate_counterfactual(
    predictor,
    student_features: dict,
    model_key: str,
    target_type: str = "desercion",
    target_prob: float = 0.30,
    max_changes: int = 3,
) -> Optional[dict]:
    """
    Genera un escenario contrafactual: "¿Qué cambios mínimos reducirían
    el riesgo por debajo de target_prob?"

    Args:
        predictor: Predictor instance con modelos cargados
        student_features: dict con las 8 features del estudiante
        model_key: key del modelo de la carrera
        target_type: "desercion" o "reprobacion"
        target_prob: probabilidad objetivo (default 0.30 = riesgo bajo)
        max_changes: máximo de features a modificar

    Returns:
        dict con:
          - factible: bool — si se encontró un escenario viable
          - prob_original: float
          - prob_contrafactual: float
          - cambios: list[{feature, actual, target, accion}]
          - features_originales: dict
          - features_contrafactuales: dict
    """
    models = predictor.models.get(model_key) or predictor.models.get("global", {})
    model = models.get(target_type)
    if model is None:
        return None

    # Stats de la carrera para saber "hacia dónde mover"
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

    # Estrategia: probar mover cada feature hacia la media de la carrera
    # y medir cuál reduce más la probabilidad
    impacts = []
    for col in FEATURE_COLUMNS:
        actual = student_features.get(col, 0)
        media = means.get(col, actual)

        # Determinar dirección favorable
        X_test = X_original.copy()
        col_idx = FEATURE_COLUMNS.index(col)

        # Mover hacia la media (o mejor que la media si ya está cerca)
        if col in ("num_reprobadas", "pct_reprobadas", "num_zeros", "std_notas"):
            # Para estos, "mejor" = más bajo
            target_val = min(actual, media * 0.7)  # 30% mejor que la media
        elif col in ("promedio_notas", "nota_min", "nota_max"):
            # Para estos, "mejor" = más alto
            target_val = max(actual, media * 1.15)  # 15% mejor que la media
        else:
            target_val = media  # mover hacia la media

        if abs(actual - target_val) < 0.01:
            continue  # no hay cambio significativo

        X_test[0, col_idx] = target_val
        prob_after = float(model.predict_proba(X_test)[0, 1])
        delta = prob_original - prob_after  # positivo = mejora

        if delta > 0.01:  # solo considerar cambios que mejoran al menos 1%
            impacts.append({
                "feature": col,
                "actual": round(actual, 2),
                "target": round(target_val, 2),
                "delta_prob": round(delta, 4),
                "prob_after": round(prob_after, 4),
            })

    # Ordenar por impacto descendente
    impacts.sort(key=lambda x: x["delta_prob"], reverse=True)

    # Seleccionar los top-N cambios más impactantes
    selected = impacts[:max_changes]

    if not selected:
        return {
            "factible": False,
            "prob_original": round(prob_original, 4),
            "mensaje": "No se encontraron cambios que reduzcan significativamente el riesgo",
        }

    # Calcular probabilidad con todos los cambios combinados
    X_cf = X_original.copy()
    cambios = []
    for s in selected:
        col_idx = FEATURE_COLUMNS.index(s["feature"])
        X_cf[0, col_idx] = s["target"]

        template = FEATURE_ACTION_TEMPLATES.get(s["feature"], "{feature}: de {actual} a {target}")
        accion = template.format(actual=s["actual"], target=s["target"])

        cambios.append({
            "feature": s["feature"],
            "actual": s["actual"],
            "target": s["target"],
            "impacto_individual": s["delta_prob"],
            "accion": accion,
        })

    prob_cf = float(model.predict_proba(X_cf)[0, 1])

    return {
        "factible": prob_cf < target_prob,
        "prob_original": round(prob_original, 4),
        "prob_contrafactual": round(prob_cf, 4),
        "reduccion_total": round(prob_original - prob_cf, 4),
        "target_prob": target_prob,
        "cambios": cambios,
        "features_originales": {c: round(student_features.get(c, 0), 2) for c in FEATURE_COLUMNS},
        "features_contrafactuales": {FEATURE_COLUMNS[i]: round(float(X_cf[0, i]), 2) for i in range(len(FEATURE_COLUMNS))},
    }
