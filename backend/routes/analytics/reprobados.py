"""
Módulo: Analítica de Reprobados.

Informe por período · carrera · nivel de los estudiantes que REPROBARON al menos
una asignatura (Grade.nota_final < umbral de aprobación), con los indicadores que
dan "luces" sobre el porqué y el posible abandono:

- Académicos: nº de asignaturas reprobadas y cuáles (con su nota), promedio del
  período, repitencia / 3ra matrícula.
- Conductuales (desconexión): índice de compromiso, días desde el último acceso a
  AVAC, % de tareas entregadas.
- Administrativos: estado de matrícula.
- Seguimiento: nº de intervenciones registradas, última fecha y si quedó sin
  respuesta / con seguimiento pendiente.
- Predictivos: prob. de reprobación, prob. de deserción y score de recuperabilidad.
- `causa_probable`: una etiqueta heurística (Administrativa / Desconexión /
  Académica) para priorizar la lectura; los indicadores crudos permiten matizarla.

Sigue las convenciones del módulo Grupos: carrera vía Student, filtros de período
dual-format, umbrales configurables. Solo rol admin (require_admin).
"""
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ...database import get_db
from ...models import Student, Grade, Enrollment, Intervention
from ...auth.jwt import require_admin
from ...models.user import User
from ._helpers import apply_periodo_filter, get_umbrales, normalize_riesgo

router = APIRouter(prefix="/analytics", tags=["analytics"])


class AsignaturaReprobada(BaseModel):
    asignatura: str
    nota: Optional[float] = None


class ReprobadoEstudiante(BaseModel):
    student_id: int
    nombre: Optional[str] = None
    carrera: Optional[str] = None
    nivel: Optional[int] = None
    grupo: Optional[str] = None
    # Académico
    num_reprobadas: int = 0
    reprobadas: list[AsignaturaReprobada] = []
    promedio: Optional[float] = None
    es_tercera_matricula: bool = False
    es_repitente: bool = False
    # Conductual / riesgo
    nivel_riesgo: Optional[str] = None
    indice_compromiso: Optional[float] = None
    dias_sin_acceso: Optional[int] = None       # último acceso real (MÍN entre aulas)
    porcentaje_tareas: Optional[float] = None
    estado_matricula: Optional[str] = None
    # Predictivo
    prob_reprobacion: Optional[float] = None
    prob_desercion: Optional[float] = None
    score_recuperabilidad: Optional[float] = None
    # Seguimiento
    num_intervenciones: int = 0
    ultima_intervencion: Optional[str] = None
    intervencion_sin_respuesta: bool = False
    sin_intervencion: bool = True
    # Síntesis
    causa_probable: Optional[str] = None


class ReprobadosKPIs(BaseModel):
    total_reprobados: int = 0
    total_asignaturas_reprobadas: int = 0
    promedio_reprobados: Optional[float] = None
    riesgo_alto: int = 0
    sin_intervencion: int = 0
    por_causa: dict[str, int] = {}


class ReprobadosAnalytics(BaseModel):
    periodo: Optional[str] = None
    carrera: Optional[str] = None
    nivel: Optional[int] = None
    nota_aprobacion: float = 70.0
    estudiantes: list[ReprobadoEstudiante] = []
    kpis: ReprobadosKPIs = ReprobadosKPIs()

    class Config:
        from_attributes = True


# Resultados de intervención que indican que el estudiante NO respondió / sigue abierto.
_SIN_RESPUESTA = {
    "no contesto", "no contestó", "no contactado", "sin respuesta", "sna",
    "no respondio", "no respondió", "pendiente", "sin contactar",
}


