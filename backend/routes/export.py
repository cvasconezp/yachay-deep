"""
Exportación a PDF — equivalente a ExportarFichaAPDF() del VBA.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO
from datetime import datetime

from ..database import get_db
from ..models import Student, AvacAccess, TaskSubmission, Grade, Intervention
from ..auth.jwt import get_current_user
from ..models.user import User

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/ficha/{student_id}/pdf")
def export_ficha_pdf(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Genera PDF de la ficha del estudiante.
    Equivalente a ExportarFichaAPDF() del VBA pero server-side.
    """
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Table, TableStyle,
            Spacer, HRFlowable
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
    except ImportError:
        raise HTTPException(status_code=500, detail="reportlab no instalado. Ejecuta: pip install reportlab")

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")

    tareas = db.query(TaskSubmission).filter(TaskSubmission.student_id == student_id).all()
    accesos = db.query(AvacAccess).filter(AvacAccess.student_id == student_id).all()
    calificaciones = db.query(Grade).filter(Grade.student_id == student_id).all()
    intervenciones = db.query(Intervention).filter(Intervention.student_id == student_id).order_by(Intervention.created_at.desc()).limit(10).all()

    # Colores por nivel de riesgo
    RISK_COLORS = {"Alto": colors.HexColor("#FF4C4C"), "Medio": colors.HexColor("#FFC000"), "Bajo": colors.HexColor("#00B050")}
    risk_color = RISK_COLORS.get(student.nivel_riesgo or "Medio", colors.grey)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    story = []

    # Header
    title_style = ParagraphStyle("title", fontSize=16, fontName="Helvetica-Bold", alignment=TA_CENTER, textColor=colors.HexColor("#1B3A6B"))
    story.append(Paragraph("YACHAY DEEP — Ficha de Seguimiento Académico", title_style))
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1B3A6B")))
    story.append(Spacer(1, 0.3*cm))

    # Datos del estudiante
    data_estudiante = [
        ["Estudiante:", student.nombre or "-", "Carrera:", student.carrera or "-"],
        ["Correo:", student.correo_institucional or "-", "Cédula:", student.cedula or "-"],
        ["Nivel de Riesgo:", student.nivel_riesgo or "-", "Índice Compromiso:", f"{(student.indice_compromiso or 0)*100:.0f}%"],
        ["Días sin acceso AVAC:", str(student.dias_sin_acceso or "-"), "% Tareas entregadas:", f"{student.porcentaje_tareas or 0:.0f}%"],
    ]
    t_datos = Table(data_estudiante, colWidths=[4*cm, 8*cm, 4*cm, 8*cm])
    t_datos.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F5F7FA")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D5DD")),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#F5F7FA"), colors.white]),
    ]))
    story.append(t_datos)
    story.append(Spacer(1, 0.4*cm))

    # Tabla de tareas por curso
    if tareas:
        story.append(Paragraph("Actividades por Curso", styles["Heading3"]))
        headers_tareas = ["Curso", "Unidad", "Estado", "Calificación", "Entregada", "Retrasada"]
        rows_tareas = [headers_tareas]
        for t in tareas[:30]:  # máximo 30 filas
            estado_corto = (t.estado or "-")[:40]
            rows_tareas.append([
                t.codigo_curso, t.unidad, estado_corto,
                f"{t.calificacion or '-'}", "✓" if t.entregada else "✗", "⚠" if t.retrasada else "-"
            ])
        t_tareas = Table(rows_tareas, colWidths=[3*cm, 2*cm, 9*cm, 3*cm, 2.5*cm, 2.5*cm])
        t_tareas.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B3A6B")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D5DD")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
        ]))
        story.append(t_tareas)
        story.append(Spacer(1, 0.4*cm))

    # Historial de intervenciones
    if intervenciones:
        story.append(Paragraph("Historial de Intervenciones", styles["Heading3"]))
        headers_interv = ["Fecha", "Monitor", "Medio", "Motivo", "Estado", "Observación"]
        rows_interv = [headers_interv]
        for i in intervenciones:
            rows_interv.append([
                i.created_at.strftime("%d/%m/%Y %H:%M") if i.created_at else "-",
                (i.monitor_nombre or "-")[:20],
                i.medio or "-",
                i.motivo or "-",
                i.estado or "-",
                (i.observacion or "-")[:40],
            ])
        t_interv = Table(rows_interv, colWidths=[3.5*cm, 4*cm, 3*cm, 4.5*cm, 3*cm, 6*cm])
        t_interv.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B3A6B")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D5DD")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
        ]))
        story.append(t_interv)

    # Footer
    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#D0D5DD")))
    footer_style = ParagraphStyle("footer", fontSize=7, textColor=colors.grey, alignment=TA_CENTER)
    story.append(Paragraph(f"Generado por Yachay Deep — {datetime.now().strftime('%d/%m/%Y %H:%M')} — Monitor: {current_user.nombre}", footer_style))

    doc.build(story)
    buffer.seek(0)

    import re
    safe_name = re.sub(r'[^\w\s-]', '', student.nombre or "estudiante").replace(' ', '_')
    filename = f"ficha_{safe_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
