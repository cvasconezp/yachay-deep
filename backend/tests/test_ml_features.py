"""
Tests para ML Feature Building — Fase 1 T04.

Cobertura:
  - build_features() con grades sinteticos conocidos
  - Verificacion de las 12 FEATURE_COLUMNS
  - Labels: deserto, reprobo
  - Deteccion de egresados (no marcar como desertores)
  - build_current_features() con datos del semestre activo
"""
import pytest
import pandas as pd
import numpy as np

from backend.models import Student, Grade
from backend.models.course_config import SemesterConfig
from backend.ml.features import (
    build_features, build_current_features,
    FEATURE_COLUMNS, EXTENDED_FEATURE_COLUMNS, PERIODOS_ORDENADOS,
    _normalize_asig, _strip_accents, _career_to_filename,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def semester_config(db):
    sc = SemesterConfig(semestre="P68", activo=True, bloque_actual="1")
    db.add(sc)
    db.commit()
    return sc


def _create_student(db, sid, nombre, carrera, nivel_academico=3, **kwargs):
    s = Student(
        id=sid, nombre=nombre, carrera=carrera,
        nivel_academico=nivel_academico, **kwargs,
    )
    db.add(s)
    db.commit()
    return s


def _create_grades(db, student_id, periodo, grades_list):
    """Crea grades para un estudiante. grades_list = [(asignatura, nota_final), ...]"""
    for asig, nota in grades_list:
        g = Grade(
            student_id=student_id,
            periodo=periodo,
            asignatura=asig,
            nota_final=nota,
            carrera=db.query(Student).get(student_id).carrera,
        )
        db.add(g)
    db.commit()


# ═══════════════════ UNIT: helpers ═══════════════════


class TestFeatureHelpers:
    def test_normalize_asig(self):
        assert _normalize_asig("  matematicas  basicas  ") == "MATEMATICAS BASICAS"

    def test_normalize_asig_newlines(self):
        assert _normalize_asig("algebra\nlineal") == "ALGEBRA LINEAL"

    def test_strip_accents(self):
        assert _strip_accents("educacion") == "educacion"

    def test_strip_accents_tilde(self):
        result = _strip_accents("EDUCACION BASICA")
        assert isinstance(result, str)

    def test_career_to_filename(self):
        result = _career_to_filename("EDUCACION BASICA")
        assert result.endswith(".json")
        assert " " not in result

    def test_feature_columns_count(self):
        assert len(FEATURE_COLUMNS) == 12

    def test_extended_columns_has_conductual(self):
        assert "dias_sin_acceso" in EXTENDED_FEATURE_COLUMNS
        assert "porcentaje_tareas" in EXTENDED_FEATURE_COLUMNS
        assert "indice_compromiso" in EXTENDED_FEATURE_COLUMNS
        assert len(EXTENDED_FEATURE_COLUMNS) == 15


# ═══════════════════ T04: build_features ═══════════════════


class TestBuildFeatures:
    """T04: Verificar que build_features produce features correctas."""

    def test_empty_db_returns_empty(self, db):
        result = build_features(db)
        assert result.empty

    def test_single_student_two_periods(self, db):
        """Un estudiante con datos en P65 y P66 produce features correctas."""
        _create_student(db, 1, "ALUMNO UNO", "EDUCACION BASICA")

        _create_grades(db, 1, "P65", [
            ("MATEMATICAS", 80), ("LENGUA", 70), ("HISTORIA", 60),
        ])
        _create_grades(db, 1, "P66", [
            ("FISICA", 90), ("QUIMICA", 50), ("BIOLOGIA", 75),
        ])

        result = build_features(db)
        assert not result.empty
        assert result["student_id"].nunique() == 1

        # Verificar features del P65
        p65 = result[result["periodo"] == "P65"].iloc[0]
        assert p65["num_asignaturas"] == 3
        assert p65["promedio_notas"] == pytest.approx(70.0, abs=0.1)
        assert p65["num_reprobadas"] == 1  # HISTORIA = 60 < 70
        assert p65["nota_min"] == 60
        assert p65["nota_max"] == 80
        assert p65["num_zeros"] == 0

    def test_pct_reprobadas_calculation(self, db):
        """pct_reprobadas = num_reprobadas / num_asignaturas."""
        _create_student(db, 1, "ALUMNO", "DERECHO")
        _create_grades(db, 1, "P66", [
            ("A", 80), ("B", 50), ("C", 40), ("D", 90),
        ])

        result = build_features(db)
        row = result[result["periodo"] == "P66"].iloc[0]
        assert row["pct_reprobadas"] == pytest.approx(0.5, abs=0.01)  # 2/4

    def test_num_zeros(self, db):
        """num_zeros cuenta materias con nota = 0."""
        _create_student(db, 1, "ALUMNO", "DERECHO")
        _create_grades(db, 1, "P66", [
            ("A", 0), ("B", 0), ("C", 80), ("D", 70),
        ])

        result = build_features(db)
        row = result[result["periodo"] == "P66"].iloc[0]
        assert row["num_zeros"] == 2

    def test_std_notas_single_subject(self, db):
        """std_notas con 1 materia debe ser 0 (no NaN)."""
        _create_student(db, 1, "ALUMNO", "DERECHO")
        _create_grades(db, 1, "P66", [("A", 80)])

        result = build_features(db)
        row = result[result["periodo"] == "P66"].iloc[0]
        assert row["std_notas"] == 0
        assert not np.isnan(row["std_notas"])

    def test_label_reprobo(self, db):
        """reprobo = 1 si tiene alguna nota < 70."""
        _create_student(db, 1, "ALUMNO", "DERECHO")
        _create_grades(db, 1, "P66", [("A", 80), ("B", 60)])  # B < 70

        result = build_features(db)
        row = result[result["periodo"] == "P66"].iloc[0]
        assert row["reprobo"] == 1

    def test_label_no_reprobo(self, db):
        """reprobo = 0 si todas las notas >= 70."""
        _create_student(db, 1, "ALUMNO", "DERECHO")
        _create_grades(db, 1, "P66", [("A", 80), ("B", 75)])

        result = build_features(db)
        row = result[result["periodo"] == "P66"].iloc[0]
        assert row["reprobo"] == 0

    def test_label_desercion(self, db):
        """deserto = 1 si no aparece en periodo siguiente."""
        _create_student(db, 1, "ALUMNO", "DERECHO")
        _create_student(db, 2, "ALUMNO2", "DERECHO")

        # Alumno 1: solo en P65, alumno 2: en P65 y P66
        _create_grades(db, 1, "P65", [("A", 80)])
        _create_grades(db, 2, "P65", [("A", 70)])
        _create_grades(db, 2, "P66", [("B", 75)])

        result = build_features(db)
        # Alumno 1 en P65 deserto (no esta en P66)
        a1_p65 = result[(result["student_id"] == 1) & (result["periodo"] == "P65")].iloc[0]
        assert a1_p65["deserto"] == 1

        # Alumno 2 en P65 no deserto (si esta en P66)
        a2_p65 = result[(result["student_id"] == 2) & (result["periodo"] == "P65")].iloc[0]
        assert a2_p65["deserto"] == 0

    def test_label_desercion_last_period_is_none(self, db):
        """deserto = None para el ultimo periodo (no se puede evaluar)."""
        _create_student(db, 1, "ALUMNO", "DERECHO")
        _create_grades(db, 1, "P67", [("A", 80)])

        result = build_features(db)
        row = result[result["periodo"] == "P67"].iloc[0]
        assert pd.isna(row["deserto"])

    def test_carrera_assigned(self, db):
        """Cada registro tiene la carrera del estudiante."""
        _create_student(db, 1, "ALUMNO", "EDUCACION BASICA")
        _create_grades(db, 1, "P66", [("A", 80)])

        result = build_features(db)
        assert result.iloc[0]["carrera"] == "EDUCACION BASICA"

    def test_all_feature_columns_present(self, db):
        """El DataFrame tiene todas las FEATURE_COLUMNS."""
        _create_student(db, 1, "ALUMNO", "DERECHO")
        _create_grades(db, 1, "P66", [("A", 80), ("B", 60)])

        result = build_features(db)
        for col in FEATURE_COLUMNS:
            assert col in result.columns, f"Missing column: {col}"

    def test_multiple_students_multiple_carreras(self, db):
        """Multiples estudiantes de distintas carreras."""
        _create_student(db, 1, "ALUMNO UNO", "EDUCACION BASICA")
        _create_student(db, 2, "ALUMNO DOS", "DERECHO")

        _create_grades(db, 1, "P66", [("A", 80)])
        _create_grades(db, 2, "P66", [("B", 60)])

        result = build_features(db)
        assert result["student_id"].nunique() == 2
        carreras = result["carrera"].unique()
        assert len(carreras) == 2


class TestBuildCurrentFeatures:
    """Tests para build_current_features (semestre activo)."""

    def test_empty_returns_empty(self, db, semester_config):
        result = build_current_features(db)
        assert result.empty

    def test_with_current_grades(self, db, semester_config):
        """Debe calcular features para grades del periodo activo."""
        s = _create_student(
            db, 1, "ALUMNO", "DERECHO",
            dias_sin_acceso=5, porcentaje_tareas=80.0, indice_compromiso=0.7,
        )
        # Grades sin periodo (fallback al activo)
        g = Grade(student_id=1, asignatura="MATEMATICAS", nota_final=85, carrera="DERECHO")
        db.add(g)
        db.commit()

        result = build_current_features(db)
        assert not result.empty
        row = result.iloc[0]
        assert row["promedio_notas"] == pytest.approx(85.0, abs=0.1)
        # Conductual features
        assert row["dias_sin_acceso"] == 5
        assert row["porcentaje_tareas"] == 80.0
        assert row["indice_compromiso"] == pytest.approx(0.7, abs=0.01)

    def test_extended_features_present(self, db, semester_config):
        """build_current_features incluye features conductuales."""
        _create_student(db, 1, "ALUMNO", "DERECHO",
                        dias_sin_acceso=3, porcentaje_tareas=60.0, indice_compromiso=0.5)
        g = Grade(student_id=1, asignatura="A", nota_final=70, carrera="DERECHO")
        db.add(g)
        db.commit()

        result = build_current_features(db)
        assert "dias_sin_acceso" in result.columns
        assert "porcentaje_tareas" in result.columns
        assert "indice_compromiso" in result.columns
