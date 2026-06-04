"""
Tests Fase 2 — T17: NaN Sanitization + T19: Semester End Detection.

Cobertura:
  T17: La configuracion de limpieza NaN/Inf es correcta y no falla en SQLite
  T19: _semester_ended() detecta correctamente fin de semestre
"""
import pytest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone as tz

from backend.database import Base, upgrade_tables
from backend.models.course_config import SemesterConfig
from backend.scraping.runner import _semester_ended


def _get_test_engine():
    from backend.tests.conftest import engine as test_engine
    return test_engine


# ═══════════════════ T17: NaN Sanitization Config ═══════════════════


class TestNanSanitization:
    """T17: Verificar que upgrade_tables maneja NaN correctamente."""

    def test_upgrade_runs_without_nan_errors_sqlite(self, db):
        """En SQLite, upgrade_tables no intenta limpiar NaN (solo PostgreSQL)."""
        test_engine = _get_test_engine()
        with patch("backend.database.engine", test_engine):
            # No debe crashear en SQLite (NaN cleanup se salta)
            upgrade_tables()

    def test_nan_cleanup_config_has_expected_tables(self):
        """La configuracion de limpieza NaN lista las tablas correctas."""
        # Verificamos leyendo el codigo fuente que las tablas criticas estan
        import inspect
        from backend.database import upgrade_tables
        source = inspect.getsource(upgrade_tables)

        assert "avac_accesses" in source
        assert "task_submissions" in source
        assert "grades" in source
        assert "students" in source

    def test_nan_cleanup_config_has_expected_columns(self):
        """Columnas float criticas estan en la lista de limpieza NaN."""
        import inspect
        from backend.database import upgrade_tables
        source = inspect.getsource(upgrade_tables)

        critical_cols = [
            "dias_sin_acceso", "nota_final",
            "prob_desercion", "prob_reprobacion",
            "indice_compromiso", "porcentaje_tareas",
        ]
        for col in critical_cols:
            assert col in source, f"Column {col} missing from NaN cleanup config"

    def test_upgrade_idempotent_with_nan_config(self, db):
        """upgrade_tables multiples veces no falla con la config de NaN."""
        test_engine = _get_test_engine()
        with patch("backend.database.engine", test_engine):
            upgrade_tables()
            upgrade_tables()  # segunda vez sin error

    def test_float_columns_accept_null(self, db):
        """Columnas float en students aceptan NULL (requisito para limpiar NaN)."""
        from backend.models import Student
        s = Student(
            nombre="TEST NAN", carrera="DERECHO",
            prob_desercion=None, prob_reprobacion=None,
            indice_compromiso=None, porcentaje_tareas=None,
        )
        db.add(s)
        db.commit()

        s2 = db.query(Student).filter(Student.nombre == "TEST NAN").first()
        assert s2.prob_desercion is None
        assert s2.prob_reprobacion is None
        assert s2.indice_compromiso is None


# ═══════════════════ T19: Semester End Detection ═══════════════════


class TestSemesterEndDetection:
    """T19: _semester_ended() detecta fin de semestre."""

    def test_no_active_semester_returns_true(self, db):
        """Sin semestre activo, retorna True (no ejecutar scraping)."""
        with patch("backend.database.SessionLocal", return_value=db):
            result = _semester_ended()
        assert result is True

    def test_active_semester_not_ended(self, db):
        """Semestre activo con fecha futura retorna False."""
        sc = SemesterConfig(
            semestre="P68", activo=True, bloque_actual="1",
            bloque1_inicio=datetime.now(tz.utc) - timedelta(days=30),
            bloque1_fin=datetime.now(tz.utc) + timedelta(days=30),
        )
        db.add(sc)
        db.commit()

        with patch("backend.database.SessionLocal", return_value=db):
            result = _semester_ended()
        assert result is False

    def test_active_semester_ended(self, db):
        """Semestre activo con fecha pasada retorna True."""
        sc = SemesterConfig(
            semestre="P67", activo=True, bloque_actual="1",
            bloque1_inicio=datetime.now(tz.utc) - timedelta(days=120),
            bloque1_fin=datetime.now(tz.utc) - timedelta(days=1),
        )
        db.add(sc)
        db.commit()

        with patch("backend.database.SessionLocal", return_value=db):
            result = _semester_ended()
        assert result is True

    def test_bloque2_active_not_ended(self, db):
        """Bloque 2 activo con fecha futura retorna False."""
        sc = SemesterConfig(
            semestre="P68", activo=True, bloque_actual="2",
            bloque1_inicio=datetime.now(tz.utc) - timedelta(days=90),
            bloque1_fin=datetime.now(tz.utc) - timedelta(days=30),
            bloque2_inicio=datetime.now(tz.utc) - timedelta(days=15),
            bloque2_fin=datetime.now(tz.utc) + timedelta(days=45),
        )
        db.add(sc)
        db.commit()

        with patch("backend.database.SessionLocal", return_value=db):
            result = _semester_ended()
        assert result is False

    def test_bloque2_ended(self, db):
        """Bloque 2 finalizado retorna True."""
        sc = SemesterConfig(
            semestre="P68", activo=True, bloque_actual="2",
            bloque2_inicio=datetime.now(tz.utc) - timedelta(days=90),
            bloque2_fin=datetime.now(tz.utc) - timedelta(days=5),
        )
        db.add(sc)
        db.commit()

        with patch("backend.database.SessionLocal", return_value=db):
            result = _semester_ended()
        assert result is True

    def test_no_dates_configured_returns_false(self, db):
        """Semestre activo sin fechas retorna False (asumir activo)."""
        sc = SemesterConfig(semestre="P68", activo=True, bloque_actual="1")
        db.add(sc)
        db.commit()

        with patch("backend.database.SessionLocal", return_value=db):
            result = _semester_ended()
        assert result is False


class TestSemesterConfigProperties:
    """Tests adicionales para las properties del modelo."""

    def test_fecha_fin_actual_bloque1(self, db):
        fin = datetime(2026, 7, 15, tzinfo=tz.utc)
        sc = SemesterConfig(
            semestre="P68", activo=True, bloque_actual="1",
            bloque1_fin=fin,
        )
        db.add(sc)
        db.commit()
        # SQLite strips tzinfo, so compare naive datetimes
        result = sc.fecha_fin_actual
        assert result.replace(tzinfo=None) == fin.replace(tzinfo=None)

    def test_fecha_fin_actual_bloque2(self, db):
        fin2 = datetime(2026, 10, 15, tzinfo=tz.utc)
        sc = SemesterConfig(
            semestre="P68", activo=True, bloque_actual="2",
            bloque2_fin=fin2,
        )
        db.add(sc)
        db.commit()
        result = sc.fecha_fin_actual
        assert result.replace(tzinfo=None) == fin2.replace(tzinfo=None)

    def test_semestre_finalizado_property(self, db):
        sc = SemesterConfig(
            semestre="P67", activo=True, bloque_actual="1",
            bloque1_fin=datetime(2025, 1, 1, tzinfo=tz.utc),  # ya paso
        )
        db.add(sc)
        db.commit()
        assert sc.semestre_finalizado is True

    def test_semestre_no_finalizado_property(self, db):
        sc = SemesterConfig(
            semestre="P69", activo=True, bloque_actual="1",
            bloque1_fin=datetime(2030, 12, 31, tzinfo=tz.utc),
        )
        db.add(sc)
        db.commit()
        assert sc.semestre_finalizado is False
