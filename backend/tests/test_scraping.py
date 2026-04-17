"""
Tests del módulo de scraping — endpoint trigger-scraping y lógica del runner.
Verifica que el flujo completo funcione para el semestre activo (P68).
"""

import os
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

from backend.models.course_config import CourseConfig, SemesterConfig
from backend.models.scraping_run import ScrapingRun

from .conftest import auth


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _setup_p68_semester(db, bloque1_fin=None):
    """Configura semestre P68 activo con cursos de prueba."""
    from datetime import datetime, timedelta
    sem = SemesterConfig(
        semestre="2026-1",
        activo=True,
        bloque_actual="1",
        bloque1_inicio=datetime(2026, 3, 1),
        bloque1_fin=bloque1_fin or datetime(2026, 5, 15),
    )
    db.add(sem)

    cursos = [
        CourseConfig(codigo_avac="395484", nombre="Lingüística Aplicada", semestre="2026-1", activo=True),
        CourseConfig(codigo_avac="395501", nombre="Práctica Comunitaria", semestre="2026-1", activo=True),
        CourseConfig(codigo_avac="395510", nombre="Didáctica EIB", semestre="2026-1", activo=True),
    ]
    db.add_all(cursos)
    db.commit()
    return sem, cursos


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Endpoint /admin/etl/trigger-scraping
# ─────────────────────────────────────────────────────────────────────────────

class TestTriggerScrapingEndpoint:
    """Tests del endpoint POST /admin/etl/trigger-scraping."""

    def test_trigger_scraping_sin_token_github(self, client, admin_token, db):
        """Debe fallar si GITHUB_TOKEN no está configurado."""
        _setup_p68_semester(db)
        # GITHUB_TOKEN no está en env por defecto → settings.GITHUB_TOKEN == None
        resp = client.post(
            "/admin/etl/trigger-scraping?mode=full",
            headers=auth(admin_token),
        )
        assert resp.status_code == 400
        assert "GITHUB_TOKEN" in resp.json()["detail"]

    def test_trigger_scraping_modo_invalido(self, client, admin_token, db):
        """Debe rechazar modos inválidos."""
        _setup_p68_semester(db)
        from backend.config import settings
        original = settings.GITHUB_TOKEN
        try:
            settings.GITHUB_TOKEN = "ghp_fake_token"
            resp = client.post(
                "/admin/etl/trigger-scraping?mode=invalido",
                headers=auth(admin_token),
            )
        finally:
            settings.GITHUB_TOKEN = original
        assert resp.status_code == 400
        assert "invalido" in resp.json()["detail"].lower()

    def test_trigger_scraping_exitoso(self, client, admin_token, db):
        """Debe disparar el workflow correctamente cuando todo está configurado."""
        _setup_p68_semester(db)

        mock_response = MagicMock()
        mock_response.status_code = 204

        from backend.config import settings
        original = settings.GITHUB_TOKEN
        try:
            settings.GITHUB_TOKEN = "ghp_fake_token"
            with patch("httpx.AsyncClient") as MockClient:
                mock_client_instance = AsyncMock()
                mock_client_instance.post.return_value = mock_response
                mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client_instance.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_client_instance

                resp = client.post(
                    "/admin/etl/trigger-scraping?mode=full",
                    headers=auth(admin_token),
                )
        finally:
            settings.GITHUB_TOKEN = original

        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "full"
        assert data["github_status"] == 204
        assert "disparado" in data["message"].lower() or "scraping" in data["message"].lower()

    def test_trigger_scraping_modos_validos(self, client, admin_token, db):
        """Los tres modos válidos deben aceptarse: full, ingresos, tareas."""
        _setup_p68_semester(db)

        mock_response = MagicMock()
        mock_response.status_code = 204

        from backend.config import settings
        original = settings.GITHUB_TOKEN
        try:
            settings.GITHUB_TOKEN = "ghp_fake"
            for mode in ("full", "ingresos", "tareas"):
                with patch("httpx.AsyncClient") as MockClient:
                    mock_client_instance = AsyncMock()
                    mock_client_instance.post.return_value = mock_response
                    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                    mock_client_instance.__aexit__ = AsyncMock(return_value=False)
                    MockClient.return_value = mock_client_instance

                    resp = client.post(
                        f"/admin/etl/trigger-scraping?mode={mode}",
                        headers=auth(admin_token),
                    )
                assert resp.status_code == 200, f"Modo '{mode}' falló: {resp.json()}"
                assert resp.json()["mode"] == mode
        finally:
            settings.GITHUB_TOKEN = original

    def test_trigger_scraping_requiere_admin(self, client, monitor_token, db):
        """Un usuario monitor NO debe poder disparar el scraping."""
        _setup_p68_semester(db)
        resp = client.post(
            "/admin/etl/trigger-scraping?mode=full",
            headers=auth(monitor_token),
        )
        assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Runner de scraping (lógica interna)