def _clasificar_causa(est: dict, umbrales: dict) -> str:
    """Etiqueta heurística de la causa probable (para priorizar la lectura).

    Prioridad: Administrativa (compuerta) → Desconexión → Académica. Si no hay
    señales conductuales ni administrativas, se asume académica (bajó notas pese a
    mantenerse conectado). 'Sin datos' cuando faltan los indicadores base.
    """
    estado = (est.get("estado_matricula") or "").strip().lower()
    admin_irregular = bool(estado) and "matriculad" not in estado

    ic = est.get("indice_compromiso")
    dias = est.get("dias_sin_acceso")
    tareas = est.get("porcentaje_tareas")
    desconexion = (
        (ic is not None and ic < umbrales["compromiso_minimo"]) or
        (dias is not None and dias >= umbrales["dias_inactividad"]) or
        (tareas is not None and tareas < umbrales["tareas_minimo"])
    )

    if admin_irregular:
        return "Administrativa"
    if desconexion:
        return "Desconexión"
    if ic is None and dias is None and tareas is None:
        return "Sin datos"
    return "Académica"


def _compute_reprobados(
    db: Session,
    periodo: Optional[str],
    carrera: Optional[str],
    nivel: Optional[int],
    umbrales: dict,
) -> ReprobadosAnalytics:
    """Núcleo del informe (lo comparten el endpoint JSON y la exportación Excel)."""
    nota_aprob = umbrales["nota_aprobacion"]

    # ── Carrera vía Student (Grade.carrera suele venir vacío), igual que Grupos ──
    carrera_sids: Optional[list[int]] = None
    if carrera:
        carrera_sids = [
            sid for (sid,) in db.query(Student.id).filter(
                func.lower(Student.carrera).contains(carrera.lower())
            ).all()
        ]
        if not carrera_sids:
            _, periodo_norm = apply_periodo_filter(db.query(Grade.id), periodo)
            return ReprobadosAnalytics(
                periodo=periodo_norm, carrera=carrera, nivel=nivel,
                nota_aprobacion=nota_aprob,
            )

    # ── Calificaciones del período ──
    gq = db.query(
        Grade.student_id, Grade.asignatura, Grade.nota_final,
        Grade.nivel, Grade.numero_repitencias,
    ).filter(Grade.nota_final.isnot(None))
    gq, periodo_norm = apply_periodo_filter(gq, periodo, include_null=True)
    if carrera_sids is not None:
        gq = gq.filter(Grade.student_id.in_(carrera_sids))
    if nivel is not None:
        gq = gq.filter(Grade.nivel == nivel)
    grade_rows = gq.all()

    # ── Agregar por estudiante: notas, reprobadas, nivel, repitencia ──
    agg: dict[int, dict] = {}
    for sid, asig, nota, niv, nrep in grade_rows:
        a = agg.setdefault(sid, {
            "notas": [], "reprobadas": [], "nivel": None, "repitente": False,
        })
        if nota is not None:
            a["notas"].append(float(nota))
            if float(nota) < nota_aprob:
                a["reprobadas"].append((str(asig or "").strip(), float(nota)))
        if niv is not None and a["nivel"] is None:
            a["nivel"] = int(niv)
        if nrep is not None and int(nrep) > 1:
            a["repitente"] = True

    reprobado_sids = [sid for sid, a in agg.items() if a["reprobadas"]]
    if not reprobado_sids:
        return ReprobadosAnalytics(
            periodo=periodo_norm, carrera=carrera, nivel=nivel,
            nota_aprobacion=nota_aprob,
        )

    # ── Datos del estudiante (bulk) ──
    students = {
        s.id: s for s in db.query(Student).filter(Student.id.in_(reprobado_sids)).all()
    }

    # ── Grupo/paralelo y repitencia desde Enrollment del período (bulk) ──
    grupo_by_sid: dict[int, str] = {}
    nivel_by_sid: dict[int, int] = {}   # nivel confiable desde la matrícula (Grade.nivel suele venir NULL)
    eq = db.query(
        Enrollment.student_id, Enrollment.nombre_grupo,
        Enrollment.numero_repitencias, Enrollment.nivel,
    )
    eq, _ = apply_periodo_filter(eq, periodo, column=Enrollment.periodo)
    eq = eq.filter(Enrollment.student_id.in_(reprobado_sids))
    for sid, nombre_grupo, nrep, e_niv in eq.all():
        if sid not in grupo_by_sid and nombre_grupo:
            grupo_by_sid[sid] = str(nombre_grupo).strip()
        if sid not in nivel_by_sid and e_niv is not None:
            nivel_by_sid[sid] = int(e_niv)
        if nrep and int(nrep) > 1 and sid in agg:
            agg[sid]["repitente"] = True

    # ── Intervenciones (bulk): conteo, última y si quedó sin respuesta ──
    interv: dict[int, dict] = {}
    iq = (
        db.query(Intervention)
        .filter(Intervention.student_id.in_(reprobado_sids))
        .order_by(Intervention.student_id, Intervention.created_at)
        .all()
    )
    for iv in iq:
        d = interv.setdefault(iv.student_id, {"count": 0, "ultima": None, "last": None})
        d["count"] += 1
        d["ultima"] = iv.created_at
        d["last"] = iv

    estudiantes: list[ReprobadoEstudiante] = []
    kpi_causa: dict[str, int] = {}
    total_asig_rep = 0
    sin_interv_count = 0
    riesgo_alto = 0
    promedios_acum: list[float] = []

    for sid in reprobado_sids:
        a = agg[sid]
        s = students.get(sid)
        if s is None:
            continue
        reprobadas = sorted(a["reprobadas"], key=lambda x: x[1])  # peor nota primero
        promedio = round(sum(a["notas"]) / len(a["notas"]), 1) if a["notas"] else None
        total_asig_rep += len(reprobadas)
        if promedio is not None:
            promedios_acum.append(promedio)

        iv = interv.get(sid)
        num_interv = iv["count"] if iv else 0
        ultima = iv["ultima"].date().isoformat() if iv and iv["ultima"] else None
        sin_respuesta = False
        if iv and iv["last"] is not None:
            last = iv["last"]
            resultado = (last.resultado or "").strip().lower()
            req_seg = (last.requiere_seguimiento or "").strip().lower()
            sin_respuesta = (resultado in _SIN_RESPUESTA) or (req_seg == "si")
        sin_interv = num_interv == 0
        if sin_interv:
            sin_interv_count += 1

        est_dict = {
            "estado_matricula": s.estado_matricula,
            "indice_compromiso": s.indice_compromiso,
            "dias_sin_acceso": s.dias_desde_ultimo_acceso,  # último acceso real
            "porcentaje_tareas": s.porcentaje_tareas,
        }
        causa = _clasificar_causa(est_dict, umbrales)
        kpi_causa[causa] = kpi_causa.get(causa, 0) + 1

        nr = normalize_riesgo(s.nivel_riesgo)
        if nr == "Alto":
            riesgo_alto += 1

        estudiantes.append(ReprobadoEstudiante(
            student_id=sid,
            nombre=s.nombre,
            carrera=s.carrera,
            nivel=a["nivel"] if a["nivel"] is not None else nivel_by_sid.get(sid),
            grupo=grupo_by_sid.get(sid) or s.grupo,
            num_reprobadas=len(reprobadas),
            reprobadas=[AsignaturaReprobada(asignatura=n, nota=nt) for n, nt in reprobadas],
            promedio=promedio,
            es_tercera_matricula=bool(s.es_tercera_matricula),
            es_repitente=bool(a["repitente"]),
            nivel_riesgo=nr,
            indice_compromiso=s.indice_compromiso,
            dias_sin_acceso=s.dias_desde_ultimo_acceso,
            porcentaje_tareas=s.porcentaje_tareas,
            estado_matricula=s.estado_matricula,
            prob_reprobacion=s.prob_reprobacion,
            prob_desercion=s.prob_desercion,
            score_recuperabilidad=s.score_recuperabilidad,
            num_intervenciones=num_interv,
            ultima_intervencion=ultima,
            intervencion_sin_respuesta=sin_respuesta,
            sin_intervencion=sin_interv,
            causa_probable=causa,
        ))

    # Ordenar: más asignaturas reprobadas primero, luego peor promedio
    estudiantes.sort(key=lambda e: (-e.num_reprobadas, e.promedio if e.promedio is not None else 999))

    kpis = ReprobadosKPIs(
        total_reprobados=len(estudiantes),
        total_asignaturas_reprobadas=total_asig_rep,
        promedio_reprobados=round(sum(promedios_acum) / len(promedios_acum), 1) if promedios_acum else None,
        riesgo_alto=riesgo_alto,
        sin_intervencion=sin_interv_count,
        por_causa=kpi_causa,
    )

    return ReprobadosAnalytics(
        periodo=periodo_norm, carrera=carrera, nivel=nivel,
        nota_aprobacion=nota_aprob, estudiantes=estudiantes, kpis=kpis,
    )


