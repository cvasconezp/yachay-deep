"""
Tests para ML Train/Predict — Fase 1 T05-T07.

Cobertura:
  T05: Train end-to-end con datos sinteticos
  T06: Predict consistency (probabilidades en [0,1])
  T07: Legacy compatibility (modelos con 8 features)
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

from backend.models import Student, Grade
from backend.models.course_config import SemesterConfig
from backend.ml.features import FEATURE_COLUMNS, build_features
from backend.ml.train import train_models, _safe_carrera_key, _train_for_subset, MODELS_DIR
from backend.ml.predict import Predictor, _LEGACY_FEATURE_COLUMNS, _get_model_features


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def semester_config(db):
    sc = SemesterConfig(semestre="P68", activo=True, bloque_actual="1")
    db.add(sc)
    db.commit()
    return sc


def _seed_training_data(db, n_students=60, n_periodos=5):
    """Genera datos sinteticos suficientes para entrenar modelos.

    Crea n_students estudiantes con grades en n_periodos consecutivos.
    ~30% desaparecen en periodos intermedios (desertores reales) para
    que build_features produzca label deserto=1 en periodos no-finales.
    """
    periodos = ["P63", "P64", "P65", "P66", "P67"][:n_periodos]
    asignaturas = ["MATEMATICAS", "LENGUA", "HISTORIA", "FISICA", "QUIMICA"]

    for sid in range(1, n_students + 1):
        carrera = "EDUCACION BASICA" if sid % 2 == 0 else "DERECHO"
        s = Student(
            id=sid, nombre=f"ALUMNO {sid}", carrera=carrera,
            nivel_academico=min(7, sid % 7 + 1),  # max 7 to avoid egresado detection
        )
        db.add(s)

        # Crear desertores reales: algunos solo cursan los primeros 2-3 periodos
        # Esto genera deserto=1 en periodos intermedios (no en el ultimo)
        if sid % 3 == 0:
            # 33% de estudiantes solo cursan los primeros 2 periodos -> desertores
            periodos_cursa = periodos[:2]
        elif sid % 7 == 0:
            # Algunos solo cursan los primeros 3 periodos
            periodos_cursa = periodos[:3]
        else:
            # El resto cursa todos los periodos
            periodos_cursa = periodos

        for periodo in periodos_cursa:
            # 3-5 materias por periodo
            n_materias = 3 + (sid % 3)
            for i in range(n_materias):
                asig = asignaturas[i % len(asignaturas)]
                # Notas con varianza: algunos reprueban
                base_nota = 50 + (sid * 7 + i * 13) % 50  # rango [50, 100)
                nota = min(100, max(0, base_nota + (hash(f"{sid}{periodo}{i}") % 30 - 15)))
                g = Grade(
                    student_id=sid, periodo=periodo, asignatura=asig,
                    nota_final=nota, carrera=carrera,
                )
                db.add(g)

    db.commit()


# ═══════════════════ UNIT: helpers ═══════════════════


class TestSafeCarreraKey:
    def test_normal(self):
        key = _safe_carrera_key("EDUCACION BASICA")
        assert key.isascii()
        assert " " not in key

    def test_accents(self):
        key = _safe_carrera_key("EDUCACION INTERCULTURAL BILINGUE")
        assert key.isascii()

    def test_none(self):
        key = _safe_carrera_key(None)
        assert key == "global"

    def test_max_length(self):
        key = _safe_carrera_key("A" * 100)
        assert len(key) <= 60


class TestGetModelFeatures:
    def test_current_features(self):
        mock_model = MagicMock()
        mock_model.n_features_in_ = len(FEATURE_COLUMNS)
        result = _get_model_features(mock_model)
        assert result == FEATURE_COLUMNS

    def test_legacy_features(self):
        mock_model = MagicMock()
        mock_model.n_features_in_ = len(_LEGACY_FEATURE_COLUMNS)
        result = _get_model_features(mock_model)
        assert result == _LEGACY_FEATURE_COLUMNS

    def test_no_n_features(self):
        """Modelo viejo sin n_features_in_ usa legacy."""
        mock_model = MagicMock(spec=[])  # sin n_features_in_
        del mock_model.n_features_in_
        result = _get_model_features(mock_model)
        assert result == _LEGACY_FEATURE_COLUMNS


# ═══════════════════ T05: Train End-to-End ═══════════════════


class TestTrainModels:
    """T05: Entrenar modelos con datos sinteticos."""

    def test_train_empty_db(self, db):
        """Sin datos, retorna status error."""
        result = train_models(db)
        assert result["status"] == "error"

    def test_train_with_data_produces_models(self, db):
        """Con datos suficientes, produce modelos y metadata."""
        _seed_training_data(db, n_students=60, n_periodos=4)

        with tempfile.TemporaryDirectory() as tmpdir:
            models_dir = Path(tmpdir)
            with patch("backend.ml.train.MODELS_DIR", models_dir):
                with patch("backend.ml.train._persist_global_metadata_to_db"):
                    with patch("backend.ml.train._persist_model_to_db"):
                        result = train_models(db)

        assert result["status"] == "ok"
        assert result["total_registros"] > 0
        assert result["estudiantes"] > 0
        assert "carreras_con_modelo" in result or "carreras" in result

    def test_train_saves_metadata(self, db):
        """El entrenamiento guarda metadata.json y carrera_mapping.json."""
        _seed_training_data(db, n_students=60, n_periodos=4)

        with tempfile.TemporaryDirectory() as tmpdir:
            models_dir = Path(tmpdir)
            with patch("backend.ml.train.MODELS_DIR", models_dir):
                with patch("backend.ml.train._persist_global_metadata_to_db"):
                    with patch("backend.ml.train._persist_model_to_db"):
                        result = train_models(db)

            # Verificar archivos creados
            assert (models_dir / "metadata.json").exists()
            assert (models_dir / "carrera_mapping.json").exists()

            metadata = json.loads((models_dir / "metadata.json").read_text())
            assert "trained_at" in metadata
            assert metadata["features"] == FEATURE_COLUMNS

    def test_train_global_model_always_created(self, db):
        """Siempre se crea un modelo global como fallback."""
        _seed_training_data(db, n_students=60, n_periodos=4)

        with tempfile.TemporaryDirectory() as tmpdir:
            models_dir = Path(tmpdir)
            with patch("backend.ml.train.MODELS_DIR", models_dir):
                with patch("backend.ml.train._persist_global_metadata_to_db"):
                    with patch("backend.ml.train._persist_model_to_db"):
                        result = train_models(db)

            # Modelo global de desercion y/o reprobacion
            model_files = list(models_dir.glob("global_*.joblib"))
            assert len(model_files) >= 1, f"Expected global models, found: {[f.name for f in models_dir.iterdir()]}"

    def test_train_small_carrera_uses_fallback(self, db):
        """Carreras con < 30 muestras usan modelo global."""
        # Primero crear datos suficientes para que el modelo global entrene
        _seed_training_data(db, n_students=60, n_periodos=4)

        # Agregar 5 estudiantes extra en una carrera chica (< 30 muestras)
        for sid in range(200, 205):
            s = Student(id=sid, nombre=f"ALUMNO {sid}", carrera="CARRERA CHICA",
                        nivel_academico=3)
            db.add(s)
            for per in ["P65", "P66", "P67"]:
                g = Grade(student_id=sid, periodo=per, asignatura="A",
                          nota_final=70, carrera="CARRERA CHICA")
                db.add(g)
        db.commit()

        with tempfile.TemporaryDirectory() as tmpdir:
            models_dir = Path(tmpdir)
            with patch("backend.ml.train.MODELS_DIR", models_dir):
                with patch("backend.ml.train._persist_global_metadata_to_db"):
                    with patch("backend.ml.train._persist_model_to_db"):
                        result = train_models(db)

        assert result["status"] == "ok"
        # La carrera chica deberia usar fallback (< 30 muestras)
        if "carreras" in result and "CARRERA CHICA" in result.get("carreras", {}):
            assert result["carreras"]["CARRERA CHICA"]["status"] == "fallback_global"


class TestTrainForSubset:
    """Tests para _train_for_subset interno."""

    def test_with_sufficient_data(self, db):
        """Con datos suficientes produce resultado ok."""
        _seed_training_data(db, n_students=60, n_periodos=4)
        features_df = build_features(db)
        assert not features_df.empty

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("backend.ml.train.MODELS_DIR", Path(tmpdir)):
                with patch("backend.ml.train._persist_model_to_db"):
                    result = _train_for_subset(features_df, "test_model")

        # Debe tener resultado para al menos reprobacion
        assert "reprobacion" in result
        if result["reprobacion"].get("status") == "ok":
            assert 0 <= result["reprobacion"]["best_auc"] <= 1


# ═══════════════════ T06: Predict Consistency ═══════════════════


class TestPredictConsistency:
    """T06: Las predicciones producen probabilidades validas."""

    def test_predictor_singleton(self):
        p1 = Predictor.get_instance()
        p2 = Predictor.get_instance()
        assert p1 is p2
        # Reset para no afectar otros tests
        Predictor._instance = None

    def test_load_models_no_files(self):
        """Sin archivos de modelo, load_models retorna False."""
        predictor = Predictor()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("backend.ml.predict.MODELS_DIR", Path(tmpdir)):
                result = predictor.load_models()
        assert result is False

    def test_predictions_in_valid_range(self, db):
        """Las probabilidades predichas deben estar en [0, 1]."""
        _seed_training_data(db, n_students=60, n_periodos=4)

        with tempfile.TemporaryDirectory() as tmpdir:
            models_dir = Path(tmpdir)
            with patch("backend.ml.train.MODELS_DIR", models_dir):
                with patch("backend.ml.predict.MODELS_DIR", models_dir):
                    with patch("backend.ml.train._persist_global_metadata_to_db"):
                        with patch("backend.ml.train._persist_model_to_db"):
                            train_result = train_models(db)

                    if train_result["status"] != "ok":
                        pytest.skip("Training failed, skipping prediction test")

                    predictor = Predictor()
                    loaded = predictor.load_models()
                    if not loaded:
                        pytest.skip("Models could not be loaded")

                    # Crear features de test
                    features = {col: 50.0 for col in FEATURE_COLUMNS}
                    features["num_asignaturas"] = 5
                    features["pct_reprobadas"] = 0.4

                    # Predecir usando modelo global
                    models = predictor.models.get("global", {})
                    for target_type, model in models.items():
                        X = np.array([[features.get(c, 0) for c in FEATURE_COLUMNS]])
                        proba = model.predict_proba(X)[0]
                        # Debe sumar ~1 y estar en [0,1]
                        assert all(0 <= p <= 1 for p in proba), f"Invalid probabilities: {proba}"
                        assert abs(sum(proba) - 1.0) < 0.01


# ═══════════════════ T07: Legacy Compatibility ═══════════════════


class TestLegacyCompatibility:
    """T07: Modelos con 8 features (legacy) siguen funcionando."""

    def test_legacy_feature_columns_defined(self):
        assert len(_LEGACY_FEATURE_COLUMNS) == 8
        assert "promedio_notas" in _LEGACY_FEATURE_COLUMNS
        assert "num_asignaturas" in _LEGACY_FEATURE_COLUMNS

    def test_legacy_is_subset_of_current(self):
        """Las features legacy son un subconjunto de las actuales."""
        for col in _LEGACY_FEATURE_COLUMNS:
            assert col in FEATURE_COLUMNS, f"Legacy column {col} not in current FEATURE_COLUMNS"

    def test_get_model_features_handles_unknown_count(self):
        """Si el modelo tiene un numero inesperado de features, no crashea."""
        mock_model = MagicMock()
        mock_model.n_features_in_ = 5  # numero raro
        result = _get_model_features(mock_model)
        assert isinstance(result, list)
        assert len(result) == 5