# ─────────────────────────────────────────────────────────────────────────────

class TestScrapingRunner:
    """Tests de la lógica del runner de scraping."""

    def test_semester_ended_detiene_scraping(self, db):
        """Si el semestre P68 ya terminó, el runner no debe ejecutar scraping."""
        from datetime import datetime
        sem = SemesterConfig(
            semestre="2026-1",
            activo=True,
            bloque_actual="1",
            bloque1_inicio=datetime(2025, 1, 1),
            bloque1_fin=datetime(2025, 6, 30),  # Fecha pasada → semestre finalizado
        )
        db.add(sem)
        db.commit()

        with patch("backend.database.SessionLocal", return_value=db):
            from backend.scraping.runner import _semester_ended
            assert _semester_ended() is True

    def test_semester_activo_permite_scraping(self, db):
        """Si el semestre P68 está activo y vigente, debe permitir scraping."""
        from datetime import datetime
        sem = SemesterConfig(
            semestre="2026-1",
            activo=True,
            bloque_actual="1",
            bloque1_inicio=datetime(2026, 3, 1),
            bloque1_fin=datetime(2026, 12, 31),  # Fecha futura → semestre vigente
        )
        db.add(sem)
        db.commit()

        with patch("backend.database.SessionLocal", return_value=db):
            from backend.scraping.runner import _semester_ended
            assert _semester_ended() is False

    def test_sin_semestre_activo_no_scrapea(self, db):
        """Sin semestre activo configurado, no debe ejecutar scraping."""
        # No agregamos ningún semestre
        with patch("backend.database.SessionLocal", return_value=db):
            from backend.scraping.runner import _semester_ended
            assert _semester_ended() is True


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Lectura de cursos activos para P68
# ─────────────────────────────────────────────────────────────────────────────

class TestCursosActivosP68:
    """Verifica que el scraper lee correctamente los cursos de P68 desde la BD."""

    def test_get_active_codigos_retorna_cursos_p68(self, db):
        """Debe retornar los códigos de cursos activos del semestre."""
        _setup_p68_semester(db)
        from backend.scraping.ingresos_avac import get_active_codigos
        codigos = get_active_codigos(db)
        assert len(codigos) == 3
        assert "395484" in codigos
        assert "395501" in codigos
        assert "395510" in codigos

    def test_get_active_codigos_excluye_inactivos(self, db):
        """Cursos marcados como inactivos no deben incluirse."""
        _setup_p68_semester(db)
        # Desactivar un curso
        curso = db.query(CourseConfig).filter(CourseConfig.codigo_avac == "395510").first()
        curso.activo = False
        db.commit()

        from backend.scraping.ingresos_avac import get_active_codigos
        codigos = get_active_codigos(db)
        assert len(codigos) == 2
        assert "395510" not in codigos

    def test_get_active_codigos_sin_db(self):
        """Sin conexión a BD, debe retornar lista vacía sin error."""
        from backend.scraping.ingresos_avac import get_active_codigos
        assert get_active_codigos(None) == []


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Parseo de tabla de participantes AVAC
# ─────────────────────────────────────────────────────────────────────────────