@router.get("/reprobados", response_model=ReprobadosAnalytics)
def get_reprobados_analytics(
    periodo: Optional[str] = None,
    carrera: Optional[str] = None,
    nivel: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Informe de reprobados (período · carrera · nivel) con indicadores de porqué."""
    return _compute_reprobados(db, periodo, carrera, nivel, get_umbrales(db))


def _lectura(a: "ReprobadosAnalytics") -> list[str]:
    """Genera una lectura/análisis en español a partir de los agregados."""
    est = a.estudiantes
    n = len(est)
    if n == 0:
        return ["No hay estudiantes reprobados con los filtros seleccionados."]
    causa = a.kpis.por_causa or {}
    desc = causa.get("Desconexión", 0)
    adm = causa.get("Administrativa", 0)
    acad = causa.get("Académica", 0)
    pc = lambda x: f"{round(100 * x / n)}%"
    low_comp = sum(1 for e in est if e.indice_compromiso is not None and e.indice_compromiso < 0.35)
    sin_interv = a.kpis.sin_intervencion
    con_interv = n - sin_interv
    sin_resp = sum(1 for e in est if e.intervencion_sin_respuesta)
    todo_cero = sum(1 for e in est if e.reprobadas and all((r.nota or 0) == 0 for r in e.reprobadas))
    carrera = a.carrera or "todas las carreras"
    per = a.periodo or "el período vigente"

    L = []
    L.append(
        f"De {n} estudiantes que reprobaron al menos una asignatura en {carrera} ({per}), la causa probable se "
        f"reparte en {desc} por desconexión ({pc(desc)}), {adm} administrativa ({pc(adm)}) y {acad} académica ({pc(acad)})."
    )
    if acad == 0:
        L.append(
            "Ningún caso aparece como reprobación puramente académica: la reprobación se explica por desenganche "
            "del aula virtual y/o situación administrativa (matrícula), no por dificultad de rendimiento con el "
            "estudiante conectado."
        )
    L.append(
        f"{a.kpis.riesgo_alto} de {n} están en riesgo alto. El índice de compromiso está por debajo del umbral "
        f"(0.35) en {low_comp} de {n}: señal de desconexión del aula virtual, no de un tropiezo puntual."
    )
    L.append(
        f"Seguimiento: {con_interv} de {n} ya tienen al menos una intervención registrada y {sin_resp} quedaron "
        f"sin respuesta del estudiante — patrón típico de abandono que no se revirtió. {sin_interv} no tienen "
        f"ninguna intervención todavía."
    )
    if todo_cero:
        L.append(
            f"{todo_cero} estudiante(s) tienen TODAS sus asignaturas reprobadas en 0: suele indicar una baja "
            f"administrativa, no un cero académico real. Conviene contrastar con la nota de AVAC antes de darlos "
            f"por reprobados."
        )
    foco = "desconexión" if desc >= adm else "administrativa"
    L.append(
        f"Recomendación: priorizar los casos de riesgo alto sin intervención y los de {foco}; para los de 0 "
        f"administrativo, verificar matrícula/AVAC antes de cerrar el caso."
    )
    return L


_MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _leeme_lines(report_title: str, num_rows: int, num_cols: int) -> list[str]:
    """Contenido de la hoja LÉEME (autoría, licencia y cita), igual que el export del front."""
    from datetime import datetime
    now = datetime.now()
    fecha = f"{now.day} de {_MESES_ES[now.month - 1]} de {now.year}"
    anio = now.year
    return [
        "════════════════════════════════════════════════════════════════",
        "           DOCUMENTACIÓN Y TÉRMINOS DE USO DE DATOS",
        "════════════════════════════════════════════════════════════════",
        "",
        "1. INFORMACIÓN DE AUTORÍA Y PROPIEDAD INTELECTUAL",
        "────────────────────────────────────────────────────────────────",
        "• Desarrollado por:     Carlos Vásconez-Paredes",
        "• Cargo/Función:        Gestor de Analítica del Aprendizaje",
        "• Institución:          Universidad Politécnica Salesiana",
        f"• Fecha de generación:  {fecha}",
        "• Versión del dataset:  v1.0 (Estructurado y Procesado)",
        f"• Reporte:              {report_title}",
        "",
        "2. CONDICIONES DE USO Y RECONOCIMIENTO (LICENCIA)",
        "────────────────────────────────────────────────────────────────",
        "Este conjunto de datos, métricas e interpretaciones analíticas son el resultado",
        "de un desarrollo metodológico y técnico específico. Se autoriza su uso para",
        "fines académicos, artículos científicos, ponencias y conferencias, bajo la",
        "condición estricta de otorgar el crédito correspondiente al autor.",
        "",
        "De acuerdo con las políticas de integridad científica, la omisión de la fuente",
        "se considerará una falta a la ética académica.",
        "",
        "3. FORMA SUGERIDA DE CITA / REFERENCIA",
        "────────────────────────────────────────────────────────────────",
        "• Estilo APA (7ma ed.):",
        f"  Vásconez-Paredes, C. ({anio}). {report_title}",
        "  (Versión 1.0) [Conjunto de datos/Métricas analíticas]. Gestión de Analítica",
        "  del Aprendizaje, Universidad Politécnica Salesiana.",
        "",
        "• Estilo Vancouver / Nota al pie:",
        "  Datos analíticos y procesamiento metodológico provistos por Carlos",
        "  Vásconez-Paredes, Gestión de Analítica del Aprendizaje, Universidad",
        f"  Politécnica Salesiana, {anio}.",
        "",
        "4. CONTACTO Y COLABORACIÓN",
        "────────────────────────────────────────────────────────────────",
        "Si su investigación requiere modificaciones metodológicas en los datos, cruces",
        "de variables avanzados o una interpretación analítica conjunta que impacte la",
        "sección de \"Metodología\" o \"Resultados\" del artículo, por favor tome contacto",
        "para estructurar una participación formal bajo la figura de coautoría.",
        "",
        "Contacto: cvasconez@ups.edu.ec",
        "",
        "5. INFORMACIÓN DE ESTA EXPORTACIÓN",
        "────────────────────────────────────────────────────────────────",
        f"• Filas de datos:   {num_rows}",
        f"• Columnas:         {num_cols}",
        f"• Fecha/hora:       {now.strftime('%d/%m/%Y %H:%M:%S')}",
        "• Plataforma:       YachayDeep — Sistema de Analítica del Aprendizaje",
        "════════════════════════════════════════════════════════════════",
    ]


@router.get("/reprobados/export")
def export_reprobados_excel(
    periodo: Optional[str] = None,
    carrera: Optional[str] = None,
    nivel: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Exporta el informe a Excel con gráficas y una lectura automática de los datos."""
    import io
    from datetime import datetime
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.chart import BarChart, PieChart, Reference
    except ImportError:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="openpyxl no instalado")
    from fastapi.responses import StreamingResponse

    a = _compute_reprobados(db, periodo, carrera, nivel, get_umbrales(db))
    est = a.estudiantes

    TITLE = Font(size=16, bold=True, color="1F2937")
    H = Font(bold=True, color="FFFFFF")
    HFILL = PatternFill("solid", fgColor="2563EB")
    BOLD = Font(bold=True)
    WRAP = Alignment(wrap_text=True, vertical="top")

    wb = Workbook()

    # ── Hoja LÉEME (autoría, licencia y cita) ──
    ws_leeme = wb.active
    ws_leeme.title = "LÉEME"
    ws_leeme.sheet_view.showGridLines = False
    ws_leeme.column_dimensions["A"].width = 82
    for i, line in enumerate(_leeme_lines("Informe de Reprobados", len(est), 20), start=1):
        ws_leeme.cell(i, 1, line)

    ws = wb.create_sheet("Análisis")
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 26
    for c in "BCD":
        ws.column_dimensions[c].width = 16

    ws["A1"] = "Informe de Reprobados"
    ws["A1"].font = TITLE
    ws["A2"] = (f"Carrera: {a.carrera or 'Todas'}   ·   Período: {a.periodo or 'vigente'}   ·   "
                f"Nivel: {a.nivel or 'Todos'}   ·   Nota de aprobación: {a.nota_aprobacion}")
    ws["A3"] = f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    ws["A3"].font = Font(italic=True, color="6B7280")

    # KPIs
    r = 5
    ws.cell(r, 1, "Resumen").font = BOLD
    kpis = [
        ("Total reprobados", a.kpis.total_reprobados),
        ("Asignaturas reprobadas", a.kpis.total_asignaturas_reprobadas),
        ("Promedio reprobados", a.kpis.promedio_reprobados if a.kpis.promedio_reprobados is not None else "—"),
        ("En riesgo alto", a.kpis.riesgo_alto),
        ("Sin intervención", a.kpis.sin_intervencion),
    ]
    for i, (lab, val) in enumerate(kpis):
        ws.cell(r + 1 + i, 1, lab)
        ws.cell(r + 1 + i, 2, val).font = BOLD

    # Lectura automática
    r2 = r + len(kpis) + 3
    ws.cell(r2, 1, "Lectura automática de los datos").font = BOLD
    for i, par in enumerate(_lectura(a)):
        cell = ws.cell(r2 + 1 + i, 1, f"• {par}")
        ws.merge_cells(start_row=r2 + 1 + i, start_column=1, end_row=r2 + 1 + i, end_column=6)
        cell.alignment = WRAP
        ws.row_dimensions[r2 + 1 + i].height = 46

    # ── Tablas de datos para gráficas (más abajo) ──
    base = r2 + len(_lectura(a)) + 3
    # Causa
    ws.cell(base, 1, "Causa probable").font = BOLD
    ws.cell(base, 2, "N").font = BOLD
    causas = ["Desconexión", "Académica", "Administrativa", "Sin datos"]
    causa_rows = [(c, (a.kpis.por_causa or {}).get(c, 0)) for c in causas if (a.kpis.por_causa or {}).get(c, 0)]
    for i, (c, v) in enumerate(causa_rows):
        ws.cell(base + 1 + i, 1, c)
        ws.cell(base + 1 + i, 2, v)
    causa_end = base + len(causa_rows)
    if causa_rows:
        pie = PieChart()
        pie.title = "Reprobados por causa probable"
        data = Reference(ws, min_col=2, min_row=base, max_row=causa_end)
        cats = Reference(ws, min_col=1, min_row=base + 1, max_row=causa_end)
        pie.add_data(data, titles_from_data=True)
        pie.set_categories(cats)
        pie.height, pie.width = 7, 11
        ws.add_chart(pie, "D" + str(base))

    # Riesgo
    rbase = causa_end + 2
    riesgos = ["Alto", "Medio", "Bajo"]
    rcount = {k: 0 for k in riesgos}
    for e in est:
        if e.nivel_riesgo in rcount:
            rcount[e.nivel_riesgo] += 1
    ws.cell(rbase, 1, "Riesgo").font = BOLD
    ws.cell(rbase, 2, "N").font = BOLD
    for i, k in enumerate(riesgos):
        ws.cell(rbase + 1 + i, 1, k)
        ws.cell(rbase + 1 + i, 2, rcount[k])
    riesgo_end = rbase + len(riesgos)
    bar = BarChart()
    bar.title = "Reprobados por nivel de riesgo"
    bar.type = "col"
    bar.legend = None
    data = Reference(ws, min_col=2, min_row=rbase, max_row=riesgo_end)
    cats = Reference(ws, min_col=1, min_row=rbase + 1, max_row=riesgo_end)
    bar.add_data(data, titles_from_data=True)
    bar.set_categories(cats)
    bar.height, bar.width = 7, 11
    ws.add_chart(bar, "D" + str(rbase))

    # Intervenciones
    ibase = riesgo_end + 2
    sin_interv = a.kpis.sin_intervencion
    sin_resp = sum(1 for e in est if e.intervencion_sin_respuesta)
    con_resp = (len(est) - sin_interv) - sin_resp
    ws.cell(ibase, 1, "Intervención").font = BOLD
    ws.cell(ibase, 2, "N").font = BOLD
    inter_rows = [("Con respuesta", max(con_resp, 0)), ("Sin respuesta", sin_resp), ("Sin intervención", sin_interv)]
    for i, (k, v) in enumerate(inter_rows):
        ws.cell(ibase + 1 + i, 1, k)
        ws.cell(ibase + 1 + i, 2, v)
    inter_end = ibase + len(inter_rows)
    bar2 = BarChart()
    bar2.title = "Estado de seguimiento (intervenciones)"
    bar2.type = "col"
    bar2.legend = None
    data = Reference(ws, min_col=2, min_row=ibase, max_row=inter_end)
    cats = Reference(ws, min_col=1, min_row=ibase + 1, max_row=inter_end)
    bar2.add_data(data, titles_from_data=True)
    bar2.set_categories(cats)
    bar2.height, bar2.width = 7, 11
    ws.add_chart(bar2, "D" + str(ibase))

    # ── Hoja Detalle ──
    ws2 = wb.create_sheet("Detalle")
    cols = [
        ("Estudiante", 32), ("Carrera", 30), ("Nivel", 7), ("Grupo", 30),
        ("N° reprobadas", 12), ("Asignaturas reprobadas", 60), ("Promedio período", 14),
        ("Condición", 16), ("Riesgo", 10), ("Compromiso", 11), ("Días sin acceso AVAC", 16),
        ("% Tareas", 9), ("Matrícula", 20), ("N° intervenciones", 14), ("Última intervención", 16),
        ("Sin respuesta", 12), ("Prob. reprobación", 14), ("Prob. deserción", 14),
        ("Recuperabilidad", 14), ("Causa probable", 16),
    ]
    for j, (name, w) in enumerate(cols, start=1):
        c = ws2.cell(1, j, name)
        c.font = H
        c.fill = HFILL
        ws2.column_dimensions[chr(64 + j) if j <= 26 else "A"].width = w
    for i, e in enumerate(est, start=2):
        cond = "3ra matrícula" if e.es_tercera_matricula else ("2da matrícula" if e.es_repitente else "")
        reprs = "; ".join(f"{r.asignatura} ({r.nota})" for r in e.reprobadas)
        vals = [
            e.nombre, e.carrera, e.nivel, e.grupo, e.num_reprobadas, reprs, e.promedio, cond,
            e.nivel_riesgo, e.indice_compromiso, e.dias_sin_acceso, e.porcentaje_tareas,
            e.estado_matricula, e.num_intervenciones, e.ultima_intervencion,
            "Sí" if e.intervencion_sin_respuesta else "", e.prob_reprobacion, e.prob_desercion,
            e.score_recuperabilidad, e.causa_probable,
        ]
        for j, v in enumerate(vals, start=1):
            ws2.cell(i, j, v if v is not None else "")
    ws2.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname = f"informe_reprobados_{a.periodo or 'actual'}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
