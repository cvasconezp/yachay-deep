"""
Exportación a PDF y Excel.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from io import BytesIO
from datetime import datetime

from ..database import get_db
from ..models import Student, AvacAccess, TaskSubmission, Grade, Intervention
from ..auth.jwt import get_current_user
from ..models.user import User

router = APIRouter(prefix="/export", tags=["export"])


# ─── Columnas disponibles para exportación Excel ─────────────────────────────

EXPORT_COLUMNS = {
    "cedula": {"label": "Cédula", "getter": lambda s, _: s.cedula},
    "nombre": {"label": "Nombres completos", "getter": lambda s, _: s.nombre},
    "correo": {"label": "Correo personal", "getter": lambda s, _: s.correo},
    "correo_institucional": {"label": "Correo institucional", "getter": lambda s, _: s.correo_institucional},
    "telefono": {"label": "Teléfono", "getter": lambda s, _: s.telefono},
    "whatsapp": {"label": "WhatsApp", "getter": lambda s, _: s.whatsapp},
    "carrera": {"label": "Carrera", "getter": lambda s, _: s.carrera},
    "nivel_academico": {"label": "Nivel académico", "getter": lambda s, _: s.nivel_academico},
    "sede": {"label": "Centro de apoyo", "getter": lambda s, _: s.sede},
    "grupo": {"label": "Grupo", "getter": lambda s, _: s.grupo},
    "estado_matricula": {"label": "Estado matrícula", "getter": lambda s, _: s.estado_matricula},
    "nivel_riesgo": {"label": "Nivel de riesgo", "getter": lambda s, _: s.nivel_riesgo},
    "indice_compromiso": {"label": "Índice compromiso", "getter": lambda s, _: round(s.indice_compromiso, 2) if s.indice_compromiso is not None else None},
    "dias_sin_acceso": {"label": "Días sin acceso AVAC", "getter": lambda s, _: s.dias_sin_acceso},
    "porcentaje_tareas": {"label": "% Tareas entregadas", "getter": lambda s, _: round(s.porcentaje_tareas, 1) if s.porcentaje_tareas is not None else None},
    "promedio_calificaciones": {"label": "Promedio calificaciones", "getter": lambda s, _: round(s.promedio_calificaciones, 1) if s.promedio_calificaciones is not None else None},
    "prob_desercion": {"label": "Prob. deserción", "getter": lambda s, _: round(s.prob_desercion, 2) if s.prob_desercion is not None else None},
    "prob_reprobacion": {"label": "Prob. reprobación", "getter": lambda s, _: round(s.prob_reprobacion, 2) if s.prob_reprobacion is not None else None},
    "genero": {"label": "Género", "getter": lambda s, _: s.genero},
    "autoidentificacion_etnica": {"label": "Autoidentificación étnica", "getter": lambda s, _: s.autoidentificacion_etnica},
    "fecha_nacimiento": {"label": "Fecha nacimiento", "getter": lambda s, _: s.fecha_nacimiento.isoformat() if s.fecha_nacimiento else None},
    "pais": {"label": "País", "getter": lambda s, _: s.pais},
    "provincia": {"label": "Provincia", "getter": lambda s, _: s.provincia},
    "ciudad": {"label": "Ciudad", "getter": lambda s, _: s.ciudad},
    "parroquia": {"label": "Parroquia", "getter": lambda s, _: s.parroquia},
    "barrio": {"label": "Barrio/Comunidad", "getter": lambda s, _: s.barrio},
    "total_intervenciones": {"label": "Total intervenciones", "getter": lambda s, ctx: ctx.get("interv", {}).get(s.id, 0)},
}


@router.get("/columnas-disponibles")
def get_columnas_disponibles(
    current_user: User = Depends(get_current_user),
):
    """Lista de columnas disponibles para exportación con su clave y etiqueta."""
    return [{"key": k, "label": v["label"]} for k, v in EXPORT_COLUMNS.items()]


@router.get("/estudiantes/excel")
def export_estudiantes_excel(
    carrera: Optional[str] = None,
    nivel: Optional[int] = None,
    nivel_riesgo: Optional[str] = None,
    periodo: Optional[str] = None,
    columnas: str = Query("cedula,nombre,correo_institucional,carrera,nivel_academico,nivel_riesgo", description="Columnas separadas por coma"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exporta estudiantes a Excel con filtros y columnas seleccionables.
    periodo: 'actual' o None = semestre actual, 'P60'-'P67' = histórico, 'todos' = todos.
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl no instalado")

    from ..models import Grade as _Grade

    periodo_filter = periodo if periodo else "actual"

    # Si es período histórico, filtrar estudiantes por quienes tienen calificaciones en ese período
    student_ids_in_periodo = None
    if periodo_filter not in ("actual", "todos"):
        grade_sids = (
            db.query(_Grade.student_id)
            .filter(_Grade.periodo == periodo_filter)
            .distinct()
            .all()
        )
        student_ids_in_periodo = set(sid for (sid,) in grade_sids)
        if not student_ids_in_periodo:
            raise HTTPException(status_code=404, detail=f"No hay calificaciones para el período {periodo_filter}")

    # Filtrar estudiantes
    query = db.query(Student)
    if carrera:
        query = query.filter(func.lower(Student.carrera).contains(carrera.lower()))
    if nivel:
        query = query.filter(Student.nivel_academico == nivel)
    if nivel_riesgo:
        query = query.filter(Student.nivel_riesgo == nivel_riesgo)
    if student_ids_in_periodo is not None:
        query = query.filter(Student.id.in_(student_ids_in_periodo))
    query = query.order_by(Student.carrera, Student.nivel_academico, Student.nombre)
    students = query.all()

    if not students:
        raise HTTPException(status_code=404, detail="No se encontraron estudiantes con los filtros aplicados")

    # Parsear columnas solicitadas
    cols_requested = [c.strip() for c in columnas.split(",") if c.strip() in EXPORT_COLUMNS]
    if not cols_requested:
        cols_requested = ["cedula", "nombre", "correo_institucional", "carrera", "nivel_academico", "nivel_riesgo"]

    # Pre-cargar contexto (intervenciones por estudiante)
    ctx = {}
    if "total_intervenciones" in cols_requested:
        student_ids = [s.id for s in students]
        interv_counts = dict(
            db.query(Intervention.student_id, func.count(Intervention.id))
            .filter(Intervention.student_id.in_(student_ids))
            .group_by(Intervention.student_id)
            .all()
        )
        ctx["interv"] = interv_counts

    # Crear workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Estudiantes"

    # Estilos
    header_font = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="1B3A6B", end_color="1B3A6B", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell_font = Font(name="Calibri", size=10)
    thin_border = Border(
        left=Side(style="thin", color="D0D5DD"),
        right=Side(style="thin", color="D0D5DD"),
        top=Side(style="thin", color="D0D5DD"),
        bottom=Side(style="thin", color="D0D5DD"),
    )
    alt_fill = PatternFill(start_color="F5F7FA", end_color="F5F7FA", fill_type="solid")

    # Headers
    for col_idx, col_key in enumerate(cols_requested, 1):
        cell = ws.cell(row=1, column=col_idx, value=EXPORT_COLUMNS[col_key]["label"])
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border

    # Datos
    for row_idx, student in enumerate(students, 2):
        for col_idx, col_key in enumerate(cols_requested, 1):
            value = EXPORT_COLUMNS[col_key]["getter"](student, ctx)
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font = cell_font
            cell.border = thin_border
            if row_idx % 2 == 0:
                cell.fill = alt_fill

    # Autofit columns
    for col_idx, col_key in enumerate(cols_requested, 1):
        max_len = len(EXPORT_COLUMNS[col_key]["label"])
        for row_idx in range(2, min(len(students) + 2, 52)):  # Sample first 50 rows
            val = ws.cell(row=row_idx, column=col_idx).value
            if val:
                max_len = max(max_len, len(str(val)))
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = min(max_len + 3, 40)

    # Fila de resumen
    summary_row = len(students) + 3
    ws.cell(row=summary_row, column=1, value=f"Total: {len(students)} estudiantes").font = Font(bold=True, size=10)
    ws.cell(row=summary_row + 1, column=1, value=f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')} — {current_user.nombre}").font = Font(size=9, color="888888")

    # Filtro aplicado
    filter_desc = "Filtros: "
    if periodo_filter and periodo_filter != "actual":
        filter_desc += f"Período={periodo_filter} "
    else:
        filter_desc += "Período=Semestre actual "
    if carrera:
        filter_desc += f"Carrera={carrera} "
    if nivel:
        filter_desc += f"Nivel={nivel} "
    if nivel_riesgo:
        filter_desc += f"Riesgo={nivel_riesgo} "
    if not carrera and not nivel and not nivel_riesgo:
        filter_desc += "(sin filtros adicionales)"
    ws.cell(row=summary_row + 2, column=1, value=filter_desc).font = Font(size=9, color="888888")

    # Freeze header row
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    import re
    safe_carrera = re.sub(r'[^\w\s-]', '', carrera or "todos").replace(' ', '_')
    filename = f"estudiantes_{safe_carrera}_{datetime.now().strftime('%Y%m%d')}.xlsx"

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ─── Columnas disponibles para exportación de Intervenciones ──────────────────

INTERVENTION_COLUMNS = {
    "nombre": {"label": "Estudiante", "getter": lambda inv, ctx: ctx["students"].get(inv.student_id, {}).get("nombre")},
    "cedula": {"label": "Cédula", "getter": lambda inv, ctx: ctx["students"].get(inv.student_id, {}).get("cedula")},
    "correo_institucional": {"label": "Correo institucional", "getter": lambda inv, ctx: ctx["students"].get(inv.student_id, {}).get("correo_institucional")},
    "telefono": {"label": "Teléfono", "getter": lambda inv, ctx: ctx["students"].get(inv.student_id, {}).get("telefono")},
    "whatsapp": {"label": "WhatsApp", "getter": lambda inv, ctx: ctx["students"].get(inv.student_id, {}).get("whatsapp")},
    "carrera": {"label": "Carrera", "getter": lambda inv, ctx: ctx["students"].get(inv.student_id, {}).get("carrera") or inv.carrera},
    "sede": {"label": "Centro de apoyo", "getter": lambda inv, ctx: ctx["students"].get(inv.student_id, {}).get("sede")},
    "nivel_riesgo": {"label": "Nivel de riesgo", "getter": lambda inv, ctx: ctx["students"].get(inv.student_id, {}).get("nivel_riesgo")},
    "medio": {"label": "Medio de contacto", "getter": lambda inv, _: inv.medio},
    "motivo": {"label": "Motivo", "getter": lambda inv, _: inv.motivo},
    "estado": {"label": "Estado", "getter": lambda inv, _: inv.estado},
    "resultado": {"label": "Resultado", "getter": lambda inv, _: inv.resultado},
    "asignatura": {"label": "Asignatura", "getter": lambda inv, _: inv.asignatura},
    "docente": {"label": "Docente", "getter": lambda inv, _: inv.docente},
    "observacion": {"label": "Observación", "getter": lambda inv, _: inv.observacion},
    "requiere_seguimiento": {"label": "Requiere seguimiento", "getter": lambda inv, _: "Sí" if inv.requiere_seguimiento == "si" else ("No" if inv.requiere_seguimiento == "no" else "")},
    "derivar_bienestar": {"label": "Derivado a Bienestar", "getter": lambda inv, _: "Sí" if inv.derivar_bienestar else "No"},
    "tipo_evento_critico": {"label": "Tipo evento crítico", "getter": lambda inv, _: inv.tipo_evento_critico},
    "reporte_bienestar": {"label": "Reporte Bienestar", "getter": lambda inv, _: inv.reporte_bienestar},
    "email_enviado": {"label": "Email Bienestar enviado", "getter": lambda inv, _: "Sí" if inv.email_enviado else "No"},
    "monitor_nombre": {"label": "Monitor", "getter": lambda inv, _: inv.monitor_nombre},
    "fecha": {"label": "Fecha", "getter": lambda inv, _: inv.created_at.strftime("%d/%m/%Y %H:%M") if inv.created_at else None},
}


@router.get("/intervenciones/columnas-disponibles")
def get_columnas_intervenciones(
    current_user: User = Depends(get_current_user),
):
    """Lista de columnas disponibles para exportación de intervenciones."""
    return [{"key": k, "label": v["label"]} for k, v in INTERVENTION_COLUMNS.items()]


@router.get("/intervenciones/excel")
def export_intervenciones_excel(
    carrera: Optional[str] = None,
    motivo: Optional[str] = None,
    estado: Optional[str] = None,
    resultado: Optional[str] = None,
    seguimiento: Optional[str] = None,
    columnas: str = Query(
        "nombre,carrera,nivel_riesgo,medio,motivo,estado,resultado,requiere_seguimiento,observacion,monitor_nombre,fecha",
        description="Columnas separadas por coma",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exporta intervenciones a Excel con filtros y columnas seleccionables."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl no instalado")

    # Query con los mismos filtros que el dashboard
    query = db.query(Intervention).join(Student, Intervention.student_id == Student.id)
    if carrera:
        query = query.filter(Student.carrera == carrera)
    if motivo:
        query = query.filter(Intervention.motivo == motivo)
    if estado:
        query = query.filter(Intervention.estado == estado)
    if resultado:
        query = query.filter(Intervention.resultado == resultado)
    if seguimiento:
        query = query.filter(Intervention.requiere_seguimiento == seguimiento)

    interventions = query.order_by(Intervention.created_at.desc()).all()

    if not interventions:
        raise HTTPException(status_code=404, detail="No se encontraron intervenciones con los filtros aplicados")

    # Parsear columnas
    cols_requested = [c.strip() for c in columnas.split(",") if c.strip() in INTERVENTION_COLUMNS]
    if not cols_requested:
        cols_requested = ["nombre", "carrera", "motivo", "estado", "resultado", "monitor_nombre", "fecha"]

    # Pre-cargar datos de estudiantes
    student_ids = list(set(inv.student_id for inv in interventions))
    students_data = db.query(Student).filter(Student.id.in_(student_ids)).all()
    ctx = {
        "students": {
            s.id: {
                "nombre": s.nombre,
                "cedula": s.cedula,
                "correo_institucional": s.correo_institucional,
                "telefono": s.telefono,
                "whatsapp": s.whatsapp,
                "carrera": s.carrera,
                "sede": s.sede,
                "nivel_riesgo": s.nivel_riesgo,
            }
            for s in students_data
        }
    }

    # Crear workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Intervenciones"

    # Estilos
    header_font = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="1B3A6B", end_color="1B3A6B", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell_font = Font(name="Calibri", size=10)
    thin_border = Border(
        left=Side(style="thin", color="D0D5DD"),
        right=Side(style="thin", color="D0D5DD"),
        top=Side(style="thin", color="D0D5DD"),
        bottom=Side(style="thin", color="D0D5DD"),
    )
    alt_fill = PatternFill(start_color="F5F7FA", end_color="F5F7FA", fill_type="solid")

    # Headers
    for col_idx, col_key in enumerate(cols_requested, 1):
        cell = ws.cell(row=1, column=col_idx, value=INTERVENTION_COLUMNS[col_key]["label"])
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border

    # Datos
    for row_idx, inv in enumerate(interventions, 2):
        for col_idx, col_key in enumerate(cols_requested, 1):
            value = INTERVENTION_COLUMNS[col_key]["getter"](inv, ctx)
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font = cell_font
            cell.border = thin_border
            if row_idx % 2 == 0:
                cell.fill = alt_fill

    # Autofit columns
    for col_idx, col_key in enumerate(cols_requested, 1):
        max_len = len(INTERVENTION_COLUMNS[col_key]["label"])
        for row_idx in range(2, min(len(interventions) + 2, 52)):
            val = ws.cell(row=row_idx, column=col_idx).value
            if val:
                max_len = max(max_len, len(str(val)))
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = min(max_len + 3, 50)

    # Resumen
    summary_row = len(interventions) + 3
    ws.cell(row=summary_row, column=1, value=f"Total: {len(interventions)} intervenciones").font = Font(bold=True, size=10)
    ws.cell(row=summary_row + 1, column=1, value=f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')} — {current_user.nombre}").font = Font(size=9, color="888888")

    filter_parts = ["Filtros:"]
    if carrera:
        filter_parts.append(f"Carrera={carrera}")
    if motivo:
        filter_parts.append(f"Motivo={motivo}")
    if estado:
        filter_parts.append(f"Estado={estado}")
    if resultado:
        filter_parts.append(f"Resultado={resultado}")
    if seguimiento:
        filter_parts.append(f"Seguimiento={seguimiento}")
    if len(filter_parts) == 1:
        filter_parts.append("(sin filtros)")
    ws.cell(row=summary_row + 2, column=1, value=" ".join(filter_parts)).font = Font(size=9, color="888888")

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    import re
    safe_carrera = re.sub(r'[^\w\s-]', '', carrera or "todas").replace(' ', '_')
    filename = f"intervenciones_{safe_carrera}_{datetime.now().strftime('%Y%m%d')}.xlsx"

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


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
