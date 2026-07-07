"""
Daily Digest — resumen diario por email para monitores y administradores.

[Épica 2.1] Notificaciones por Email

Genera un resumen HTML con:
- Conteo de alertas nuevas por severidad
- Top 5 estudiantes más críticos
- Alertas de deterioro progresivo detectadas
- Resumen de última ejecución del pipeline ETL

Se puede invocar desde un cron job o endpoint manual.
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
from html import escape as html_escape
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from ..config import settings
from .logsafe import mask_email
from ..models import Student, ScrapingRun
from ..models.alert_event import AlertEvent
from ..models.course_config import SemesterConfig
from ..models.user import User, UserRole

logger = logging.getLogger(__name__)


def build_digest_data(db: Session) -> dict:
    """
    Construye los datos para el digest diario.
    Retorna dict con toda la información necesaria para el template.
    """
    now = datetime.now(timezone.utc)
    ayer = now - timedelta(hours=24)

    # Semestre activo
    semconfig = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    semestre_nombre = semconfig.semestre if semconfig else "No configurado"
    bloque = semconfig.bloque_actual if semconfig else "—"

    # Alertas no leídas por severidad
    alertas_criticas = db.query(func.count(AlertEvent.id)).filter(
        AlertEvent.leido == False, AlertEvent.severidad == "alto"
    ).scalar() or 0
    alertas_altas = db.query(func.count(AlertEvent.id)).filter(
        AlertEvent.leido == False, AlertEvent.severidad == "alto"
    ).scalar() or 0
    alertas_medias = db.query(func.count(AlertEvent.id)).filter(
        AlertEvent.leido == False, AlertEvent.severidad == "medio"
    ).scalar() or 0
    total_alertas = alertas_criticas + alertas_altas + alertas_medias

    # Alertas por tipo
    alertas_por_tipo = {}
    for tipo, cnt in db.query(AlertEvent.tipo, func.count(AlertEvent.id)).filter(
        AlertEvent.leido == False
    ).group_by(AlertEvent.tipo).all():
        alertas_por_tipo[tipo] = cnt

    # Top 5 estudiantes más críticos (más alertas no leídas)
    top_students_q = (
        db.query(
            Student.id, Student.nombre, Student.carrera,
            func.count(AlertEvent.id).label("n_alertas"),
            Student.prob_desercion, Student.indice_compromiso,
        )
        .join(AlertEvent, AlertEvent.student_id == Student.id)
        .filter(AlertEvent.leido == False)
        .group_by(Student.id, Student.nombre, Student.carrera,
                  Student.prob_desercion, Student.indice_compromiso)
        .order_by(func.count(AlertEvent.id).desc())
        .limit(5)
        .all()
    )
    top_students = [
        {
            "nombre": s.nombre or "—",
            "carrera": s.carrera or "—",
            "n_alertas": s.n_alertas,
            "prob_desercion": s.prob_desercion,
            "compromiso": s.indice_compromiso,
        }
        for s in top_students_q
    ]

    # Alertas de deterioro progresivo
    n_deterioro = alertas_por_tipo.get("deterioro_progresivo", 0)

    # Última ejecución ETL
    last_run = db.query(ScrapingRun).order_by(ScrapingRun.id.desc()).first()
    etl_info = None
    if last_run:
        etl_info = {
            "status": last_run.status,
            "timestamp": last_run.finished_at.strftime("%d/%m/%Y %H:%M") if last_run.finished_at else "—",
            "registros": last_run.registros_insertados or 0,
            "triggered_by": last_run.triggered_by or "—",
        }

    # Total estudiantes monitoreados
    total_estudiantes = db.query(func.count(Student.id)).scalar() or 0
    estudiantes_riesgo_alto = db.query(func.count(Student.id)).filter(
        Student.nivel_riesgo == "Alto"
    ).scalar() or 0

    return {
        "fecha": now.strftime("%d/%m/%Y"),
        "hora": now.strftime("%H:%M UTC"),
        "semestre": semestre_nombre,
        "bloque": bloque,
        "total_alertas": total_alertas,
        "alertas_criticas": alertas_criticas,
        "alertas_altas": alertas_altas,
        "alertas_medias": alertas_medias,
        "alertas_por_tipo": alertas_por_tipo,
        "n_deterioro": n_deterioro,
        "top_students": top_students,
        "etl_info": etl_info,
        "total_estudiantes": total_estudiantes,
        "estudiantes_riesgo_alto": estudiantes_riesgo_alto,
    }


def build_digest_html(data: dict) -> str:
    """Genera el HTML del Daily Digest."""

    # Tabla de top estudiantes
    top_rows = ""
    for i, s in enumerate(data["top_students"], 1):
        bg = "#fff8f8" if i % 2 == 0 else "#ffffff"
        prob = f"{s['prob_desercion']:.0%}" if s.get("prob_desercion") is not None else "—"
        comp = f"{s['compromiso']:.2f}" if s.get("compromiso") is not None else "—"
        top_rows += f"""
        <tr style="background:{bg};">
            <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;">{html_escape(s['nombre'])}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;">{html_escape(s['carrera'])}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;text-align:center;font-weight:bold;color:#dc2626;">{s['n_alertas']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;text-align:center;">{prob}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;text-align:center;">{comp}</td>
        </tr>"""

    # Alertas por tipo
    tipo_labels = {
        "inactividad": "Inactividad",
        "compromiso_bajo": "Compromiso bajo",
        "nota_cero": "Nota cero",
        "tareas_bajas": "Tareas bajas",
        "segunda_matricula": "Segunda matrícula",
        "tercera_matricula": "Tercera matrícula",
        "deterioro_progresivo": "Deterioro progresivo",
    }
    tipo_rows = ""
    for tipo, cnt in sorted(data["alertas_por_tipo"].items(), key=lambda x: -x[1]):
        label = tipo_labels.get(tipo, tipo)
        color = "#dc2626" if tipo in ("inactividad", "tercera_matricula", "deterioro_progresivo") else "#d97706"
        tipo_rows += f'<span style="display:inline-block;margin:4px 6px;padding:4px 12px;background:#fef2f2;border:1px solid {color};border-radius:12px;font-size:13px;color:{color};"><strong>{cnt}</strong> {html_escape(label)}</span>'

    # ETL info
    etl_section = ""
    if data.get("etl_info"):
        etl = data["etl_info"]
        status_color = "#16a34a" if etl["status"] == "success" else "#dc2626"
        etl_section = f"""
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:14px;margin-top:16px;">
            <strong style="color:#475569;">Última ejecución ETL:</strong>
            <span style="color:{status_color};font-weight:bold;"> {html_escape(etl['status'].upper())}</span>
            <span style="color:#94a3b8;"> — {html_escape(etl['timestamp'])} — {etl['registros']} registros</span>
        </div>"""

    # Deterioro warning
    deterioro_section = ""
    if data["n_deterioro"] > 0:
        deterioro_section = f"""
        <div style="background:#fef3c7;border:1px solid #f59e0b;border-radius:8px;padding:14px;margin-top:16px;">
            <strong style="color:#92400e;">⚠ Deterioro Progresivo:</strong>
            <span style="color:#92400e;"> {data['n_deterioro']} estudiante(s) con patrón de abandono silencioso detectado. Requieren atención prioritaria.</span>
        </div>"""

    return f"""
    <html>
    <body style="font-family:Calibri,Arial,sans-serif;background:#f4f7fa;padding:20px;margin:0;">
        <div style="max-width:680px;margin:auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">

            <div style="background:linear-gradient(135deg,#0F2444,#1B3A6B);color:white;padding:24px;">
                <h1 style="margin:0;font-size:22px;">Yachay Deep — Resumen Diario</h1>
                <p style="margin:6px 0 0;opacity:0.7;font-size:14px;">{html_escape(data['fecha'])} | Semestre {html_escape(data['semestre'])} — Bloque {html_escape(data['bloque'])}</p>
            </div>

            <div style="padding:24px;">

                <!-- KPI Cards -->
                <div style="display:flex;gap:12px;margin-bottom:20px;">
                    <div style="flex:1;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:16px;text-align:center;">
                        <div style="font-size:28px;font-weight:bold;color:#dc2626;">{data['alertas_criticas']}</div>
                        <div style="font-size:12px;color:#991b1b;margin-top:4px;">CRÍTICAS</div>
                    </div>
                    <div style="flex:1;background:#fffbeb;border:1px solid #fed7aa;border-radius:8px;padding:16px;text-align:center;">
                        <div style="font-size:28px;font-weight:bold;color:#d97706;">{data['alertas_altas']}</div>
                        <div style="font-size:12px;color:#92400e;margin-top:4px;">ALTAS</div>
                    </div>
                    <div style="flex:1;background:#f0f9ff;border:1px solid #bae6fd;border-radius:8px;padding:16px;text-align:center;">
                        <div style="font-size:28px;font-weight:bold;color:#0284c7;">{data['alertas_medias']}</div>
                        <div style="font-size:12px;color:#075985;margin-top:4px;">MEDIAS</div>
                    </div>
                    <div style="flex:1;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px;text-align:center;">
                        <div style="font-size:28px;font-weight:bold;color:#16a34a;">{data['total_estudiantes']}</div>
                        <div style="font-size:12px;color:#166534;margin-top:4px;">MONITOREADOS</div>
                    </div>
                </div>

                <!-- Alertas por tipo -->
                <div style="margin-bottom:20px;">
                    <h2 style="font-size:15px;color:#1a365d;border-bottom:2px solid #2563eb;padding-bottom:6px;">Alertas por Tipo</h2>
                    <div style="margin-top:10px;">{tipo_rows if tipo_rows else '<span style="color:#94a3b8;">Sin alertas pendientes</span>'}</div>
                </div>

                {deterioro_section}

                <!-- Top estudiantes -->
                <h2 style="font-size:15px;color:#1a365d;border-bottom:2px solid #2563eb;padding-bottom:6px;margin-top:20px;">
                    Top 5 Estudiantes con Más Alertas
                </h2>
                <table style="width:100%;border-collapse:collapse;margin-top:10px;">
                    <thead>
                        <tr style="background:#f1f5f9;">
                            <th style="padding:8px 12px;text-align:left;font-size:13px;color:#475569;">Estudiante</th>
                            <th style="padding:8px 12px;text-align:left;font-size:13px;color:#475569;">Carrera</th>
                            <th style="padding:8px 12px;text-align:center;font-size:13px;color:#475569;">Alertas</th>
                            <th style="padding:8px 12px;text-align:center;font-size:13px;color:#475569;">P. Deserción</th>
                            <th style="padding:8px 12px;text-align:center;font-size:13px;color:#475569;">Compromiso</th>
                        </tr>
                    </thead>
                    <tbody>
                        {top_rows if top_rows else '<tr><td colspan="5" style="padding:16px;text-align:center;color:#94a3b8;">Sin datos</td></tr>'}
                    </tbody>
                </table>

                {etl_section}

                <!-- Footer -->
                <div style="border-top:1px solid #e5e7eb;padding-top:14px;margin-top:24px;font-size:12px;color:#9ca3af;">
                    <p style="margin:2px 0;">Estudiantes en riesgo alto: <strong>{data['estudiantes_riesgo_alto']}</strong> de {data['total_estudiantes']}</p>
                    <p style="margin:2px 0;">Generado: {html_escape(data['fecha'])} {html_escape(data['hora'])}</p>
                    <p style="margin:8px 0 0;font-style:italic;">Este resumen fue generado automáticamente por Yachay Deep.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


