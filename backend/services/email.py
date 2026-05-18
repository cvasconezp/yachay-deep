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


def send_tutoria_notification(
    student_data: dict,
    asignatura: str,
    docente: str,
    motivo: str,
    monitor_nombre: str,
) -> bool:
    """
    Envía notificación de tutoría al correo institucional del estudiante.
    Informa que debe asistir a tutoría sincrónica con el docente.
    """
    from ..config import settings

    if not settings.SMTP_HOST or not settings.SMTP_USER:
        logger.warning("SMTP no configurado — notificación de tutoría no enviada")
        return False

    correo_estudiante = student_data.get("correo_institucional") or student_data.get("correo")
    if not correo_estudiante:
        logger.warning("Estudiante sin correo — notificación no enviada")
        return False

    nombre = html_escape(student_data.get("nombre", "Estudiante"))
    asig = html_escape(asignatura)
    doc = html_escape(docente)
    mot = html_escape(motivo)
    monitor = html_escape(monitor_nombre)
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")

    html_body = f"""
    <html>
    <body style="font-family: Calibri, Arial, sans-serif; background: #f4f7fa; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
            <div style="background: linear-gradient(135deg, #0F2444, #1B3A6B); color: white; padding: 20px 24px;">
                <h2 style="margin: 0; font-size: 18px;">Convocatoria a Tutoría Académica</h2>
                <p style="margin: 4px 0 0; opacity: 0.7; font-size: 13px;">Yachay Deep — Monitoreo Académico</p>
            </div>
            <div style="padding: 24px;">
                <p style="font-size: 14px; color: #333;">Estimado/a <strong>{nombre}</strong>,</p>
                <p style="font-size: 14px; color: #555; line-height: 1.6;">
                    Se le convoca a una <strong>tutoría sincrónica</strong> en la asignatura
                    <strong style="color: #1B3A6B;">{asig}</strong> con el/la docente
                    <strong style="color: #1B3A6B;">{doc}</strong>.
                </p>
                <div style="background: #FFF8E1; border-left: 4px solid #E8A838; padding: 12px 16px; margin: 16px 0; border-radius: 4px;">
                    <p style="margin: 0; font-size: 13px; color: #7B6124;"><strong>Motivo:</strong> {mot}</p>
                </div>
                <p style="font-size: 14px; color: #555;">
                    Por favor coordine con su docente el horario de la tutoría.
                    Su participación es importante para mejorar su desempeño académico.
                </p>
                <div style="border-top: 1px solid #e5e7eb; padding-top: 14px; margin-top: 20px; font-size: 12px; color: #9ca3af;">
                    <p style="margin: 2px 0;">Convocado por: <strong>{monitor}</strong></p>
                    <p style="margin: 2px 0;">Fecha: {fecha}</p>
                    <p style="margin: 8px 0 0; font-style: italic;">Este correo fue generado por el sistema Yachay Deep.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Convocatoria a Tutoría — {asignatura}"
        msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
        msg["To"] = correo_estudiante
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(msg["From"], [correo_estudiante], msg.as_string())

        logger.info(f"Notificación de tutoría enviada a {correo_estudiante} ({asignatura})")
        return True
    except Exception as e:
        logger.error(f"Error enviando notificación de tutoría: {e}")
        return False


# ── Mapa de tabs a nombres legibles ──
TAB_LABELS = {
    "dashboard": ("Estudiantes", "Panel principal con lista de estudiantes y niveles de riesgo"),
    "alertas": ("Alertas", "Alertas académicas agrupadas por estudiante con acciones sugeridas"),
    "intervenciones": ("Intervenciones", "Gestión de intervenciones con seguimiento de estados"),
    "ficha": ("Ficha Estudiante", "Búsqueda y ficha detallada de cada estudiante"),
    "asignaturas": ("Asignaturas", "Vista de asignaturas con métricas de rendimiento"),
    "entregas": ("Entregas", "Monitoreo de entregas y tareas por asignatura"),
    "docentes": ("Docentes", "Métricas de efectividad docente"),
    "tutorias": ("Tutorías", "Gestión de tutorías académicas"),
    "resumen": ("Análisis Institucional", "Dashboard ejecutivo con KPIs y tendencias"),
    "about": ("Sobre Yachay Deep", "Información sobre la plataforma"),
    "admin": ("Administración", "Gestión de usuarios, ETL y configuración del sistema"),
}

# Guías por rol
GUIAS_POR_ROL = {
    "admin": [
        "Comienza revisando la pestaña <strong>Estudiantes</strong> para ver el panorama general de riesgo.",
        "Revisa las <strong>Alertas</strong> diariamente para identificar estudiantes que necesitan atención.",
        "Usa <strong>Intervenciones</strong> para registrar las acciones tomadas con cada estudiante.",
        "En <strong>Administración</strong> puedes gestionar usuarios, ejecutar ETL y configurar el sistema.",
        "El <strong>Análisis Institucional</strong> te da una vista macro de KPIs y tendencias.",
    ],
    "coordinador": [
        "Revisa el <strong>Análisis Institucional</strong> para monitorear KPIs y tendencias por carrera.",
        "Usa <strong>Estudiantes</strong> y <strong>Alertas</strong> para supervisar el estado de riesgo.",
        "Consulta <strong>Docentes</strong> y <strong>Asignaturas</strong> para identificar áreas problemáticas.",
        "Revisa las <strong>Intervenciones</strong> para dar seguimiento al trabajo de los monitores.",
        "Usa <strong>Tutorías</strong> para coordinar el apoyo académico de tu carrera.",
    ],
    "docente": [
        "Consulta <strong>Asignaturas</strong> para ver el rendimiento en tus materias.",
        "Revisa <strong>Entregas</strong> para identificar estudiantes con tareas pendientes.",
        "Usa la <strong>Ficha Estudiante</strong> para entender el contexto de cada alumno.",
        "Consulta <strong>Docentes</strong> para ver tu panel de efectividad.",
    ],
    "monitor": [
        "Tu trabajo principal está en <strong>Alertas</strong>: revísalas cada día para actuar a tiempo.",
        "Usa la <strong>Ficha Estudiante</strong> para investigar el historial completo de un estudiante.",
        "Registra cada contacto o acción en <strong>Intervenciones</strong> para mantener el seguimiento.",
        "Consulta <strong>Entregas</strong> y <strong>Asignaturas</strong> para entender el contexto académico.",
        "Si un caso es grave, deriva a Bienestar Estudiantil desde la intervención.",
    ],
}


def send_welcome_email(
    to_email: str,
    nombre: str,
    role: str,
    password: str,
    permissions: list[str] | None = None,
) -> bool:
    """
    Envía correo de bienvenida a un nuevo usuario con sus credenciales,
    pestañas asignadas y guía de primeros pasos.
    """
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        logger.warning("SMTP no configurado — email de bienvenida no enviado")
        return False

    app_url = getattr(settings, "FRONTEND_URL", None) or "https://yachay-deep.vercel.app"
    nombre_safe = html_escape(nombre)
    role_safe = html_escape(role)
    email_safe = html_escape(to_email)
    pass_safe = html_escape(password)

    # Construir lista de pestañas asignadas
    if permissions:
        tabs_html = ""
        for tab_key in permissions:
            label, desc = TAB_LABELS.get(tab_key, (tab_key.capitalize(), ""))
            tabs_html += f"""
            <tr>
                <td style="padding: 8px 12px; font-weight: 600; color: #1B3A6B; border-bottom: 1px solid #f0f0f0;">{html_escape(label)}</td>
                <td style="padding: 8px 12px; color: #6b7280; font-size: 13px; border-bottom: 1px solid #f0f0f0;">{html_escape(desc)}</td>
            </tr>"""
    else:
        tabs_html = """
            <tr>
                <td style="padding: 8px 12px; color: #6b7280;" colspan="2">Acceso completo a todas las pestañas</td>
            </tr>"""

    # Guía de primeros pasos
    guia_items = GUIAS_POR_ROL.get(role, GUIAS_POR_ROL["monitor"])
    guia_html = ""
    for i, paso in enumerate(guia_items, 1):
        guia_html += f"""
        <div style="display: flex; align-items: flex-start; margin-bottom: 10px;">
            <div style="min-width: 28px; height: 28px; background: #2563eb; color: white; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-weight: bold; font-size: 13px; margin-right: 12px;">{i}</div>
            <p style="margin: 0; padding-top: 4px; font-size: 14px; color: #374151; line-height: 1.5;">{paso}</p>
        </div>"""

    html_body = f"""
    <html>
    <body style="font-family: Calibri, Arial, sans-serif; background: #f4f7fa; padding: 20px; margin: 0;">
        <div style="max-width: 620px; margin: auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.08);">

            <!-- Header -->
            <div style="background: linear-gradient(135deg, #0F2444, #1B3A6B); color: white; padding: 28px 24px; text-align: center;">
                <h1 style="margin: 0; font-size: 22px; font-weight: 700;">Bienvenido/a a Yachay Deep</h1>
                <p style="margin: 6px 0 0; opacity: 0.8; font-size: 14px;">Sistema de Monitoreo Académico y Alerta Temprana</p>
            </div>

            <div style="padding: 28px 24px;">

                <!-- Saludo -->
                <p style="font-size: 15px; color: #333; margin-bottom: 4px;">Hola <strong>{nombre_safe}</strong>,</p>
                <p style="font-size: 14px; color: #555; line-height: 1.6;">
                    Se ha creado tu cuenta en <strong>Yachay Deep</strong>, la plataforma de monitoreo académico
                    que permite identificar estudiantes en riesgo y coordinar intervenciones oportunas.
                </p>

                <!-- Credenciales -->
                <div style="background: #f0f7ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 18px; margin: 20px 0;">
                    <h3 style="margin: 0 0 12px; font-size: 14px; color: #1e40af;">Tus credenciales de acceso</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 4px 0; font-weight: 600; color: #374151; width: 120px;">URL:</td>
                            <td style="padding: 4px 0;"><a href="{app_url}" style="color: #2563eb; text-decoration: none;">{app_url}</a></td>
                        </tr>
                        <tr>
                            <td style="padding: 4px 0; font-weight: 600; color: #374151;">Email:</td>
                            <td style="padding: 4px 0;">{email_safe}</td>
                        </tr>
                        <tr>
                            <td style="padding: 4px 0; font-weight: 600; color: #374151;">Contraseña:</td>
                            <td style="padding: 4px 0; font-family: monospace; background: #e0e7ff; padding: 3px 8px; border-radius: 4px; display: inline-block;">{pass_safe}</td>
                        </tr>
                        <tr>
                            <td style="padding: 4px 0; font-weight: 600; color: #374151;">Rol:</td>
                            <td style="padding: 4px 0;"><span style="background: #dbeafe; color: #1e40af; padding: 2px 10px; border-radius: 12px; font-size: 13px; font-weight: 600; text-transform: capitalize;">{role_safe}</span></td>
                        </tr>
                    </table>
                </div>

                <!-- Pestañas asignadas -->
                <h3 style="font-size: 15px; color: #1B3A6B; margin: 24px 0 10px; border-bottom: 2px solid #2563eb; padding-bottom: 6px;">
                    Módulos disponibles para ti
                </h3>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                    {tabs_html}
                </table>

                <!-- Guía de primeros pasos -->
                <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; margin: 20px 0;">
                    <h3 style="margin: 0 0 14px; font-size: 15px; color: #1B3A6B;">Primeros pasos</h3>
                    {guia_html}
                </div>

                <!-- CTA -->
                <div style="text-align: center; margin: 28px 0 12px;">
                    <a href="{app_url}/login" style="display: inline-block; background: linear-gradient(135deg, #1B3A6B, #2563eb); color: white; text-decoration: none; padding: 12px 36px; border-radius: 8px; font-weight: 600; font-size: 15px;">
                        Ingresar a Yachay Deep
                    </a>
                </div>

                <p style="font-size: 12px; color: #9ca3af; text-align: center; margin-top: 20px;">
                    Te recomendamos cambiar tu contraseña después del primer inicio de sesión.<br>
                    Si tienes dudas, contacta al administrador del sistema.
                </p>
            </div>

            <!-- Footer -->
            <div style="background: #f9fafb; padding: 16px 24px; border-top: 1px solid #e5e7eb; text-align: center;">
                <p style="margin: 0; font-size: 12px; color: #9ca3af;">
                    Yachay Deep — Sistema de Monitoreo Académico<br>
                    Este correo fue generado automáticamente. Por favor no responder.
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Bienvenido/a a Yachay Deep — Tus credenciales de acceso"
        msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(msg["From"], [to_email], msg.as_string())

        logger.info(f"Email de bienvenida enviado a {to_email}")
        return True
    except Exception as e:
        logger.error(f"Error enviando email de bienvenida: {e}")
        return False
