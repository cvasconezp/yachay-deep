"""
Predictor — carga modelos entrenados (por carrera + global) y ejecuta
predicciones para estudiantes del semestre actual.
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


FEATURE_LABELS = {
    "promedio_notas": "Promedio de notas",
    "num_asignaturas": "Cantidad de materias",
    "num_reprobadas": "Materias reprobadas",
    "pct_reprobadas": "Porcentaje reprobadas",
    "nota_min": "Nota mínima",
    "nota_max": "Nota máxima",
    "std_notas": "Dispersión de notas",
    "num_zeros": "Materias con nota cero",
    # [GAP-F2-01] Features conductuales
    "dias_sin_acceso": "Días sin acceso al AVAC",
    "porcentaje_tareas": "Porcentaje de tareas entregadas",
    "indice_compromiso": "Índice de compromiso académico",
}


class Predictor:
    _instance = None

    def __init__(self):
        self.models = {}  # key -> {"desercion": model, "reprobacion": model}
        self.stats = {}   # key -> {"desercion": stats_dict, "reprobacion": stats_dict}
        self.carrera_mapping = {}  # carrera -> key
        self.metadata = None
        self._loaded = False

    @classmethod
    def get_instance(cls) -> "Predictor":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_models(self) -> bool:
        """
        Carga modelos con prioridad:
          1. Disco local (rápido, pero se pierde en redeploys)
          2. PostgreSQL (persistente, [GAP-F2-02])
        """
        meta_path = MODELS_DIR / "metadata.json"
        mapping_path = MODELS_DIR / "carrera_mapping.json"

        if meta_path.exists():
            self.metadata = json.loads(meta_path.read_text(encoding="utf-8"))

        if mapping_path.exists():
            self.carrera_mapping = json.loads(mapping_path.read_text(encoding="utf-8"))

        loaded_any = False

        # 1) Intentar cargar desde disco
        for joblib_file in MODELS_DIR.glob("*.joblib"):
            name = joblib_file.stem
            try:
                model = joblib.load(joblib_file)
            except (EOFError, Exception) as e:
                logger.warning(f"Archivo de modelo corrupto, ignorando {joblib_file.name}: {e}")
                continue
            if name.endswith("_desercion"):
                key = name[:-len("_desercion")]
                self.models.setdefault(key, {})["desercion"] = model
                loaded_any = True
            elif name.endswith("_reprobacion"):
                key = name[:-len("_reprobacion")]
                self.models.setdefault(key, {})["reprobacion"] = model
                loaded_any = True

        for stats_file in MODELS_DIR.glob("*_stats.json"):
            name = stats_file.stem[:-len("_stats")]
            try:
                stats_data = json.loads(stats_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Stats corrupto, ignorando {stats_file.name}: {e}")
                continue
            if name.endswith("_desercion"):
                key = name[:-len("_desercion")]
                self.stats.setdefault(key, {})["desercion"] = stats_data
            elif name.endswith("_reprobacion"):
                key = name[:-len("_reprobacion")]
                self.stats.setdefault(key, {})["reprobacion"] = stats_data

        # 2) [GAP-F2-02] Si no hay modelos en disco, restaurar desde PostgreSQL
        if not loaded_any:
            loaded_any = self._load_from_db()

        self._loaded = loaded_any
        if loaded_any:
            logger.info(f"Modelos cargados: {list(self.models.keys())} ({sum(len(v) for v in self.models.values())} total)")
        return loaded_any

    def _get_model_key(self, carrera: Optional[str]) -> str:
        """Obtiene la key del modelo para una carrera dada."""
        if carrera and carrera in self.carrera_mapping:
            return self.carrera_mapping[carrera]
        return "global"

    def _load_from_db(self) -> bool:
        """[GAP-F2-02] Restaura modelos desde PostgreSQL cuando el disco está vacío."""
        try:
            from ..database import SessionLocal
            from ..models.ml_model_store import MLModelStore
            import io

            db = SessionLocal()
            try:
                rows = db.query(MLModelStore).all()
                if not rows:
                    return False

                MODELS_DIR.mkdir(exist_ok=True)
                loaded = False

                for row in rows:
                    name = row.name
                    # Restaurar .joblib a disco
                    model_path = MODELS_DIR / f"{name}.joblib"
                    model_path.write_bytes(row.model_data)
                    model = joblib.load(model_path)

                    if name.endswith("_desercion"):
                        key = name[:-len("_desercion")]
                        self.models.setdefault(key, {})["desercion"] = model
                        loaded = True
                    elif name.endswith("_reprobacion"):
                        key = name[:-len("_reprobacion")]
                        self.models.setdefault(key, {})["reprobacion"] = model
                        loaded = True

                    # Restaurar stats JSON
                    if row.metadata_json:
                        stats = json.loads(row.metadata_json)
                        stats_path = MODELS_DIR / f"{name}_stats.json"
                        stats_path.write_text(row.metadata_json)

                        if name.endswith("_desercion"):
                            key = name[:-len("_desercion")]
                            self.stats.setdefault(key, {})["desercion"] = stats
                        elif name.endswith("_reprobacion"):
                            key = name[:-len("_reprobacion")]
                            self.stats.setdefault(key, {})["reprobacion"] = stats

                # Restaurar metadata.json y carrera_mapping.json desde BD
                for special_name, attr in [("__metadata__", "metadata"), ("__carrera_mapping__", "carrera_mapping")]:
                    row = db.query(MLModelStore).filter(MLModelStore.name == special_name).first()
                    if row and row.metadata_json:
                        data = json.loads(row.metadata_json)
                        setattr(self, attr, data)
                        # Also write to disk for future fast loads
                        fname = "metadata.json" if attr == "metadata" else "carrera_mapping.json"
                        (MODELS_DIR / fname).write_text(row.metadata_json)

                if loaded:
                    logger.info(f"[DB] Modelos restaurados desde PostgreSQL: {len(rows)} archivos")
                return loaded
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"[DB] No se pudo restaurar modelos desde BD: {e}")
            return False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def reset(self):
        """Reinicia el estado del predictor para forzar recarga de modelos."""
        self.models = {}
        self.stats = {}
        self.carrera_mapping = {}
        self.metadata = None
        self._loaded = False

    def get_status(self) -> dict:
        """Estado actual del predictor."""
        if not self._loaded:
            self.load_models()

        return {
            "loaded": self._loaded,
            "models": {k: list(v.keys()) for k, v in self.models.items()},
            "carrera_mapping": self.carrera_mapping,
            "metadata": self.metadata,
        }

    def predict_batch(self, db: Session) -> dict:
        """
        Ejecuta predicciones para todos los estudiantes del semestre actual.
        Usa modelo por carrera si existe, sino modelo global.
        """
        if not self._loaded:
            if not self.load_models():
                return {"status": "error", "message": "No hay modelos entrenados"}

        features_df = build_current_features(db)
        if features_df.empty:
            return {"status": "error", "message": "No hay calificaciones del semestre actual"}

        from ..models.student import Student

        now = datetime.now(timezone.utc)
        updated = 0
        por_carrera_count = 0
        global_count = 0

        for _, row in features_df.iterrows():
            sid = int(row["student_id"])
            carrera = row.get("carrera")
            model_key = self._get_model_key(carrera)
            models = self.models.get(model_key) or self.models.get("global", {})

            X = np.array([[row[c] for c in FEATURE_COLUMNS]])

            student = db.query(Student).filter(Student.id == sid).first()
            if not student:
                continue

            if "desercion" in models:
                student.prob_desercion = round(float(models["desercion"].predict_proba(X)[0, 1]), 4)
            if "reprobacion" in models:
                student.prob_reprobacion = round(float(models["reprobacion"].predict_proba(X)[0, 1]), 4)
            student.prediccion_updated_at = now
            updated += 1

            if model_key != "global":
                por_carrera_count += 1
            else:
                global_count += 1

        db.commit()

        logger.info(
            f"Predicciones actualizadas: {updated} estudiantes "
            f"({por_carrera_count} por carrera, {global_count} global)"
        )
        return {
            "status": "ok",
            "updated": updated,
            "por_carrera": por_carrera_count,
            "global_fallback": global_count,
            "total_features": len(features_df),
            "timestamp": now.isoformat(),
        }

    def _compute_explanations(
        self, features: dict, model_key: str, target: str, top_n: int = 5
    ) -> Optional[list]:
        """
        Calcula las contribuciones de cada feature a la prediccion (XAI).
        - LogisticRegression: contribution = coef_i * (value_i - mean_i)
        - RandomForest: contribution = importance_i * ((value_i - mean_i) / std_i)
        Retorna lista ordenada por |contribucion| descendente.
        """
        stats_key = self.stats.get(model_key, {}).get(target)
        if not stats_key:
            # Intentar fallback a global
            stats_key = self.stats.get("global", {}).get(target)
        if not stats_key:
            return None

        model_type = stats_key.get("model_type")
        means = stats_key.get("feature_means", {})
        stds = stats_key.get("feature_stds", {})

        contributions = []

        for col in FEATURE_COLUMNS:
            val = features.get(col, 0)
            mean = means.get(col, 0)
            std = stds.get(col, 1)

            if model_type == "logistic":
                coefs = stats_key.get("coefficients", {})
                coef = coefs.get(col, 0)
                contrib = coef * (val - mean)
            elif model_type == "random_forest":
                importances = stats_key.get("feature_importances", {})
                imp = importances.get(col, 0)
                safe_std = std if std > 0.001 else 1.0
                contrib = imp * ((val - mean) / safe_std)
            else:
                continue

            direction = "incrementa" if contrib > 0 else "reduce"
            contributions.append({
                "feature": col,
                "label": FEATURE_LABELS.get(col, col),
                "valor": round(val, 2),
                "media_carrera": round(mean, 2),
                "contribucion": round(float(contrib), 4),
                "direccion": direction,
            })

        # [GAP-F3-01] Filtrar factores con contribución insignificante
        contributions = [c for c in contributions if abs(c["contribucion"]) >= 0.01]
        contributions.sort(key=lambda x: abs(x["contribucion"]), reverse=True)
        return contributions[:top_n]

    def predict_single(self, db: Session, student_id: int) -> Optional[dict]:
        """Prediccion individual con features detalladas y explicaciones XAI."""
        if not self._loaded:
            if not self.load_models():
                return None

        from sqlalchemy import text as sql_text
        from .features import _get_active_periodo, _build_periodo_condition, _detect_current_periodo

        # Obtener carrera del estudiante
        from ..models.student import Student
        student = db.query(Student).filter(Student.id == student_id).first()
        carrera = student.carrera if student else None

        active_periodo = _get_active_periodo(db)
        periodo_cond = _build_periodo_condition(active_periodo)

        query = sql_text(f"""
            SELECT g.nota_final FROM grades g
            WHERE g.student_id = :sid AND {periodo_cond}
        """)
        rows = db.execute(query, {"sid": student_id}).fetchall()

        # Fallback: detectar periodo desde grades si SemesterConfig no coincide
        if not rows and active_periodo:
            detected = _detect_current_periodo(db)
            if detected and detected != active_periodo:
                periodo_cond2 = _build_periodo_condition(detected)
                query2 = sql_text(f"""
                    SELECT g.nota_final FROM grades g
                    WHERE g.student_id = :sid AND {periodo_cond2}
                """)
                rows = db.execute(query2, {"sid": student_id}).fetchall()

        if not rows:
            return None

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

        model_key = self._get_model_key(carrera)
        models = self.models.get(model_key) or self.models.get("global", {})

        result = {
            "features": features,
            "model_used": model_key,
            "carrera": carrera,
        }

        if "desercion" in models:
            result["prob_desercion"] = round(float(models["desercion"].predict_proba(X)[0, 1]), 4)
            result["explicacion_desercion"] = self._compute_explanations(
                features, model_key, "desercion"
            )
        if "reprobacion" in models:
            result["prob_reprobacion"] = round(float(models["reprobacion"].predict_proba(X)[0, 1]), 4)
            result["explicacion_reprobacion"] = self._compute_explanations(
                features, model_key, "reprobacion"
            )

        # [GAP-F3-02] Contexto conductual adicional (no depende del modelo ML)
        # Enriquece las explicaciones con indicadores intuitivos para tutores
        if student:
            contexto = []
            if student.dias_sin_acceso is not None and student.dias_sin_acceso > 7:
                sev = "critica" if student.dias_sin_acceso >= 14 else "alerta"
                contexto.append({
                    "factor": "Inactividad AVAC",
                    "descripcion": f"{student.dias_sin_acceso} dias sin acceder al aula virtual",
                    "valor": student.dias_sin_acceso,
                    "severidad": sev,
                })
            if student.porcentaje_tareas is not None and student.porcentaje_tareas < 60:
                sev = "critica" if student.porcentaje_tareas < 40 else "alerta"
                contexto.append({
                    "factor": "Entrega de tareas baja",
                    "descripcion": f"Solo ha entregado el {round(student.porcentaje_tareas)}% de tareas",
                    "valor": round(student.porcentaje_tareas, 1),
                    "severidad": sev,
                })
            if student.indice_compromiso is not None and student.indice_compromiso < 0.55:
                sev = "critica" if student.indice_compromiso < 0.3 else "alerta"
                contexto.append({
                    "factor": "Compromiso academico bajo",
                    "descripcion": f"Indice de compromiso: {round(student.indice_compromiso * 100)}%",
                    "valor": round(student.indice_compromiso, 3),
                    "severidad": sev,
                })
            if student.estado_matricula and "matriculad" not in student.estado_matricula.lower():
                contexto.append({
                    "factor": "Matricula pendiente",
                    "descripcion": f"Estado: {student.estado_matricula}",
                    "valor": student.estado_matricula,
                    "severidad": "critica",
                })
            if contexto:
                result["contexto_conductual"] = contexto

        return result
