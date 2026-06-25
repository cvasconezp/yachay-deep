"""
Épica 5.2a: SHAP Explainability

Integra SHAP (TreeExplainer para RF) para explicaciones individuales reales,
reemplazando la comparación simple con media.
"""
from __future__ import annotations

import logging
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)


def compute_shap_explanation(model, feature_names: list[str], instance: np.ndarray, target_idx: int = 1) -> dict:
    """Calcula explicación SHAP para una instancia individual.

    Args:
        model: modelo sklearn entrenado (RF, GBT, LR)
        feature_names: lista de nombres de features
        instance: array 1D o 2D con los valores de features
        target_idx: índice de la clase objetivo (1 = riesgo alto)

    Returns:
        dict con shap_values, feature_importance, top_factors
    """
    try:
        import shap
    except ImportError:
        logger.warning("SHAP no disponible, usando fallback de feature importance")
        return _fallback_feature_importance(model, feature_names, instance)

    instance = np.atleast_2d(instance)

    try:
        # Intentar TreeExplainer (para RF, GBT)
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(instance)

        # Para clasificación binaria, shap_values es lista de 2 arrays
        if isinstance(shap_values, list):
            values = shap_values[target_idx][0]
        else:
            values = shap_values[0]

    except Exception:
        try:
            # Fallback a LinearExplainer
            explainer = shap.LinearExplainer(model, instance)
            shap_values = explainer.shap_values(instance)
            values = shap_values[0] if isinstance(shap_values, list) else shap_values[0]
        except Exception:
            return _fallback_feature_importance(model, feature_names, instance)

    # Construir resultado
    factors = []
    for name, val in zip(feature_names, values):
        factors.append({
            "feature": name,
            "shap_value": round(float(val), 4),
            "impact": "aumenta_riesgo" if val > 0 else "reduce_riesgo",
            "magnitude": round(abs(float(val)), 4),
        })

    factors.sort(key=lambda x: x["magnitude"], reverse=True)

    return {
        "method": "shap",
        "shap_values": {name: round(float(v), 4) for name, v in zip(feature_names, values)},
        "top_factors": factors[:5],
        "all_factors": factors,
    }


def _fallback_feature_importance(model, feature_names: list[str], instance: np.ndarray) -> dict:
    """Fallback usando feature importance del modelo cuando SHAP no está disponible."""
    try:
        importances = model.feature_importances_
    except AttributeError:
        try:
            importances = np.abs(model.coef_[0])
        except (AttributeError, IndexError):
            importances = np.ones(len(feature_names)) / len(feature_names)

    instance = np.atleast_2d(instance)
    factors = []
    for name, imp, val in zip(feature_names, importances, instance[0]):
        factors.append({
            "feature": name,
            "importance": round(float(imp), 4),
            "value": round(float(val), 4),
            "magnitude": round(float(imp), 4),
        })

    factors.sort(key=lambda x: x["magnitude"], reverse=True)

    return {
        "method": "feature_importance",
        "feature_importances": {name: round(float(imp), 4) for name, imp in zip(feature_names, importances)},
        "top_factors": factors[:5],
        "all_factors": factors,
    }
