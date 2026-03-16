"""
Servicio de envío de correos — Derivación a Bienestar Estudiantil.
Genera y envía un reporte con datos del estudiante y la situación crítica.
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from html import escape as html_escape

from ..config import settings

logger = logging.getLogger(__name__)


def send_bienestar_report(
    student: dict,
    intervention: dict,
    monitor_nombre: str,
) -> bool:
    """
    Envía un correo al departamento de Bienestar Estudiantil con el reporte
    de derivación. Retorna True si se envió exitosamente.

    student: dict con nombre, cedula, correo, telefono, whatsapp, carrera, sede
    intervention: dict con tipo_evento_critico, reporte_bienestar, motivo, observacion
    """
    if not settings.SMTP_HOST or not settings.BIENESTAR_EMAIL:
        logger.warning(
            "SMTP no configurado o BIENESTAR_EMAIL no definido. "
            "El reporte de derivación no se envió por correo. "
            "Configure SMTP_HOST, SMTP_USER, SMTP_PASSWORD y BIENESTAR_EMAIL."
        )
        return False

    subject = (
        f"[YACHAY DEEP] Derivación Bienestar — "
        f"{student.get('nombre', 'Estudiante')} — "
        f"{intervention.get('tipo_evento_critico', 'Evento crítico')}"
    )

    html = _build_report_html(student, intervention, monitor_nombre)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = settings.BIENESTAR_EMAIL
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(msg["From"], [settings.BIENESTAR_EMAIL], msg.as_string())
        logger.info(f"Reporte de bienestar enviado a {settings.BIENESTAR_EMAIL}")
        return True
    except Exception as e:
        logger.error(f"Error al enviar correo de bienestar: {e}")
        return False


def _build_report_html(student: dict, intervention: dict, monitor: str) -> str:
    """Genera el HTML del reporte de derivación."""
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")

    nombre = html_escape(str(student.get("nombre", "—")))
    cedula = html_escape(str(student.get("cedula", "—")))
    correo = html_escape(str(student.get("correo", student.get("correo_institucional", "—"))))
    correo_inst = html_escape(str(student.get("correo_institucional", "—")))
    telefono = html_escape(str(student.get("telefono", "—")))
    whatsapp = html_escape(str(student.get("whatsapp", "—")))
    carrera = html_escape(str(student.get("carrera", "—")))
    sede = html_escape(str(student.get("sede", "—")))

    tipo_evento = html_escape(str(intervention.get("tipo_evento_critico", "—")))
    reporte = html_escape(str(intervention.get("reporte_bienestar", "—")))
    motivo = html_escape(str(intervention.get("motivo", "—")))
    observacion = html_escape(str(intervention.get("observacion", "—")))
    monitor = html_escape(str(monitor))

    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 650px; margin: 0 auto; color: #333;">
        <div style="background: linear-gradient(135deg, #1a365d, #2563eb); padding: 24px; border-radius: 12px 12px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 20px;">Yachay Deep — Reporte de Derivación</h1>
            <p style="color: #93c5fd; margin: 6px 0 0; font-size: 13px;">Departamento de Bienestar Estudiantil</p>
        </div>

        <div style="border: 1px solid #e5e7eb; border-top: none; padding: 24px; border-radius: 0 0 12px 12px;">

            <div style="background: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 14px; margin-bottom: 20px;">
                <strong style="color: #92400e;">Tipo de evento:</strong>
                <span style="color: #92400e; font-size: 15px;"> {tipo_evento}</span>
            </div>

            <h2 style="font-size: 15px; color: #1a365d; border-bottom: 2px solid #2563eb; padding-bottom: 6px;">
                Datos del Estudiante
            </h2>
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <tr><td style="padding: 6px 12px; font-weight: bold; color: #6b7280; width: 140px;">Nombre</td><td style="padding: 6px 12px;">{nombre}</td></tr>
                <tr style="background: #f9fafb;"><td style="padding: 6px 12px; font-weight: bold; color: #6b7280;">Cédula</td><td style="padding: 6px 12px;">{cedula}</td></tr>
                <tr><td style="padding: 6px 12px; font-weight: bold; color: #6b7280;">Carrera</td><td style="padding: 6px 12px;">{carrera}</td></tr>
                <tr style="background: #f9fafb;"><td style="padding: 6px 12px; font-weight: bold; color: #6b7280;">Sede</td><td style="padding: 6px 12px;">{sede}</td></tr>
                <tr><td style="padding: 6px 12px; font-weight: bold; color: #6b7280;">Correo personal</td><td style="padding: 6px 12px;">{correo}</td></tr>
                <tr style="background: #f9fafb;"><td style="padding: 6px 12px; font-weight: bold; color: #6b7280;">Correo institucional</td><td style="padding: 6px 12px;">{correo_inst}</td></tr>
                <tr><td style="padding: 6px 12px; font-weight: bold; color: #6b7280;">Teléfono</td><td style="padding: 6px 12px;">{telefono}</td></tr>
                <tr style="background: #f9fafb;"><td style="padding: 6px 12px; font-weight: bold; color: #6b7280;">WhatsApp</td><td style="padding: 6px 12px;">{whatsapp}</td></tr>
            </table>

            <h2 style="font-size: 15px; color: #1a365d; border-bottom: 2px solid #2563eb; padding-bottom: 6px;">
                Reporte del Incidente
            </h2>
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <tr><td style="padding: 6px 12px; font-weight: bold; color: #6b7280; width: 140px;">Motivo</td><td style="padding: 6px 12px;">{motivo}</td></tr>
                <tr style="background: #f9fafb;"><td style="padding: 6px 12px; font-weight: bold; color: #6b7280;">Tipo de evento</td><td style="padding: 6px 12px;">{tipo_evento}</td></tr>
            </table>

            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 20px;">
                <strong style="color: #475569; display: block; margin-bottom: 8px;">Descripción detallada:</strong>
                <p style="color: #334155; line-height: 1.6; margin: 0; white-space: pre-wrap;">{reporte}</p>
            </div>

            {f'''<div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 20px;">
                <strong style="color: #475569; display: block; margin-bottom: 8px;">Observaciones adicionales:</strong>
                <p style="color: #334155; line-height: 1.6; margin: 0;">{observacion}</p>
            </div>''' if observacion and observacion != "—" else ""}

            <div style="border-top: 1px solid #e5e7eb; padding-top: 14px; margin-top: 20px; font-size: 12px; color: #9ca3af;">
                <p style="margin: 2px 0;">Reportado por: <strong>{monitor}</strong></p>
                <p style="margin: 2px 0;">Fecha: {fecha}</p>
                <p style="margin: 2px 0;">Sistema: Yachay Deep — Monitoreo Académico</p>
                <p style="margin: 8px 0 0; font-style: italic;">Este correo fue generado automáticamente. Por favor contactar al estudiante a la brevedad posible.</p>
            </div>
        </div>
    </body>
    </html>
    """
