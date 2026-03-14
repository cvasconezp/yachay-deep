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
