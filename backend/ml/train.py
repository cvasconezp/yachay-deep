"""
Entrenamiento de modelos predictivos para desercion y reprobacion.
Entrena un modelo por carrera + un modelo global como fallback.
Split temporal: todos menos ultimo periodo para train, ultimo para validacion.
Ejecutable: python -m backend.ml.train
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score

from .features import build_features, FEATURE_COLUMNS, PERIODOS_ORDENADOS

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent / "models"

# Minimo de muestras para entrenar un modelo por carrera
MIN_SAMPLES_CARRERA = 30


def _safe_carrera_key(carrera: str) -> str:
    """Convierte nombre de carrera a key segura para nombre de archivo."""
    import re
    import unicodedata
    key = unicodedata.normalize("NFKD", carrera or "global")
    key = key.encode("ASCII", "ignore").decode("utf-8")
    key = re.sub(r"[^a-zA-Z0-9]", "_", key).lower().strip("_")
    return key[:60] or "global"


def train_models(db) -> dict:
    """
    Entrena modelos de desercion y reprobacion por carrera + global.
    Retorna diccionario con metricas y estado.
    """
    MODELS_DIR.mkdir(exist_ok=True)

    features_df = build_features(db)
    if features_df.empty:
        return {"status": "error", "message": "No hay datos historicos para entrenar"}

    results = {"carreras": {}, "global": {}}

    # Obtener carreras únicas con suficientes datos
    carreras = features_df["carrera"].dropna().unique().tolist()

    # --- Entrenar modelo GLOBAL (fallback) ---
    logger.info("=== Entrenando modelo GLOBAL ===")
    results["global"] = _train_for_subset(features_df, "global")

    # --- Entrenar modelo POR CARRERA ---
    for carrera in carreras:
        df_carrera = features_df[features_df["carrera"] == carrera]
        if len(df_carrera) < MIN_SAMPLES_CARRERA:
            logger.info(f"  Carrera '{carrera}': solo {len(df_carrera)} muestras, usará modelo global")
            results["carreras"][carrera] = {"status": "fallback_global", "samples": len(df_carrera)}
            continue

        logger.info(f"=== Entrenando modelo para carrera: {carrera} ({len(df_carrera)} muestras) ===")
        key = _safe_carrera_key(carrera)
        results["carreras"][carrera] = _train_for_subset(df_carrera, key)

    # Guardar metadata
    metadata = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "total_registros": len(features_df),
        "estudiantes": int(features_df["student_id"].nunique()),
        "carreras_con_modelo": [c for c, r in results["carreras"].items() if r.get("status") != "fallback_global"],
        "carreras_fallback": [c for c, r in results["carreras"].items() if r.get("status") == "fallback_global"],
        "periodos": sorted(features_df["periodo"].unique().tolist()),
        "features": FEATURE_COLUMNS,
        "results": results,
    }
    (MODELS_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2, default=str, ensure_ascii=False))

    # Guardar mapping carrera -> key para prediccion
    carrera_mapping = {"global": "global"}
    for carrera in carreras:
        r = results["carreras"].get(carrera, {})
        if r.get("status") != "fallback_global":
            carrera_mapping[carrera] = _safe_carrera_key(carrera)
        else:
            carrera_mapping[carrera] = "global"
    (MODELS_DIR / "carrera_mapping.json").write_text(
        json.dumps(carrera_mapping, indent=2, ensure_ascii=False)
    )

    logger.info(f"Entrenamiento completado: {len(results['carreras'])} carreras procesadas")
    return {"status": "ok", **metadata}


def _train_for_subset(df, model_prefix: str) -> dict:
    """Entrena desercion + reprobacion para un subset (carrera o global)."""
    result = {}

    # Desercion
    df_des = df[df["deserto"].notna()].copy()
    if len(df_des) > 20:
        result["desercion"] = _train_single_target(df_des, "deserto", f"{model_prefix}_desercion")
    else:
        result["desercion"] = {"status": "skip", "message": f"Solo {len(df_des)} muestras"}

    # Reprobacion
    if len(df) > 20:
        result["reprobacion"] = _train_single_target(df, "reprobo", f"{model_prefix}_reprobacion")
    else:
        result["reprobacion"] = {"status": "skip", "message": f"Solo {len(df)} muestras"}

    return result


def _train_single_target(df, target_col: str, model_name: str) -> dict:
    """Entrena LR y RF para un target, selecciona el mejor por AUC."""
    periodos = sorted(df["periodo"].unique().tolist())

    if len(periodos) < 3:
        split_idx = max(1, int(len(periodos) * 0.7))
        train_periodos = periodos[:split_idx]
        val_periodos = periodos[split_idx:]
    else:
        train_periodos = periodos[:-1]
        val_periodos = [periodos[-1]]

    train = df[df["periodo"].isin(train_periodos)]
    val = df[df["periodo"].isin(val_periodos)]

    val_with_label = val[val[target_col].notna()]
    if len(val_with_label) < 10:
        n = int(len(train) * 0.8)
        val = train.iloc[n:]
        train = train.iloc[:n]
        val_with_label = val[val[target_col].notna()]

    X_train = train[FEATURE_COLUMNS].values
    y_train = train[target_col].values.astype(int)
    X_val = val_with_label[FEATURE_COLUMNS].values
    y_val = val_with_label[target_col].values.astype(int)

    candidates = {
        "logistic": LogisticRegression(
            class_weight="balanced", max_iter=1000, random_state=42
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=100, class_weight="balanced", random_state=42, n_jobs=-1
        ),
    }

    best_name = None
    best_model = None
    best_auc = -1
    model_metrics = {}

    for name, model in candidates.items():
        model.fit(X_train, y_train)

        if len(np.unique(y_val)) < 2:
            auc = model.score(X_val, y_val)
        else:
            y_proba = model.predict_proba(X_val)[:, 1]
            auc = roc_auc_score(y_val, y_proba)

        model_metrics[name] = {"auc": round(auc, 4)}
        logger.info(f"  {model_name}/{name}: AUC={auc:.4f}")

        if auc > best_auc:
            best_auc = auc
            best_name = name
            best_model = model

    model_path = MODELS_DIR / f"{model_name}.joblib"
    joblib.dump(best_model, model_path)
    logger.info(f"  Mejor modelo {model_name}: {best_name} (AUC={best_auc:.4f}) -> {model_path}")

    return {
        "status": "ok",
        "best_model": best_name,
        "best_auc": round(best_auc, 4),
        "train_samples": len(train),
        "val_samples": len(val_with_label),
        "train_periodos": train_periodos,
        "val_periodos": val_periodos,
        "positive_rate_train": round(float(y_train.mean()), 4),
        "all_models": model_metrics,
    }


# --- CLI entrypoint ---
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from backend.database import SessionLocal, create_tables, upgrade_tables

    create_tables()
    upgrade_tables()
    db = SessionLocal()
    try:
        result = train_models(db)
        print(json.dumps(result, indent=2, default=str))
    finally:
        db.close()
