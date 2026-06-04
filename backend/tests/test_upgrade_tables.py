"""
Test upgrade_tables() Safety — Fase 1 T10.

Cobertura:
  - upgrade_tables() agrega columnas nuevas sin perder datos
  - Columnas existentes no se borran
  - Datos pre-existentes sobreviven al upgrade
"""
import pytest
from unittest.mock import patch
from sqlalchemy import inspect

from backend.database import Base, upgrade_tables
from backend.models import Student, Grade, Enrollment
from backend.models.course_config import SemesterConfig


# We need to use the test engine (from conftest), not the production engine.
# conftest creates tables via Base.metadata.create_all(bind=test_engine)
# but upgrade_tables() uses backend.database.engine internally.
# So we patch backend.database.engine with the test engine.

def _get_test_engine():
    """Get the test engine from conftest module."""
    from backend.tests.conftest import engine as test_engine
    return test_engine


# ═══════════════════ T10: upgrade_tables Safety ═══════════════════


class TestUpgradeTables:
    """T10: Verificar migracion segura de schema."""

    def _run_upgrade(self):
        """Run upgrade_tables with the test engine patched in."""
        test_engine = _get_test_engine()
        with patch("backend.database.engine", test_engine):
            upgrade_tables()

    def test_upgrade_tables_idempotent(self, db):
        """Ejecutar upgrade_tables multiples veces no causa error."""
        self._run_upgrade()
        self._run_upgrade()  # segunda ejecucion no debe fallar
        self._run_upgrade()  # tercera tampoco

    def test_students_table_has_expected_columns(self, db):
        """La tabla students tiene las columnas esperadas despues de upgrade."""
        self._run_upgrade()

        test_engine = _get_test_engine()
        inspector = inspect(test_engine)
        cols = {c["name"] for c in inspector.get_columns("students")}

        expected = {
            "id", "nombre", "carrera",
            "prob_desercion", "prob_reprobacion", "prediccion_updated_at",
            "whatsapp", "nivel_academico",
        }
        for col in expected:
            assert col in cols, f"Missing column 'students.{col}'"

    def test_interventions_has_snapshot_columns(self, db):
        """upgrade_tables agrega columnas de snapshot a interventions."""
        self._run_upgrade()

        test_engine = _get_test_engine()
        inspector = inspect(test_engine)
        cols = {c["name"] for c in inspector.get_columns("interventions")}

        snapshot_cols = [
            "snapshot_compromiso", "snapshot_dias_sin_acceso",
            "snapshot_porcentaje_tareas", "snapshot_prob_desercion",
        ]
        for col in snapshot_cols:
            assert col in cols, f"Missing column 'interventions.{col}'"

    def test_data_survives_upgrade(self, db):
        """Datos insertados antes del upgrade sobreviven."""
        s = Student(nombre="DATO CRITICO", carrera="DERECHO", cedula="1111111111")
        db.add(s)
        db.commit()
        sid = s.id

        self._run_upgrade()

        s2 = db.query(Student).filter(Student.id == sid).first()
        assert s2 is not None
        assert s2.nombre == "DATO CRITICO"
        assert s2.cedula == "1111111111"

    def test_grades_table_has_periodo(self, db):
        """grades tiene la columna periodo despues de upgrade."""
        self._run_upgrade()

        test_engine = _get_test_engine()
        inspector = inspect(test_engine)
        cols = {c["name"] for c in inspector.get_columns("grades")}
        assert "periodo" in cols
        assert "numero_repitencias" in cols

    def test_enrollments_has_tercera_matricula(self, db):
        """enrollments tiene columna es_tercera_matricula."""
        self._run_upgrade()

        test_engine = _get_test_engine()
        inspector = inspect(test_engine)
        if "enrollments" in inspector.get_table_names():
            cols = {c["name"] for c in inspector.get_columns("enrollments")}
            assert "es_tercera_matricula" in cols

    def test_avac_accesses_has_periodo(self, db):
        """avac_accesses tiene columna periodo."""
        self._run_upgrade()

        test_engine = _get_test_engine()
        inspector = inspect(test_engine)
        if "avac_accesses" in inspector.get_table_names():
            cols = {c["name"] for c in inspector.get_columns("avac_accesses")}
            assert "periodo" in cols
            assert "snapshot_date" in cols
