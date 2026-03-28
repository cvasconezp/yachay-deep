"""
Endpoints de prediccion ML — Fases 2-4 del Framework Yachay Deep.
Permite entrenar modelos, ejecutar predicciones, consultar estado
y generar recomendaciones automáticas de intervención.
"""
import logging
import threading
import time as _time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db, SessionLocal
from ..auth.jwt import get_current_user
from ..models.user import User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predictions", tags=["predictions"])

# ── Estado de tareas en background (train/predict) ──
_bg_task: dict = {"running": False, "type": None, "started": None, "result": None, "error": None}


def _require_admin(user: User):
    if user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Solo administradores")


def _run_train_in_background():
    """Ejecuta entrenamiento en un hilo separado para evitar timeout HTTP."""
    db = SessionLocal()
    try:
        from ..ml.train import train_models
        result = train_models(db)
        _bg_task["result"] = result
        _bg_task["error"] = None

        # Recargar el singleton del Predictor para que get_status() refleje los nuevos modelos
        if result.get("status") == "ok":
            try:
                from ..ml.predict import Predictor
                predictor = Predictor.get_instance()
                predictor.reset()
                predictor.load_models()
                logger.info("Predictor recargado con modelos recién entrenados")
            except Exception as e:
                logger.warning("No se pudo recargar Predictor: %s", e)

        logger.info("Entrenamiento en background completado: %s", result.get("status"))
    except Exception as e:
        _bg_task["result"] = None
        _bg_task["error"] = str(e)
        logger.error("Error en entrenamiento background: %s", e)
    finally:
        db.close()
        _bg_task["running"] = False


def _run_predict_in_background():
    """Ejecuta predicciones en un hilo separado para evitar timeout HTTP."""
    db = SessionLocal()
    try:
        from ..ml.predict import Predictor
        predictor = Predictor.get_instance()

        # Auto-reentrenar si no hay modelos cargados
        if not predictor.is_loaded and not predictor.load_models():
            from ..ml.train import train_models
            train_result = train_models(db)
            if train_result.get("status") != "ok":
                _bg_task["result"] = {"status": "error", "message": "No se pudo entrenar", "detail": train_result}
                return
            predictor.reset()
            predictor.load_models()

        result = predictor.predict_batch(db)
        _bg_task["result"] = result
        _bg_task["error"] = None
        logger.info("Predicciones en background completadas: %s", result.get("status"))
    except Exception as e:
        _bg_task["result"] = None
        _bg_task["error"] = str(e)
        logger.error("Error en predicciones background: %s", e)
    finally:
        db.close()
        _bg_task["running"] = False


@router.post("/train")
def train_model(
    current_user: User = Depends(get_current_user),
):
    """Reentrena los modelos predictivos en background."""
    _require_admin(current_user)

    if _bg_task["running"]:
        return {"status": "already_running", "type": _bg_task["type"], "started": _bg_task["started"]}

    _bg_task.update({"running": True, "type": "train", "started": _time.time(), "result": None, "error": None})
    threading.Thread(target=_run_train_in_background, daemon=True).start()
    return {"status": "started", "message": "Entrenamiento iniciado en background. Consulta /predictions/task-status para ver progreso."}


@router.post("/run")
def run_predictions(
    current_user: User = Depends(get_current_user),
):
    """Ejecuta predicciones en background para todos los estudiantes."""
    _require_admin(current_user)

    if _bg_task["running"]:
        return {"status": "already_running", "type": _bg_task["type"], "started": _bg_task["started"]}

    _bg_task.update({"running": True, "type": "predict", "started": _time.time(), "result": None, "error": None})
    threading.Thread(target=_run_predict_in_background, daemon=True).start()
    return {"status": "started", "message": "Predicciones iniciadas en background. Consulta /predictions/task-status para ver progreso."}


@router.get("/task-status")
def task_status(current_user: User = Depends(get_current_user)):
    """Estado de la tarea en background (train o predict)."""
    elapsed = round(_time.time() - _bg_task["started"], 1) if _bg_task["started"] else None
    return {
        "running": _bg_task["running"],
        "type": _bg_task["type"],
        "elapsed_seconds": elapsed,
        "result": _bg_task["result"],
        "error": _bg_task["error"],
    }


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

    # Contrafactual conductual (siempre disponible, basado en compromiso)
    from ..ml.counterfactual_conductual import generate_behavioral_counterfactual
    cf_conductual = generate_behavioral_counterfactual(db, student_id)

    return {
        "student_id": student_id,
        "target_prob": target_prob,
        "contrafactual_desercion": cf_desercion,
        "contrafactual_reprobacion": cf_reprobacion,
        "contrafactual_conductual": cf_conductual,
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


@router.post("/notify-tutoria")
def notify_tutoria(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Envía notificación de tutoría al estudiante y al docente por email.
    Registra automáticamente una intervención con los datos de la tutoría.

    Body: {student_id, asignatura, docente, motivo}
    """
    from ..models.student import Student
    from ..models.intervention import Intervention

    student_id = payload.get("student_id")
    asignatura = payload.get("asignatura", "")
    docente = payload.get("docente", "")
    motivo = payload.get("motivo", "")

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")

    # Registrar intervención automática
    intervention = Intervention(
        student_id=student_id,
        monitor_id=current_user.id,
        monitor_nombre=current_user.nombre,
        carrera=student.carrera,
        medio="Tutoría",
        motivo=f"Convocatoria a tutoría — {asignatura}",
        estado="Convocado",
        asignatura=asignatura,
        docente=docente,
        observacion=f"Tutoría recomendada por sistema contrafactual. Motivo: {motivo}. Notificación enviada a estudiante y docente.",
        resultado="Pendiente de asistencia",
        requiere_seguimiento="si",
        snapshot_compromiso=student.indice_compromiso,
        snapshot_dias_sin_acceso=student.dias_sin_acceso,
        snapshot_porcentaje_tareas=student.porcentaje_tareas,
        snapshot_prob_desercion=student.prob_desercion,
        snapshot_prob_reprobacion=student.prob_reprobacion,
        snapshot_nivel_riesgo=student.nivel_riesgo,
    )
    db.add(intervention)
    db.commit()
    db.refresh(intervention)

    # Enviar emails
    email_enviado = False
    try:
        from ..services.email import send_tutoria_notification
        email_enviado = send_tutoria_notification(
            student_data={
                "nombre": student.nombre,
                "correo": student.correo,
                "correo_institucional": student.correo_institucional,
                "carrera": student.carrera,
            },
            asignatura=asignatura,
            docente=docente,
            motivo=motivo,
            monitor_nombre=current_user.nombre,
        )
    except Exception as e:
        logger.warning(f"Error enviando notificación de tutoría: {e}")

    return {
        "status": "ok",
        "intervention_id": intervention.id,
        "email_enviado": email_enviado,
        "mensaje": f"Tutoría de {asignatura} notificada. Intervención #{intervention.id} creada.",
    }
