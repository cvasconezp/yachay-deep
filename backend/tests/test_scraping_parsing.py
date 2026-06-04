"""
Tests para Scraping Parsing — Fase 2 T11-T12.

Cobertura:
  T11: Parsing de tabla de participantes (ingresos AVAC)
  T12: Parsing de reporte general de calificaciones (estado tareas)
"""
import pytest
from bs4 import BeautifulSoup

from backend.scraping.ingresos_avac import (
    _parse_participants_table, _match_header, _COL_MAPS,
)
from backend.scraping.estado_tareas import (
    _procesar_reporte_general, _limpiar, _normalizar,
    COLUMNAS_ESTANDAR, EQUIVALENCIA_UNIDADES, PALABRAS_EXCLUIDAS,
)


# ═══════════════════ Fixtures HTML ═══════════════════


PARTICIPANTS_HTML_MOODLE4 = """
<table class="generaltable">
  <thead>
    <tr>
      <th>Seleccionar todos</th>
      <th>Apellido(s), Nombre(s)</th>
      <th>Correo electrónico</th>
      <th>Último acceso al curso</th>
      <th>Estatus</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>GARCIA LOPEZ JUAN CARLOS</td>
      <td>jgarcia@ups.edu.ec</td>
      <td>hace 2 dias</td>
      <td>Activo</td>
    </tr>
    <tr>
      <td>MARTINEZ PEREZ MARIA</td>
      <td>mmartinez@ups.edu.ec</td>
      <td>Nunca</td>
      <td>Inactivo</td>
    </tr>
    <tr>
      <td>FILA SIN CORREO</td>
      <td>no-tiene</td>
      <td>-</td>
      <td>-</td>
    </tr>
  </tbody>
</table>
"""

PARTICIPANTS_HTML_SIMPLE = """
<table class="generaltable">
  <thead>
    <tr>
      <th>Nombre</th>
      <th>Email address</th>
      <th>Last access to course</th>
      <th>Status</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>ALUMNO UNO</td>
      <td>alumno1@ups.edu.ec</td>
      <td>3 days ago</td>
      <td>Active</td>
    </tr>
  </tbody>
</table>
"""

GRADES_HTML = """
<table id="user-grades">
  <tr class="heading">
    <th>Nombre</th>
    <th>Correo electrónico</th>
    <th title="Total del curso">Total del curso</th>
  </tr>
  <tr>
    <td>GARCIA LOPEZ JUAN</td>
    <td>jgarcia@ups.edu.ec</td>
    <td>85.50</td>
  </tr>
  <tr>
    <td>MARTINEZ PEREZ MARIA</td>
    <td>mmartinez@ups.edu.ec</td>
    <td>-</td>
  </tr>
  <tr>
    <td>Promedio del curso</td>
    <td>sin-correo</td>
    <td>72.30</td>
  </tr>
</table>
"""

GRADES_HTML_SPECIAL = """
<table id="user-grades">
  <tr class="heading">
    <th>Nombre</th>
    <th>Correo electrónico</th>
    <th title="Total Unidad 1">Total Unidad 1</th>
    <th title="Total Unidad 2">Total Unidad 2</th>
    <th title="Total del curso">Total del curso</th>
  </tr>
  <tr>
    <td>ALUMNO ESPECIAL</td>
    <td>especial@ups.edu.ec</td>
    <td>90</td>
    <td>75</td>
    <td>82.50</td>
  </tr>
</table>
"""

EMPTY_TABLE_HTML = """<div>No hay participantes</div>"""


# ═══════════════════ T11: Scraping Ingresos Parsing ═══════════════════


class TestMatchHeader:
    """Helpers de matching de columnas."""

    def test_exact_match(self):
        assert _match_header("correo electrónico", _COL_MAPS["correo"])

    def test_case_insensitive(self):
        assert _match_header("CORREO ELECTRÓNICO", _COL_MAPS["correo"])

    def test_partial_match(self):
        assert _match_header("Dirección de correo electrónico", _COL_MAPS["correo"])

    def test_no_match(self):
        assert not _match_header("Roles del sistema", _COL_MAPS["estado"])

    def test_nombre_match(self):
        assert _match_header("Apellido(s), Nombre(s)", _COL_MAPS["nombre"])

    def test_ultimo_acceso_match(self):
        assert _match_header("Último acceso al curso", _COL_MAPS["ultimo_acceso"])


