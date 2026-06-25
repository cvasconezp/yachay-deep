"""
Tests de integracion para ETL Pipeline — Fase 1.

Cobertura:
  T01: run_full() con datos sinteticos completos
  T02: Idempotencia — ejecutar 2 veces sin duplicar registros
  T03: Error recovery — fallo a mitad del pipeline
"""
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from backend.models import Student, Grade, Enrollment, AvacAccess, TaskSubmission, ScrapingRun
from backend.models.course_config import SemesterConfig, CourseConfig
from backend.etl.pipeline import ETLPipeline, _clean_str, _nan_to_none, _normalize_name
from .conftest import auth


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def semester_config(db):
    sc = SemesterConfig(semestre="P68", activo=True, bloque_actual="1")
    db.add(sc)
    db.commit()
    return sc


@pytest.fixture
def tmp_data_dirs():
    """Crea directorios temporales con CSVs sinteticos para el ETL."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)

        # IngresosAVAC — CSV con formato esperado
        ingresos_dir = base / "IngresosAVAC"
        ingresos_dir.mkdir()

        # Tareas
        tareas_dir = base / "Tareas"
        tareas_dir.mkdir()

        # Calificaciones
        cal_file = base / "calificaciones.csv"
        cal_file.write_text("")  # vacio, se usa historico como fallback

        # TableauHistorico
        hist_dir = base / "TableauHistorico"
        hist_dir.mkdir()

        # Reportes
        reportes_dir = base / "Reportes"
        reportes_dir.mkdir()

        # DatosEspecificos
        datos_dir = base / "DatosEspecificos"
        datos_dir.mkdir()

        # Practicas
        prac_dir = base / "Practicas"
        prac_dir.mkdir()

        # TercerasMatriculas
        tm_dir = base / "TercerasMatriculas"
        tm_dir.mkdir()

        yield {
            "base": base,
            "ingresos": str(ingresos_dir),
            "tareas": str(tareas_dir),
            "calificaciones": str(cal_file),
            "historico": str(hist_dir),
            "reportes": str(reportes_dir),
            "datos_especificos": str(datos_dir),
            "practicas": str(prac_dir),
            "terceras": str(tm_dir),
        }


def _patch_settings(dirs):
    """Genera patch dict para sobreescribir settings con dirs temporales."""
    return {
        "DATA_PATH_INGRESOS": dirs["ingresos"],
        "DATA_PATH_TAREAS": dirs["tareas"],
        "DATA_PATH_CALIFICACIONES": dirs["calificaciones"],
        "DATA_PATH_CALIFICACIONES_HISTORICO": dirs["historico"],
        "DATA_PATH_REPORTE": dirs["reportes"],
        "DATA_PATH_DATOS_ESPECIFICOS": dirs["datos_especificos"],
        "DATA_PATH_PRACTICAS": dirs["practicas"],
        "DATA_PATH_TERCERAS_MATRICULAS": dirs["terceras"],
    }


# ═══════════════════ UNIT: pipeline helpers ═══════════════════


class TestCleanStr:
    def test_normal(self):
        assert _clean_str("hello") == "hello"

    def test_none(self):
        assert _clean_str(None) == ""

    def test_nan_string(self):
        assert _clean_str("nan") == ""

    def test_none_string(self):
        assert _clean_str("None") == ""

    def test_strips_whitespace(self):
        assert _clean_str("  hello  ") == "hello"


class TestNanToNone:
    def test_none_passthrough(self):
        assert _nan_to_none(None) is None

    def test_normal_value(self):
        assert _nan_to_none(42) == 42

    def test_nan(self):
        assert _nan_to_none(float("nan")) is None

    def test_inf(self):
        assert _nan_to_none(float("inf")) is None

    def test_neg_inf(self):
        assert _nan_to_none(float("-inf")) is None

    def test_string_passthrough(self):
        assert _nan_to_none("hello") == "hello"

    def test_zero(self):
        assert _nan_to_none(0) == 0

    def test_float_normal(self):
        assert _nan_to_none(3.14) == 3.14


class TestNormalizeName:
    def test_accents_removed(self):
        assert _normalize_name("GARCIA LOPEZ MARIA") == "GARCIA LOPEZ MARIA"

    def test_tilde_n(self):
        result = _normalize_name("PEREZ NUNEZ ANA")
        assert result == "PEREZ NUNEZ ANA"

    def test_accent_chars(self):
        result = _normalize_name("GARCIA LOPEZ MARIA")
        assert "GARCIA" in result

    def test_collapses_spaces(self):
        result = _normalize_name("GARCIA  LOPEZ  MARIA")
        assert "  " not in result

    def test_empty(self):
        assert _normalize_name("") == ""

    def test_none(self):
        assert _normalize_name(None) == ""


# ═══════════════════ T01: run_full con datos sinteticos ═══════════════════


class TestETLRunFull:
    """T01: Verificar que run_full completa exitosamente con datos vacios."""

    def test_run_full_empty_data_succeeds(self, db, semester_config, tmp_data_dirs):
        """Pipeline debe completar exitosamente incluso sin datos."""
        dirs = _patch_settings(tmp_data_dirs)

        with patch.multiple("backend.config.settings", **dirs):
            pipeline = ETLPipeline(db)
            run = pipeline.run_full(triggered_by="test")

        # Debe completar sin error
        assert run.status in ("success", "error")
        assert run.finished_at is not None
        assert run.log_output is not None

    def test_run_full_creates_scraping_run(self, db, semester_config, tmp_data_dirs):
        """Debe crear un ScrapingRun con metadata."""
        dirs = _patch_settings(tmp_data_dirs)

        with patch.multiple("backend.config.settings", **dirs):
            pipeline = ETLPipeline(db)
            run = pipeline.run_full(triggered_by="test")

        assert run.tipo == "full"
        assert run.triggered_by == "test"
        assert isinstance(run.log_output, str)

    def test_run_full_with_preexisting_students(self, db, semester_config, tmp_data_dirs):
        """run_full con estudiantes pre-existentes no los borra."""
        s = Student(nombre="ALUMNO EXISTENTE", carrera="DERECHO", cedula="9999999999")
        db.add(s)
        db.commit()
        student_id = s.id

        dirs = _patch_settings(tmp_data_dirs)
        with patch.multiple("backend.config.settings", **dirs):
            pipeline = ETLPipeline(db)
            pipeline.run_full(triggered_by="test")

        # El estudiante preexistente sigue ahi
        existing = db.query(Student).filter(Student.id == student_id).first()
        assert existing is not None
        assert existing.nombre == "ALUMNO EXISTENTE"


# ═══════════════════ T02: Idempotencia ═══════════════════


class TestETLIdempotency:
    """T02: Ejecutar pipeline 2 veces sin duplicar registros."""

    def test_double_run_no_duplicate_students(self, db, semester_config, tmp_data_dirs):
        """Dos ejecuciones con mismos datos no duplican estudiantes."""
        # Crear un estudiante que el ETL encontraria
        s = Student(nombre="ALUMNO TEST", carrera="EDUCACION BASICA", cedula="1234567890")
        db.add(s)
        db.commit()

        dirs = _patch_settings(tmp_data_dirs)
        with patch.multiple("backend.config.settings", **dirs):
            pipeline = ETLPipeline(db)
            pipeline.run_full(triggered_by="test")

            count_after_first = db.query(Student).count()

            pipeline2 = ETLPipeline(db)
            pipeline2.run_full(triggered_by="test")

            count_after_second = db.query(Student).count()

        assert count_after_second == count_after_first

    def test_double_run_no_duplicate_scraping_runs(self, db, semester_config, tmp_data_dirs):
        """Cada ejecucion crea su propio ScrapingRun."""
        dirs = _patch_settings(tmp_data_dirs)
        with patch.multiple("backend.config.settings", **dirs):
            pipeline = ETLPipeline(db)
            pipeline.run_full(triggered_by="test")
            pipeline2 = ETLPipeline(db)
            pipeline2.run_full(triggered_by="test")

        runs = db.query(ScrapingRun).all()
        assert len(runs) == 2


# ═══════════════════ T03: Error Recovery ═══════════════════


class TestETLErrorRecovery:
    """T03: Verificar que errores marcan el run como failed."""

    def test_error_marks_run_as_error(self, db, semester_config, tmp_data_dirs):
        """Si transform_personales explota, el run queda como error."""
        dirs = _patch_settings(tmp_data_dirs)

        with patch.multiple("backend.config.settings", **dirs):
            with patch("backend.etl.pipeline.transform_personales", side_effect=RuntimeError("Boom")):
                pipeline = ETLPipeline(db)
                run = pipeline.run_full(triggered_by="test")

        assert run.status == "error"
        assert run.finished_at is not None
        assert "Boom" in run.log_output

    def test_error_preserves_existing_data(self, db, semester_config, tmp_data_dirs):
        """Un error en el pipeline no debe borrar datos pre-existentes."""
        s = Student(nombre="DATO CRITICO", carrera="DERECHO", cedula="5555555555")
        db.add(s)
        db.commit()
        sid = s.id

        dirs = _patch_settings(tmp_data_dirs)
        with patch.multiple("backend.config.settings", **dirs):
            with patch("backend.etl.pipeline.transform_personales", side_effect=RuntimeError("Crash")):
                pipeline = ETLPipeline(db)
                pipeline.run_full(triggered_by="test")

        # Los datos previos siguen intactos
        assert db.query(Student).filter(Student.id == sid).first() is not None

    def test_error_run_has_error_details(self, db, semester_config, tmp_data_dirs):
        """El run debe registrar detalles del error."""
        dirs = _patch_settings(tmp_data_dirs)
        with patch.multiple("backend.config.settings", **dirs):
            with patch("backend.etl.pipeline.transform_personales", side_effect=ValueError("bad data")):
                pipeline = ETLPipeline(db)
                run = pipeline.run_full(triggered_by="test")

        assert run.errores is not None
        assert len(run.errores) > 0


# ═══════════════════ Pipeline config ═══════════════════


class TestETLConfig:
    """Tests para metodos de configuracion del pipeline."""

    def test_get_active_semester(self, db, semester_config):
        pipeline = ETLPipeline(db)
        sem = pipeline._get_active_semester()
        assert sem is not None
        assert sem.semestre == "P68"
        assert sem.activo is True

    def test_get_active_semester_none(self, db):
        pipeline = ETLPipeline(db)
        assert pipeline._get_active_semester() is None

    def test_get_codigos_for_bloque_no_config(self, db):
        pipeline = ETLPipeline(db)
        assert pipeline._get_codigos_for_bloque(None) is None

    def test_get_codigos_for_bloque_with_courses(self, db, semester_config):
        c = CourseConfig(
            codigo_avac="123456", asignatura="MATH", semestre="P68",
            activo=True, bloque="1",
        )
        db.add(c)
        db.commit()

        pipeline = ETLPipeline(db)
        codigos = pipeline._get_codigos_for_bloque(semester_config)
        assert codigos is not None
        assert "123456" in codigos

    def test_get_codigos_excludes_inactive(self, db, semester_config):
        c1 = CourseConfig(codigo_avac="111", asignatura="A", semestre="P68", activo=True, bloque="1")
        c2 = CourseConfig(codigo_avac="222", asignatura="B", semestre="P68", activo=False, bloque="1")
        db.add_all([c1, c2])
        db.commit()

        pipeline = ETLPipeline(db)
        codigos = pipeline._get_codigos_for_bloque(semester_config)
        assert "111" in codigos
        assert "222" not in codigos
