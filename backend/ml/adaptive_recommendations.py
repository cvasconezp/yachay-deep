"""
Épica 5.1: Recomendaciones Adaptativas basadas en ML

Extrae pares (perfil_estudiante + tipo_intervención → resultado) de intervenciones
cerradas, entrena un clasificador para predecir la intervención más efectiva,
y provee fallback a reglas cuando hay insuficientes datos.

Umbral: MIN_SAMPLES = 50 intervenciones cerradas con snapshot para usar ML.
"""
from __future__ import annotations

import logging
import pickle
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from ..models.student import Student
from ..models.intervention import Intervention

logger = logging.getLogger(__name__)

MIN_SAMPLES = 50
FEATURE_COLS = [
    "indice_compromiso", "dias_sin_acceso", "porcentaje_tareas",
    "prob_desercion", "prob_reprobacion", "score_recuperabilidad",
]


def _extract_training_data(db: Session) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Extrae pares (perfil → medio efectivo) de intervenciones resueltas con snapshot."""
    intervenciones = db.query(Intervention).filter(
        Intervention.estado_workflow == "resuelto",
        Intervention.medio.isnot(None),
        Intervention.snapshot_compromiso.isnot(None),
    ).all()

    if not intervenciones:
        return np.array([]), np.array([]), []

    # Obtener estudiantes
    student_ids = list({inv.student_id for inv in intervenciones if inv.student_id})
    students = db.query(Student).filter(Student.id.in_(student_ids)).all() if student_ids else []
    students_map = {s.id: s for s in students}

    X_rows = []
    y_labels = []
    medios_unicos = set()

    for inv in intervenciones:
        student = students_map.get(inv.student_id)
        if not student:
            continue

        features = [
            float(inv.snapshot_compromiso or student.indice_compromiso or 0),
            float(inv.snapshot_dias_sin_acceso or student.dias_sin_acceso or 0),
            float(inv.snapshot_porcentaje_tareas or student.porcentaje_tareas or 0),
            float(inv.snapshot_prob_desercion or student.prob_desercion or 0),
            float(inv.snapshot_prob_reprobacion or student.prob_reprobacion or 0),
            float(student.score_recuperabilidad or 50),
        ]
        X_rows.append(features)
        y_labels.append(inv.medio)
        medios_unicos.add(inv.medio)

    if not X_rows:
        return np.array([]), np.array([]), []

    return np.array(X_rows), np.array(y_labels), sorted(medios_unicos)


def train_adaptive_model(db: Session) -> dict:
    """Entrena el modelo de recomendaciones adaptativas.

    Returns dict con status, n_samples, classes, accuracy.
    """
    X, y, classes = _extract_training_data(db)

    if len(X) < MIN_SAMPLES:
        return {
            "status": "insufficient_data",
            "n_samples": len(X),
            "min_required": MIN_SAMPLES,
            "message": f"Se necesitan al menos {MIN_SAMPLES} intervenciones resueltas con snapshot. Actual: {len(X)}",
        }

    # Entrenar RandomForest
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import cross_val_score
    from sklearn.preprocessing import LabelEncoder

    le = LabelEncoder()
    y_encoded = le.fit_transform(y)

    clf = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42, n_jobs=-1)

    # Cross-validation
    if len(np.unique(y_encoded)) >= 2 and len(X) >= 10:
        n_splits = min(5, len(X) // 2)
        scores = cross_val_score(clf, X, y_encoded, cv=max(2, n_splits), scoring="accuracy")
        accuracy = float(np.mean(scores))
    else:
        accuracy = 0.0

    clf.fit(X, y_encoded)

    # Guardar modelo
    model_data = {
        "model": clf,
        "label_encoder": le,
        "feature_cols": FEATURE_COLS,
        "classes": classes,
        "n_samples": len(X),
        "accuracy": accuracy,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }

    # Persistir en memoria (se podría guardar en DB o archivo)
    _MODEL_CACHE["adaptive"] = model_data

    logger.info(f"Modelo adaptativo entrenado: {len(X)} muestras, accuracy={accuracy:.3f}, clases={classes}")

    return {
        "status": "trained",
        "n_samples": len(X),
        "classes": classes,
        "accuracy": round(accuracy, 3),
    }


# Cache en memoria del modelo
_MODEL_CACHE: dict = {}


def predict_best_intervention(student: Student, db: Session = None) -> dict:
    """Predice el medio de intervención más efectivo para un estudiante.

    Returns dict con:
      - medio_recomendado: str
      - confianza: float (0-1)
      - fuente: "ml" | "reglas"
      - alternativas: list[dict] con probabilidades por medio
    """
    model_data = _MODEL_CACHE.get("adaptive")

    # Fallback a reglas si no hay modelo entrenado
    if model_data is None:
        return _fallback_reglas(student)

    clf = model_data["model"]
    le = model_data["label_encoder"]

    features = np.array([[
        float(student.indice_compromiso or 0),
        float(student.dias_sin_acceso or 0),
        float(student.porcentaje_tareas or 0),
        float(student.prob_desercion or 0),
        float(student.prob_reprobacion or 0),
        float(student.score_recuperabilidad or 50),
    ]])

    # Predicción con probabilidades
    proba = clf.predict_proba(features)[0]
    classes = le.classes_
    pred_idx = np.argmax(proba)
    medio = le.inverse_transform([pred_idx])[0]
    confianza = float(proba[pred_idx])

    alternativas = sorted(
        [{"medio": le.inverse_transform([i])[0], "probabilidad": round(float(p), 3)} for i, p in enumerate(proba)],
        key=lambda x: x["probabilidad"], reverse=True
    )

    # Si confianza muy baja, usar fallback
    if confianza < 0.3:
        fallback = _fallback_reglas(student)
        fallback["nota"] = f"ML sugería '{medio}' con confianza {confianza:.2f}, se usó reglas por baja confianza"
        return fallback

    return {
        "medio_recomendado": medio,
        "confianza": round(confianza, 3),
        "fuente": "ml",
        "accuracy_modelo": model_data.get("accuracy", 0),
        "n_samples_entrenamiento": model_data.get("n_samples", 0),
        "alternativas": alternativas,
    }


def _fallback_reglas(student: Student) -> dict:
    """Recomendación basada en reglas cuando no hay modelo ML disponible."""
    dias = student.dias_sin_acceso or 0
    compromiso = student.indice_compromiso or 0
    tareas = student.porcentaje_tareas or 0

    if dias > 14:
        medio = "Llamada telefónica"
        razon = "Estudiante inactivo >14 días, contacto directo prioritario"
    elif dias > 7:
        medio = "WhatsApp"
        razon = "Inactividad moderada, contacto vía mensajería"
    elif compromiso < 0.3:
        medio = "Email + Tutoría"
        razon = "Compromiso muy bajo, requiere acompañamiento académico"
    elif tareas < 40:
        medio = "WhatsApp"
        razon = "Tareas atrasadas, recordatorio vía mensajería"
    else:
        medio = "Email"
        razon = "Seguimiento general"

    return {
        "medio_recomendado": medio,
        "confianza": 0.5,
        "fuente": "reglas",
        "razon": razon,
        "alternativas": [],
    }


def get_model_status() -> dict:
    """Retorna el estado actual del modelo adaptativo."""
    model_data = _MODEL_CACHE.get("adaptive")
    if not model_data:
        return {"status": "not_trained", "message": "Modelo no entrenado aún"}
    return {
        "status": "trained",
        "n_samples": model_data["n_samples"],
        "accuracy": model_data["accuracy"],
        "classes": model_data["classes"],
        "trained_at": model_data["trained_at"],
    }