def send_daily_digest(db: Session, recipient_email: Optional[str] = None) -> dict:
    """
    Genera y envía el Daily Digest.

    Si recipient_email es None, envía a todos los usuarios admin/monitor.
    Retorna dict con: sent_to, failed, data_summary
    """
    if not settings.SMTP_HOST:
        return {"error": "SMTP no configurado", "sent_to": [], "failed": []}

    # Construir datos
    data = build_digest_data(db)

    # Si no hay alertas, no enviar (evitar spam)
    if data["total_alertas"] == 0:
        logger.info("Daily Digest: sin alertas pendientes, no se envía")
        return {"sent_to": [], "failed": [], "skipped": True,
                "reason": "Sin alertas pendientes"}

    # Generar HTML
    html = build_digest_html(data)

    # Determinar destinatarios
    if recipient_email:
        recipients = [recipient_email]
    else:
        users = db.query(User).filter(
            User.role.in_([UserRole.admin, UserRole.monitor])
        ).all()
        recipients = [u.email for u in users if u.email]

    if not recipients:
        return {"sent_to": [], "failed": [], "error": "Sin destinatarios"}

    sent_to = []
    failed = []

    for email_addr in recipients:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = (
                f"[Yachay Deep] Resumen Diario — "
                f"{data['total_alertas']} alertas ({data['alertas_criticas']} críticas) — "
                f"{data['fecha']}"
            )
            msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
            msg["To"] = email_addr
            msg.attach(MIMEText(html, "html", "utf-8"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
                server.starttls()
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(msg["From"], [email_addr], msg.as_string())

            sent_to.append(email_addr)
            logger.info(f"Daily Digest enviado a {mask_email(email_addr)}")

        except Exception as e:
            failed.append({"email": email_addr, "error": str(e)})
            logger.error(f"Error enviando Daily Digest a {mask_email(email_addr)}: {e}")

    return {
        "sent_to": sent_to,
        "failed": failed,
        "total_alertas": data["total_alertas"],
        "alertas_criticas": data["alertas_criticas"],
        "timestamp": data["fecha"],
    }
