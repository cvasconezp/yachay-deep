"""
Entrenamiento de modelos predictivos para desercion y reprobacion.
Split temporal: P60-P65 train, P66 validacion.
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
from sklearn.metrics import roc_auc_score, classification_report

from .features import build_features, FEATURE_COLUMNS, PERIODOS_ORDENADOS

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent / "models"


def train_models(db) -> dict:
    """
    Entrena modelos de desercion y reprobacion con datos historicos.
    Retorna diccionario con metricas y estado.
    """
    MODELS_DIR.mkdir(exist_ok=True)

    features_df = build_features(db)
    if features_df.empty:
        return {"status": "error", "message": "No hay datos historicos para entrenar"}

    results = {}

    # --- Modelo de desercion ---
    df_des = features_df[features_df["deserto"].notna()].copy()
    if len(df_des) > 50:
        res_des = _train_single_target(df_des, "deserto", "desercion")
        results["desercion"] = res_des
    else:
        results["desercion"] = {"status": "skip", "message": f"Solo {len(df_des)} muestras con label de desercion"}

    # --- Modelo de reprobacion ---
    df_rep = features_df.copy()
    if len(df_rep) > 50:
        res_rep = _train_single_target(df_rep, "reprobo", "reprobacion")
        results["reprobacion"] = res_rep
    else:
        results["reprobacion"] = {"status": "skip", "message": f"Solo {len(df_rep)} muestras"}

    # Guardar metadata
    metadata = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "total_registros": len(features_df),
        "estudiantes": int(features_df["student_id"].nunique()),
        "periodos": sorted(features_df["periodo"].unique().tolist()),
        "features": FEATURE_COLUMNS,
        "results": results,
    }
    (MODELS_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2, default=str))

    logger.info(f"Entrenamiento completado: {results}")
    return {"status": "ok", **metadata}


def _train_single_target(df, target_col: str, model_name: str) -> dict:
    """Entrena LR y RF para un target, selecciona el mejor por AUC."""
    # Split temporal: todos menos los ultimos 2 periodos para train,
    # penultimo periodo para validacion
    periodos = sorted(df["periodo"].unique().tolist())

    if len(periodos) < 3:
        # Fallback: usar 80/20 split por periodo
        split_idx = max(1, int(len(periodos) * 0.7))
        train_periodos = periodos[:split_idx]
        val_periodos = periodos[split_idx:]
    else:
        train_periodos = periodos[:-1]
        val_periodos = [periodos[-1]]

    train = df[df["periodo"].isin(train_periodos)]
    val = df[df["periodo"].isin(val_periodos)]

    # Si el split de validacion no tiene label (e.g. ultimo periodo sin siguiente),
    # usar una porcion del train como validacion
    val_with_label = val[val[target_col].notna()]
    if len(val_with_label) < 10:
        # Usar ultimo 20% del train como validacion
        n = int(len(train) * 0.8)
        val = train.iloc[n:]
        train = train.iloc[:n]
        val_with_label = val[val[target_col].notna()]

    X_train = train[FEATURE_COLUMNS].values
    y_train = train[target_col].values.astype(int)
    X_val = val_with_label[FEATURE_COLUMNS].values
    y_val = val_with_label[target_col].values.astype(int)

    # Entrenar candidatos
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
            # Solo una clase en validacion — usar accuracy
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

    # Guardar mejor modelo
    model_path = MODELS_DIR / f"{model_name}.joblib"
    joblib.dump(best_model, model_path)
    logger.info(f"  Mejor modelo {model_name}: {best_name} (AUC={best_auc:.4f}) → {model_path}")

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

    # Importar DB
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
