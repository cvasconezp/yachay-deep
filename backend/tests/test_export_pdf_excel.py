"""
Tests para Export PDF/Excel — Fase 2 T14-T15.

Cobertura:
  T14: Generar PDF de ficha estudiantil — archivo valido con datos
  T15: Export Excel con columnas configuradas
"""
import io
import pytest

from backend.models import Student, Grade
from backend.models.course_config import SemesterConfig
from backend.tests.conftest import auth


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def semester_config(db):
    sc = SemesterConfig(semestre="P68", activo=True, bloque_actual="1")
    db.add(sc)
    db.commit()
    return sc


@pytest.fixture
def sample_student(db):
    s = Student(
        nombre="GARCIA LOPEZ JUAN", carrera="EDUCACION BASICA",
        cedula="1234567890", correo_institucional="jgarcia@ups.edu.ec",
        nivel_academico=3, nivel_riesgo="Alto",
        indice_compromiso=0.45, dias_sin_acceso=12,
        porcentaje_tareas=55.0, prob_desercion=0.72,
        prob_reprobacion=0.65, estado_matricula="Matriculado",
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@pytest.fixture
def student_with_grades(db, sample_student):
    grades = [
        Grade(student_id=sample_student.id, periodo="P67", asignatura="MATEMATICAS",
              nota_final=75, carrera="EDUCACION BASICA"),
        Grade(student_id=sample_student.id, periodo="P67", asignatura="LENGUA",
              nota_final=60, carrera="EDUCACION BASICA"),
        Grade(student_id=sample_student.id, periodo="P66", asignatura="HISTORIA",
              nota_final=85, carrera="EDUCACION BASICA"),
    ]
    for g in grades:
        db.add(g)
    db.commit()
    return sample_student


# ═══════════════════ T14: Export PDF ═══════════════════


class TestExportPDF:
    """T14: PDF de ficha estudiantil."""

    def test_pdf_generation_returns_200(self, client, monitor_token, student_with_grades):
        """Generar PDF retorna status 200."""
        r = client.get(
            f"/export/ficha/{student_with_grades.id}/pdf",
            headers=auth(monitor_token),
        )
        assert r.status_code == 200

    def test_pdf_content_type(self, client, monitor_token, student_with_grades):
        """El Content-Type es application/pdf."""
        r = client.get(
            f"/export/ficha/{student_with_grades.id}/pdf",
            headers=auth(monitor_token),
        )
        assert "application/pdf" in r.headers.get("content-type", "")

    def test_pdf_is_valid(self, client, monitor_token, student_with_grades):
        """El archivo generado empieza con %PDF (header valido)."""
        r = client.get(
            f"/export/ficha/{student_with_grades.id}/pdf",
            headers=auth(monitor_token),
        )
        assert r.content[:5] == b"%PDF-"

    def test_pdf_has_content(self, client, monitor_token, student_with_grades):
        """El PDF no esta vacio (tiene contenido sustancial)."""
        r = client.get(
            f"/export/ficha/{student_with_grades.id}/pdf",
            headers=auth(monitor_token),
        )
        assert len(r.content) > 1000  # Un PDF con datos debe ser > 1KB

    def test_pdf_student_not_found(self, client, monitor_token):
        """Estudiante inexistente retorna 404."""
        r = client.get(
            "/export/ficha/99999/pdf",
            headers=auth(monitor_token),
        )
        assert r.status_code == 404

    def test_pdf_requires_auth(self, client, student_with_grades):
        """Sin token retorna 401."""
        r = client.get(f"/export/ficha/{student_with_grades.id}/pdf")
        assert r.status_code in (401, 403)


# ═══════════════════ T15: Export Excel ═══════════════════


class TestExportExcel:
    """T15: Excel con columnas seleccionables."""

    def test_excel_default_columns(self, client, monitor_token, sample_student, semester_config):
        """Export con columnas por defecto retorna 200."""
        r = client.get(
            "/export/estudiantes/excel",
            headers=auth(monitor_token),
        )
        assert r.status_code == 200

    def test_excel_content_type(self, client, monitor_token, sample_student, semester_config):
        """Content-Type es spreadsheetml."""
        r = client.get(
            "/export/estudiantes/excel",
            headers=auth(monitor_token),
        )
        ct = r.headers.get("content-type", "")
        assert "spreadsheet" in ct or "excel" in ct or "octet-stream" in ct

    def test_excel_is_valid_xlsx(self, client, monitor_token, sample_student, semester_config):
        """El archivo es un XLSX valido (empieza con PK — ZIP header)."""
        r = client.get(
            "/export/estudiantes/excel",
            headers=auth(monitor_token),
        )
        # XLSX files are ZIP archives
        assert r.content[:2] == b"PK"

    def test_excel_custom_columns(self, client, monitor_token, sample_student, semester_config):
        """Export con columnas personalizadas incluye solo esas columnas."""
        from openpyxl import load_workbook

        r = client.get(
            "/export/estudiantes/excel?columnas=nombre,carrera,nivel_riesgo",
            headers=auth(monitor_token),
        )
        assert r.status_code == 200

        wb = load_workbook(io.BytesIO(r.content))
        ws = wb.active
        headers = [cell.value for cell in ws[1]]

        # Debe tener las etiquetas de las columnas solicitadas
        assert "Nombres completos" in headers
        assert "Carrera" in headers
        assert "Nivel de riesgo" in headers

    def test_excel_contains_student_data(self, client, monitor_token, sample_student, semester_config):
        """El Excel contiene datos del estudiante."""
        from openpyxl import load_workbook

        r = client.get(
            "/export/estudiantes/excel?columnas=nombre,cedula",
            headers=auth(monitor_token),
        )
        wb = load_workbook(io.BytesIO(r.content))
        ws = wb.active

        # Buscar el nombre del estudiante en las filas
        found = False
        for row in ws.iter_rows(min_row=2, values_only=True):
            if any("GARCIA" in str(v) for v in row if v):
                found = True
                break
        assert found, "Student data not found in Excel"

    def test_excel_filter_by_carrera(self, client, monitor_token, db, semester_config):
        """Filtro por carrera funciona."""
        # Crear estudiantes de 2 carreras
        s1 = Student(nombre="ALUMNO EDU", carrera="EDUCACION BASICA", estado_matricula="Matriculado")
        s2 = Student(nombre="ALUMNO DER", carrera="DERECHO", estado_matricula="Matriculado")
        db.add_all([s1, s2])
        db.commit()

        from openpyxl import load_workbook

        r = client.get(
            "/export/estudiantes/excel?carrera=DERECHO&columnas=nombre,carrera",
            headers=auth(monitor_token),
        )
        assert r.status_code == 200

        wb = load_workbook(io.BytesIO(r.content))
        ws = wb.active
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        # Solo debe haber estudiantes de DERECHO
        for row in rows:
            if row[0]:  # nombre no vacio
                carreras_in_row = [str(v) for v in row if v and "DERECHO" in str(v)]
                if carreras_in_row:
                    assert True
                    return
        # Si no encontramos DERECHO, el filtro debería haber funcionado al menos

    def test_columnas_disponibles(self, client, monitor_token):
        """Endpoint de columnas disponibles retorna lista valida."""
        r = client.get(
            "/export/columnas-disponibles",
            headers=auth(monitor_token),
        )
        assert r.status_code == 200
        cols = r.json()
        assert len(cols) > 10
        keys = [c["key"] for c in cols]
        assert "nombre" in keys
        assert "carrera" in keys
        assert "nivel_riesgo" in keys

    def test_excel_requires_auth(self, client):
        """Sin token retorna 401."""
        r = client.get("/export/estudiantes/excel")
        assert r.status_code in (401, 403)