class TestParseParticipantsTable:
    """T11: Parsing de tabla de participantes de Moodle."""

    def test_moodle4_with_select_column(self):
        """Moodle 4.x agrega columna 'Seleccionar' sin <td> — offset correcto."""
        soup = BeautifulSoup(PARTICIPANTS_HTML_MOODLE4, "html.parser")
        result = _parse_participants_table(soup)

        assert len(result) == 2  # fila sin correo valido se ignora
        assert result[0]["Correo"] == "jgarcia@ups.edu.ec"
        assert result[1]["Correo"] == "mmartinez@ups.edu.ec"

    def test_nombre_extracted_correctly(self):
        """El nombre se extrae correctamente con offset de Moodle 4.x."""
        soup = BeautifulSoup(PARTICIPANTS_HTML_MOODLE4, "html.parser")
        result = _parse_participants_table(soup)

        assert "GARCIA" in result[0]["Nombre"]
        assert "MARTINEZ" in result[1]["Nombre"]

    def test_ultimo_acceso_captured(self):
        """Se captura el ultimo acceso al curso."""
        soup = BeautifulSoup(PARTICIPANTS_HTML_MOODLE4, "html.parser")
        result = _parse_participants_table(soup)

        assert result[0]["Último acceso"] != ""
        assert "Nunca" in result[1]["Último acceso"]

    def test_estado_captured(self):
        """Se captura el estado del estudiante."""
        soup = BeautifulSoup(PARTICIPANTS_HTML_MOODLE4, "html.parser")
        result = _parse_participants_table(soup)

        assert result[0]["Estado"] == "Activo"
        assert result[1]["Estado"] == "Inactivo"

    def test_simple_table_no_offset(self):
        """Tabla sin columna 'Seleccionar' funciona correctamente (sin offset)."""
        soup = BeautifulSoup(PARTICIPANTS_HTML_SIMPLE, "html.parser")
        result = _parse_participants_table(soup)

        assert len(result) == 1
        assert result[0]["Correo"] == "alumno1@ups.edu.ec"
        assert result[0]["Nombre"] == "ALUMNO UNO"

    def test_english_headers(self):
        """Headers en ingles tambien se detectan."""
        soup = BeautifulSoup(PARTICIPANTS_HTML_SIMPLE, "html.parser")
        result = _parse_participants_table(soup)

        assert len(result) == 1
        assert result[0]["Último acceso"] == "3 days ago"

    def test_empty_table_returns_empty(self):
        """Sin tabla, retorna lista vacia."""
        soup = BeautifulSoup(EMPTY_TABLE_HTML, "html.parser")
        result = _parse_participants_table(soup)
        assert result == []

    def test_rows_without_email_skipped(self):
        """Filas sin @ en correo se ignoran."""
        soup = BeautifulSoup(PARTICIPANTS_HTML_MOODLE4, "html.parser")
        result = _parse_participants_table(soup)

        correos = [r["Correo"] for r in result]
        assert "no-tiene" not in correos


# ═══════════════════ T12: Scraping Tareas Parsing ═══════════════════


class TestLimpiar:
    def test_removes_newlines(self):
        assert _limpiar("hola\nmundo") == "hola mundo"

    def test_removes_tabs(self):
        assert _limpiar("a\tb") == "a b"

    def test_removes_semicolons(self):
        assert _limpiar("a;b") == "a,b"

    def test_empty(self):
        assert _limpiar("") == ""

    def test_none(self):
        assert _limpiar(None) == ""


class TestNormalizar:
    def test_removes_accents(self):
        result = _normalizar("Educación Básica")
        assert "a" in result  # accent removed
        assert result.islower()

    def test_removes_special_chars(self):
        result = _normalizar("Hello@World#2024!")
        # Only alphanumeric and spaces should remain
        assert all(c.isalnum() or c == " " for c in result)

    def test_empty(self):
        assert _normalizar("") == ""

    def test_none(self):
        assert _normalizar(None) == ""


class TestProcesarReporteGeneral:
    """T12: Parsing del reporte de calificaciones."""

    def test_basic_grades_parsing(self):
        """Parsea tabla de calificaciones con correo, nombre y total."""
        soup = BeautifulSoup(GRADES_HTML, "html.parser")
        datos = _procesar_reporte_general(soup)

        assert "jgarcia@ups.edu.ec" in datos
        assert datos["jgarcia@ups.edu.ec"]["Nombre"] == "GARCIA LOPEZ JUAN"
        assert datos["jgarcia@ups.edu.ec"]["Total del Curso"] == "85.50"

    def test_dash_becomes_empty(self):
        """Valores '-' se convierten a cadena vacia."""
        soup = BeautifulSoup(GRADES_HTML, "html.parser")
        datos = _procesar_reporte_general(soup)

        assert datos["mmartinez@ups.edu.ec"]["Total del Curso"] == ""

    def test_rows_without_email_skipped(self):
        """Filas sin correo valido se ignoran (ej: 'Promedio del curso')."""
        soup = BeautifulSoup(GRADES_HTML, "html.parser")
        datos = _procesar_reporte_general(soup)

        assert "sin-correo" not in datos
        assert len(datos) == 2

    def test_special_course_extracts_units(self):
        """Cursos especiales extraen totales por unidad."""
        soup = BeautifulSoup(GRADES_HTML_SPECIAL, "html.parser")
        datos = _procesar_reporte_general(soup, es_especial=True)

        assert "especial@ups.edu.ec" in datos
        d = datos["especial@ups.edu.ec"]
        assert d["Total del Curso"] == "82.50"
        # Debe extraer calificaciones por unidad
        has_unit_data = any(k.startswith("Calificación") for k in d)
        assert has_unit_data

    def test_empty_html_returns_empty(self):
        """Sin tabla de calificaciones, retorna dict vacio."""
        soup = BeautifulSoup(EMPTY_TABLE_HTML, "html.parser")
        datos = _procesar_reporte_general(soup)
        assert datos == {}

    def test_correo_lowercased(self):
        """Los correos se guardan en minusculas."""
        soup = BeautifulSoup(GRADES_HTML, "html.parser")
        datos = _procesar_reporte_general(soup)

        for key in datos:
            assert key == key.lower()


