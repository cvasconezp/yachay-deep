"""
Tests para Email Service — Fase 2 T13.

Cobertura:
  - _build_report_html() genera HTML valido con datos del estudiante
  - send_bienestar_report() maneja SMTP errors gracefully
  - send_bienestar_report() retorna False sin SMTP configurado
  - send_tutoria_notification() construye correo correcto
"""
import pytest
from unittest.mock import patch, MagicMock

from backend.services.email import (
    send_bienestar_report, _build_report_html, send_tutoria_notification,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


STUDENT_DATA = {
    "nombre": "GARCIA LOPEZ JUAN",
    "cedula": "1234567890",
    "correo": "jgarcia@test.com",
    "correo_institucional": "jgarcia@ups.edu.ec",
    "telefono": "0991234567",
    "whatsapp": "+593991234567",
    "carrera": "EDUCACION BASICA",
    "sede": "Cuenca",
}

INTERVENTION_DATA = {
    "tipo_evento_critico": "Ideacion suicida",
    "reporte_bienestar": "Estudiante manifesto sentirse muy mal.",
    "motivo": "Riesgo alto de desercion + señales de alerta",
    "observacion": "Requiere atencion inmediata.",
}


# ═══════════════════ T13: Email Service ═══════════════════


class TestBuildReportHtml:
    """Verificar que el HTML del reporte se genera correctamente."""

    def test_contains_student_name(self):
        html = _build_report_html(STUDENT_DATA, INTERVENTION_DATA, "Monitor Test")
        assert "GARCIA LOPEZ JUAN" in html

    def test_contains_cedula(self):
        html = _build_report_html(STUDENT_DATA, INTERVENTION_DATA, "Monitor")
        assert "1234567890" in html

    def test_contains_tipo_evento(self):
        html = _build_report_html(STUDENT_DATA, INTERVENTION_DATA, "Monitor")
        assert "Ideacion suicida" in html

    def test_contains_reporte(self):
        html = _build_report_html(STUDENT_DATA, INTERVENTION_DATA, "Monitor")
        assert "Estudiante manifesto sentirse muy mal" in html

    def test_contains_monitor(self):
        html = _build_report_html(STUDENT_DATA, INTERVENTION_DATA, "Prof. Garcia")
        assert "Prof. Garcia" in html

    def test_contains_carrera(self):
        html = _build_report_html(STUDENT_DATA, INTERVENTION_DATA, "Monitor")
        assert "EDUCACION BASICA" in html

    def test_html_escapes_xss(self):
        """Datos con HTML malicioso se escapan correctamente."""
        xss_student = {**STUDENT_DATA, "nombre": "<script>alert('xss')</script>"}
        html = _build_report_html(xss_student, INTERVENTION_DATA, "Monitor")
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_missing_fields_use_dash(self):
        """Campos faltantes muestran '—' en lugar de error."""
        html = _build_report_html({}, {}, "Monitor")
        assert "—" in html  # em-dash default

    def test_observacion_hidden_when_dash(self):
        """Si observacion no esta presente (default '—'), no se muestra el bloque."""
        intervention = {**INTERVENTION_DATA}
        del intervention["observacion"]
        html = _build_report_html(STUDENT_DATA, intervention, "Monitor")
        # El bloque de observaciones no debería aparecer cuando es "—"
        assert "Observaciones adicionales" not in html


class TestSendBienestarReport:
    """Verificar envio de reporte de bienestar."""

    def test_returns_false_without_smtp(self):
        """Sin SMTP configurado retorna False."""
        with patch("backend.services.email.settings") as mock_settings:
            mock_settings.SMTP_HOST = ""
            mock_settings.BIENESTAR_EMAIL = ""
            result = send_bienestar_report(STUDENT_DATA, INTERVENTION_DATA, "Monitor")
        assert result is False

    def test_returns_false_without_bienestar_email(self):
        with patch("backend.services.email.settings") as mock_settings:
            mock_settings.SMTP_HOST = "smtp.test.com"
            mock_settings.BIENESTAR_EMAIL = ""
            result = send_bienestar_report(STUDENT_DATA, INTERVENTION_DATA, "Monitor")
        assert result is False

    def test_returns_true_on_successful_send(self):
        """Con SMTP mock funcional, retorna True."""
        with patch("backend.services.email.settings") as mock_settings:
            mock_settings.SMTP_HOST = "smtp.test.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USER = "user@test.com"
            mock_settings.SMTP_PASSWORD = "pass"
            mock_settings.SMTP_FROM = "noreply@test.com"
            mock_settings.BIENESTAR_EMAIL = "bienestar@ups.edu.ec"

            with patch("backend.services.email.smtplib.SMTP") as mock_smtp:
                mock_server = MagicMock()
                mock_smtp.return_value.__enter__ = lambda s: mock_server
                mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

                result = send_bienestar_report(STUDENT_DATA, INTERVENTION_DATA, "Monitor")

        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.sendmail.assert_called_once()

    def test_returns_false_on_smtp_error(self):
        """Error SMTP retorna False sin crashear."""
        with patch("backend.services.email.settings") as mock_settings:
            mock_settings.SMTP_HOST = "smtp.test.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USER = "user"
            mock_settings.SMTP_PASSWORD = "pass"
            mock_settings.SMTP_FROM = "noreply@test.com"
            mock_settings.BIENESTAR_EMAIL = "bienestar@ups.edu.ec"

            with patch("backend.services.email.smtplib.SMTP") as mock_smtp:
                mock_smtp.side_effect = Exception("Connection refused")
                result = send_bienestar_report(STUDENT_DATA, INTERVENTION_DATA, "Monitor")

        assert result is False


class TestSendTutoriaNotification:
    """Verificar envio de notificacion de tutoria."""

    def test_returns_false_without_smtp(self):
        with patch("backend.services.email.settings") as mock_settings:
            mock_settings.SMTP_HOST = ""
            mock_settings.SMTP_USER = ""
            result = send_tutoria_notification(
                STUDENT_DATA, "MATEMATICAS", "Prof. Perez", "Bajo rendimiento", "Monitor"
            )
        assert result is False

    def test_returns_false_without_student_email(self):
        with patch("backend.services.email.settings") as mock_settings:
            mock_settings.SMTP_HOST = "smtp.test.com"
            mock_settings.SMTP_USER = "user"
            result = send_tutoria_notification(
                {}, "MATEMATICAS", "Prof.", "Motivo", "Monitor"
            )
        assert result is False