class TestParseParticipantsTable:
    """Verifica el parseo robusto de la tabla HTML de participantes de AVAC."""

    def test_parseo_tabla_formato_espanol(self):
        """Tabla con encabezados en español debe parsearse correctamente."""
        from bs4 import BeautifulSoup
        from backend.scraping.ingresos_avac import _parse_participants_table

        html = """
        <table class="generaltable">
            <thead><tr>
                <th>Apellido(s), Nombre(s)</th>
                <th>Correo electrónico</th>
                <th>Último acceso al sitio</th>
                <th>Estado</th>
            </tr></thead>
            <tbody>
                <tr>
                    <td>García López, María</td>
                    <td>mgarcia@est.ups.edu.ec</td>
                    <td>hace 2 días</td>
                    <td>Estudiante</td>
                </tr>
                <tr>
                    <td>Pérez, Juan</td>
                    <td>jperez@est.ups.edu.ec</td>
                    <td>Nunca</td>
                    <td>Estudiante</td>
                </tr>
            </tbody>
        </table>
        """
        soup = BeautifulSoup(html, "html.parser")
        registros = _parse_participants_table(soup)

        assert len(registros) == 2
        assert registros[0]["Correo"] == "mgarcia@est.ups.edu.ec"
        assert registros[0]["Nombre"] == "García López, María"
        assert registros[1]["Correo"] == "jperez@est.ups.edu.ec"

    def test_parseo_tabla_formato_ingles(self):
        """Tabla con encabezados en inglés también debe funcionar."""
        from bs4 import BeautifulSoup
        from backend.scraping.ingresos_avac import _parse_participants_table

        html = """
        <table class="generaltable">
            <thead><tr>
                <th>Name</th>
                <th>Email address</th>
                <th>Last access to site</th>
                <th>Status</th>
            </tr></thead>
            <tbody>
                <tr>
                    <td>Test Student</td>
                    <td>test@est.ups.edu.ec</td>
                    <td>2 days ago</td>
                    <td>Student</td>
                </tr>
            </tbody>
        </table>
        """
        soup = BeautifulSoup(html, "html.parser")
        registros = _parse_participants_table(soup)

        assert len(registros) == 1
        assert registros[0]["Correo"] == "test@est.ups.edu.ec"

    def test_parseo_sin_tabla(self):
        """Si no hay tabla generaltable, debe retornar lista vacía."""
        from bs4 import BeautifulSoup
        from backend.scraping.ingresos_avac import _parse_participants_table

        soup = BeautifulSoup("<div>Sin tabla</div>", "html.parser")
        assert _parse_participants_table(soup) == []

    def test_parseo_filtra_filas_sin_correo(self):
        """Filas sin correo válido deben ser excluidas."""
        from bs4 import BeautifulSoup
        from backend.scraping.ingresos_avac import _parse_participants_table

        html = """
        <table class="generaltable">
            <thead><tr>
                <th>Nombre</th>
                <th>Correo electrónico</th>
                <th>Último acceso</th>
                <th>Estado</th>
            </tr></thead>
            <tbody>
                <tr><td>Con correo</td><td>alumno@ups.edu.ec</td><td>Hoy</td><td>Estudiante</td></tr>
                <tr><td>Sin correo</td><td>-</td><td>Nunca</td><td>Estudiante</td></tr>
                <tr><td>Vacío</td><td></td><td>Nunca</td><td>Docente</td></tr>
            </tbody>
        </table>
        """
        soup = BeautifulSoup(html, "html.parser")
        registros = _parse_participants_table(soup)
        assert len(registros) == 1
        assert registros[0]["Correo"] == "alumno@ups.edu.ec"