class TestColumnasEstandar:
    """Verificar estructura de columnas esperadas."""

    def test_has_base_columns(self):
        assert "Nombre" in COLUMNAS_ESTANDAR
        assert "Correo" in COLUMNAS_ESTANDAR
        assert "Total del Curso" in COLUMNAS_ESTANDAR
        assert "Código Curso" in COLUMNAS_ESTANDAR
        assert "Fecha Extracción" in COLUMNAS_ESTANDAR

    def test_has_detail_columns_per_unit(self):
        """Cada unidad tiene los campos de detalle."""
        for u in EQUIVALENCIA_UNIDADES:
            assert f"Estado {u}" in COLUMNAS_ESTANDAR
            assert f"Calificación {u}" in COLUMNAS_ESTANDAR

    def test_palabras_excluidas_defined(self):
        """Palabras excluidas para filtrar tareas no-evaluables."""
        assert "autoevaluacion" in PALABRAS_EXCLUIDAS
        assert "cuestionario" in PALABRAS_EXCLUIDAS
        assert len(PALABRAS_EXCLUIDAS) >= 4


# ─────────────────────────────────────────────────────────────────────────────
# Tests para _extraer_pendientes y mejoras de cursos especiales
# ─────────────────────────────────────────────────────────────────────────────

class TestExtraerPendientes:
    """Tests para la función _extraer_pendientes."""

    def test_extraer_pendientes_html(self):
        """Extrae pendientes desde HTML de resumen de actividad."""
        from backend.scraping.estado_tareas import _extraer_pendientes

        # Mock session que retorna HTML con tabla de resumen
        class MockResponse:
            text = """
            <html><body>
            <table>
                <tr><th>Participantes</th><td>35</td></tr>
                <tr><th>Enviados</th><td>30</td></tr>
                <tr><th>Pendientes por calificar</th><td>5</td></tr>
            </table>
            </body></html>
            """
        class MockSession:
            def get(self, url, timeout=30):
                return MockResponse()

        result = _extraer_pendientes(MockSession(), "http://test", "123", "1")
        assert result.get("Pendientes Actividad 1") == "5"
        assert result.get("Participantes Actividad 1") == "35"
        assert result.get("Enviados Actividad 1") == "30"

    def test_extraer_pendientes_no_data(self):
        """Retorna dict vacío si no hay tabla de resumen."""
        from backend.scraping.estado_tareas import _extraer_pendientes

        class MockResponse:
            text = "<html><body><p>No summary</p></body></html>"
        class MockSession:
            def get(self, url, timeout=30):
                return MockResponse()

        result = _extraer_pendientes(MockSession(), "http://test", "123", "2")
        assert result == {}


class TestExpandirResumenPendientes:
    """Tests para _expandir_resumen_pendientes del transformer."""

    def test_expande_pendientes_a_filas(self):
        """Formato resumen con pendientes se expande a filas por actividad."""
        import pandas as pd
        from backend.etl.transformers import _expandir_resumen_pendientes

        df = pd.DataFrame([{
            "código": "395484",
            "fecha": "2026-05-18",
            "especial": "No",
            "alumnos": 35,
            "pendientes_actividad_1": "5",
            "pendientes_actividad_2": "0",
            "_fuente": "Resumen_General.csv",
        }])
        result = _expandir_resumen_pendientes(df)
        assert len(result) == 2
        row1 = result[result["actividad"] == "Actividad Unidad 1"].iloc[0]
        assert row1["pendientes"] == 5
        assert row1["calificada"] == "No"
        row2 = result[result["actividad"] == "Actividad Unidad 2"].iloc[0]
        assert row2["pendientes"] == 0
        assert row2["calificada"] == "Sí"

    def test_no_pendientes_returns_original(self):
        """Sin columnas de pendientes retorna el df original."""
        import pandas as pd
        from backend.etl.transformers import _expandir_resumen_pendientes

        df = pd.DataFrame([{
            "código": "395484",
            "fecha": "2026-05-18",
            "_fuente": "Resumen_General.csv",
        }])
        result = _expandir_resumen_pendientes(df)
        assert len(result) == 1
        assert "código" in result.columns


class TestParseEstadoTareaFinalizado:
    """Tests para parse_estado_tarea con estado 'Finalizado'."""

    def test_finalizado_total_counts_as_delivered_and_graded(self):
        """Estado 'Finalizado (Total)' de cursos especiales cuenta como entregada y calificada."""
        from backend.etl.transformers import parse_estado_tarea

        entregada, calificada, retrasada = parse_estado_tarea("Finalizado (Total)")
        assert entregada is True
        assert calificada is True
        assert retrasada is False
