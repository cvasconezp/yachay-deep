"""
Predictor singleton — carga modelos entrenados y ejecuta predicciones
para estudiantes del semestre actual.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
from sqlalchemy.orm import Session

from .features import build_current_features, FEATURE_COLUMNS

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent / "models"


class Predictor:
    _instance = None

    def __init__(self):
        self.model_desercion = None
        self.model_reprobacion = None
        self.metadata = None
        self._loaded = False

    @classmethod
    def get_instance(cls) -> "Predictor":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_models(self) -> bool:
        """Carga modelos desde disco. Retorna True si al menos uno se cargo."""
        des_path = MODELS_DIR / "desercion.joblib"
        rep_path = MODELS_DIR / "reprobacion.joblib"
        meta_path = MODELS_DIR / "metadata.json"

        loaded_any = False

        if des_path.exists():
            self.model_desercion = joblib.load(des_path)
            loaded_any = True
            logger.info("Modelo de desercion cargado")

        if rep_path.exists():
            self.model_reprobacion = joblib.load(rep_path)
            loaded_any = True
            logger.info("Modelo de reprobacion cargado")

        if meta_path.exists():
            self.metadata = json.loads(meta_path.read_text())

        self._loaded = loaded_any
        return loaded_any

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def get_status(self) -> dict:
        """Estado actual del predictor."""
        if not self._loaded:
            self.load_models()

        meta_path = MODELS_DIR / "metadata.json"
        if meta_path.exists():
            metadata = json.loads(meta_path.read_text())
        else:
            metadata = None

        return {
            "loaded": self._loaded,
            "has_desercion": self.model_desercion is not None,
            "has_reprobacion": self.model_reprobacion is not None,
            "metadata": metadata,
        }

    def predict_batch(self, db: Session) -> dict:
        """
        Ejecuta predicciones para todos los estudiantes del semestre actual.
        Actualiza Student.prob_desercion, prob_reprobacion, prediccion_updated_at.
        """
        if not self._loaded:
            if not self.load_models():
                return {"status": "error", "message": "No hay modelos entrenados"}

        features_df = build_current_features(db)
        if features_df.empty:
            return {"status": "error", "message": "No hay calificaciones del semestre actual"}

        from ..models.student import Student

        X = features_df[FEATURE_COLUMNS].values
        student_ids = features_df["student_id"].values

        # Predicciones
        prob_des = None
        prob_rep = None

        if self.model_desercion is not None:
            prob_des = self.model_desercion.predict_proba(X)[:, 1]

        if self.model_reprobacion is not None:
            prob_rep = self.model_reprobacion.predict_proba(X)[:, 1]

        # Actualizar BD
        now = datetime.now(timezone.utc)
        updated = 0

        for i, sid in enumerate(student_ids):
            student = db.query(Student).filter(Student.id == int(sid)).first()
            if not student:
                continue

            if prob_des is not None:
                student.prob_desercion = round(float(prob_des[i]), 4)
            if prob_rep is not None:
                student.prob_reprobacion = round(float(prob_rep[i]), 4)
            student.prediccion_updated_at = now
            updated += 1

        db.commit()

        logger.info(f"Predicciones actualizadas para {updated} estudiantes")
        return {
            "status": "ok",
            "updated": updated,
            "total_features": len(features_df),
            "timestamp": now.isoformat(),
        }

    def predict_single(self, db: Session, student_id: int) -> Optional[dict]:
        """Prediccion individual con features detalladas."""
        if not self._loaded:
            if not self.load_models():
                return None

        from sqlalchemy import text
        query = text("""
            SELECT g.nota_final FROM grades g
            WHERE g.student_id = :sid AND g.periodo IS NULL
        """)
        rows = db.execute(query, {"sid": student_id}).fetchall()
        if not rows:
            return None

        import pandas as pd
        notas = [float(r[0]) if r[0] is not None else 0.0 for r in rows]
        notas_arr = np.array(notas)

        features = {
            "promedio_notas": float(notas_arr.mean()),
            "num_asignaturas": len(notas),
            "num_reprobadas": int((notas_arr < 70).sum()),
            "pct_reprobadas": float((notas_arr < 70).mean()),
            "nota_min": float(notas_arr.min()),
            "nota_max": float(notas_arr.max()),
            "std_notas": float(notas_arr.std()) if len(notas) > 1 else 0.0,
            "num_zeros": int((notas_arr == 0).sum()),
        }

        X = np.array([[features[c] for c in FEATURE_COLUMNS]])

        result = {"features": features}

        if self.model_desercion is not None:
            result["prob_desercion"] = round(float(self.model_desercion.predict_proba(X)[0, 1]), 4)
        if self.model_reprobacion is not None:
            result["prob_reprobacion"] = round(float(self.model_reprobacion.predict_proba(X)[0, 1]), 4)

        return result
