"""
Endpoints de prediccion ML — Fases 2-4 del Framework Yachay Deep.
Permite entrenar modelos, ejecutar predicciones, consultar estado
y generar recomendaciones automáticas de intervención.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth.jwt import get_current_user
from ..models.user import User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predictions", tags=["predictions"])


def _require_admin(user: User):
    if user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Solo administradores")


@router.post("/train")
def train_model(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reentrena los modelos predictivos con datos historicos."""
    _require_admin(current_user)

    from ..ml.train import train_models
    result = train_models(db)
    return result


@router.post("/run")
def run_predictions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Ejecuta predicciones para todos los estudiantes del semestre actual.
    Si no hay modelos entrenados (ej. después de un redeploy en Railway),
    reentrena automáticamente antes de predecir.
    """
    _require_admin(current_user)

    from ..ml.predict import Predictor
    predictor = Predictor.get_instance()

    # Auto-reentrenar si no hay modelos cargados
    if not predictor.is_loaded and not predictor.load_models():
        from ..ml.train import train_models
        train_result = train_models(db)
        if train_result.get("status") != "ok":
            return {"status": "error", "message": "No se pudo entrenar el modelo", "train_detail": train_result}
        # Recargar modelos recién entrenados
        predictor.reset()
        predictor.load_models()

    result = predictor.predict_batch(db)
    if result.get("status") == "error" and "No hay modelos" in result.get("message", ""):
        result["hint"] = "No hay datos históricos suficientes para entrenar. Ejecute primero el ETL con datos del TableauHistorico."
    return result


@router.get("/status")
def prediction_status(
    current_user: User = Depends(get_current_user),
):
    """Estado del modelo predictivo (cargado, metricas, fecha)."""
    from ..ml.predict import Predictor
    predictor = Predictor.get_instance()
    return predictor.get_status()


@router.get("/student/{student_id}")
def predict_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Prediccion individual con features detalladas."""
    from ..ml.predict import Predictor
    predictor = Predictor.get_instance()
    result = predictor.predict_single(db, student_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Sin datos para predecir")
    return result


@router.get("/student/{student_id}/recommendations")
def get_recommendations(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Genera recomendaciones automáticas de intervención (Fase 4)."""
    from ..ml.predict import Predictor
    from ..ml.recommendations import generate_recommendations

    # Obtener datos XAI si el modelo está cargado
    xai_data = None
    try:
        predictor = Predictor.get_instance()
        xai_data = predictor.predict_single(db, student_id)
    except Exception as e:
        logger.warning("XAI prediction failed for student %s: %s", student_id, e)

    recs = generate_recommendations(db, student_id, xai_data)
    return {"student_id": student_id, "recommendations": recs, "total": len(recs)}


@router.get("/student/{student_id}/counterfactual")
def get_counterfactual(
    student_id: int,
    target: str = "desercion",
    target_prob: float = 0.30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    [Dropout-Insight] Genera escenarios contrafactuales:
    "¿Qué cambios mínimos reducirian el riesgo de este estudiante?"

    Inspirado en DiCE (Diverse Counterfactual Explanations) del repo
    Dropout-Insight, adaptado para el stack de Yachay Deep sin dependencia
    externa de dice_ml.

    Args:
        target: "desercion" o "reprobacion"
        target_prob: probabilidad objetivo (default 0.30)
    """
    from ..ml.predict import Predictor
    from ..ml.counterfactual import generate_counterfactual

    predictor = Predictor.get_instance()
    if not predictor.is_loaded and not predictor.load_models():
        raise HTTPException(status_code=503, detail="Modelos no disponibles")

    result = predictor.predict_single(db, student_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Sin datos para generar contrafactual")

    model_key = result.get("model_used", "global")
    features = result.get("features", {})

    cf_desercion = None
    cf_reprobacion = None

    if target in ("desercion", "ambos"):
        cf_desercion = generate_counterfactual(
            predictor, features, model_key, "desercion", target_prob
        )
    if target in ("reprobacion", "ambos"):
        cf_reprobacion = generate_counterfactual(
            predictor, features, model_key, "reprobacion", target_prob
        )

    return {
        "student_id": student_id,
        "target_prob": target_prob,
        "contrafactual_desercion": cf_desercion,
        "contrafactual_reprobacion": cf_reprobacion,
    }


@router.post("/student/{student_id}/what-if")
def what_if_analysis(
    student_id: int,
    changes: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    [Dropout-Insight] Análisis What-If:
    "Si cambio estas variables del estudiante, ¿cómo cambia la predicción?"

    El tutor puede explorar escenarios modificando features manualmente.

    Body: {"promedio_notas": 75.0, "num_reprobadas": 1, ...}
    Solo enviar las features que se quieren modificar.
    """
    from ..ml.predict import Predictor
    from ..ml.features import FEATURE_COLUMNS
    import numpy as np

    predictor = Predictor.get_instance()
    if not predictor.is_loaded and not predictor.load_models():
        raise HTTPException(status_code=503, detail="Modelos no disponibles")

    result = predictor.predict_single(db, student_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Sin datos")

    features_original = result.get("features", {})
    model_key = result.get("model_used", "global")
    models = predictor.models.get(model_key) or predictor.models.get("global", {})

    # Aplicar cambios del usuario
    features_modified = features_original.copy()
    for key, value in changes.items():
        if key in FEATURE_COLUMNS:
            features_modified[key] = float(value)

    X_mod = np.array([[features_modified.get(c, 0) for c in FEATURE_COLUMNS]])

    resultado = {
        "student_id": student_id,
        "features_originales": features_original,
        "features_modificadas": features_modified,
        "cambios_aplicados": {k: v for k, v in changes.items() if k in FEATURE_COLUMNS},
    }

    if "desercion" in models:
        prob_orig = result.get("prob_desercion", 0)
        prob_new = round(float(models["desercion"].predict_proba(X_mod)[0, 1]), 4)
        resultado["desercion"] = {
            "prob_original": prob_orig,
            "prob_modificada": prob_new,
            "cambio": round(prob_new - prob_orig, 4),
            "mejoro": prob_new < prob_orig,
        }

    if "reprobacion" in models:
        prob_orig = result.get("prob_reprobacion", 0)
        prob_new = round(float(models["reprobacion"].predict_proba(X_mod)[0, 1]), 4)
        resultado["reprobacion"] = {
            "prob_original": prob_orig,
            "prob_modificada": prob_new,
            "cambio": round(prob_new - prob_orig, 4),
            "mejoro": prob_new < prob_orig,
        }

    return resultado
