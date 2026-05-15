"""
Endpoints para Fase 5 — ML Avanzado

- Recomendaciones adaptativas (Épica 5.1)
- SHAP explainability (Épica 5.2a)
- Clustering de perfiles (Épica 5.2b)
- Estado del modelo adaptativo
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..models.student import Student
from ..auth.jwt import get_current_user

router = APIRouter(prefix="/ml", tags=["ml-advanced"])


@router.post("/adaptive/train")
def train_adaptive(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Entrena el modelo de recomendaciones adaptativas."""
    if current_user.role != "admin":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Solo admin puede entrenar modelos")
    from ..ml.adaptive_recommendations import train_adaptive_model
    return train_adaptive_model(db)


@router.get("/adaptive/status")
def adaptive_status(current_user=Depends(get_current_user)):
    """Estado del modelo de recomendaciones adaptativas."""
    from ..ml.adaptive_recommendations import get_model_status
    return get_model_status()


@router.get("/adaptive/predict/{student_id}")
def adaptive_predict(
    student_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Predice la mejor intervención para un estudiante."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    from ..ml.adaptive_recommendations import predict_best_intervention
    return predict_best_intervention(student, db)


@router.get("/explain/{student_id}")
def explain_prediction(
    student_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Explicación SHAP/feature importance para la predicción de un estudiante."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")

    # Cargar modelo y features
    import numpy as np
    from ..ml.explainability import compute_shap_explanation

    # Intentar cargar modelo de la BD o archivo
    try:
        from ..ml.predict import _load_model
        model, feature_names = _load_model(student.carrera)
    except Exception:
        return {"error": "No hay modelo entrenado disponible", "method": "none"}

    if model is None:
        return {"error": "No hay modelo entrenado disponible", "method": "none"}

    # Construir instancia de features
    from ..ml.features import build_current_features
    try:
        df = build_current_features(db)
        row = df[df["student_id"] == student_id]
        if row.empty:
            return {"error": "Sin features calculadas para este estudiante", "method": "none"}
        instance = row[feature_names].values[0]
    except Exception as e:
        return {"error": f"Error construyendo features: {str(e)}", "method": "none"}

    return compute_shap_explanation(model, feature_names, instance)


@router.post("/clustering/run")
def run_clustering_endpoint(
    n_clusters: int = Query(5, ge=3, le=7),
    periodo: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Ejecuta K-Means clustering sobre estudiantes."""
    if current_user.role != "admin":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Solo admin puede ejecutar clustering")
    from ..ml.clustering import run_clustering
    return run_clustering(db, n_clusters=n_clusters, periodo=periodo)


@router.get("/clustering/status")
def clustering_status(current_user=Depends(get_current_user)):
    """Estado del último clustering."""
    from ..ml.clustering import get_cluster_status
    return get_cluster_status()
