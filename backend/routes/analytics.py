"""
Analítica de asignaturas, docentes y resumen de datos — Módulos 8.2, 8.3, 8.5.
Proporciona vistas agregadas por asignatura, por docente y resumen general.
"""
from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, distinct, extract
from pydantic import BaseModel

from ..database import get_db
from ..models import Student, Grade, Intervention, TaskSubmission, AvacAccess
from ..models.course_config import CourseConfig
from ..auth.jwt import get_current_user
from ..models.user import User

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _apply_periodo_filter(query, periodo: Optional[str], column=None):
    """Aplica filtro de período a una query de SQLAlchemy.
    Retorna (query_filtrado, periodo_normalizado)."""
    col = column or Grade.periodo
    pf = periodo if periodo else "actual"
    if pf == "actual":
        query = query.filter(col.is_(None))
    elif pf != "todos":
        query = query.filter(col == pf)
    return query, pf


# ─── Módulo 8.2: Analítica de Asignaturas ────────────────────────────────────

class AsignaturaAnalytics(BaseModel):
    asignatura: str
    carrera: Optional[str] = None
    docente: Optional[str] = None
    nivel: Optional[int] = None
    grupo: Optional[str] = None
    total_estudiantes: int = 0
    promedio_general: Optional[float] = None
    nota_maxima: Optional[float] = None
    nota_minima: Optional[float] = None
    aprobados: int = 0
    reprobados: int = 0
    porcentaje_aprobacion: Optional[float] = None
    porcentaje_reprobacion: Optional[float] = None
    total_repitentes: int = 0
    estudiantes_riesgo_alto: int = 0
    estudiantes_riesgo_medio: int = 0
    estudiantes_riesgo_bajo: int = 0
    promedio_compromiso: Optional[float] = None
    total_intervenciones: int = 0

    class Config:
        from_attributes = True


class AsignaturaDetalle(BaseModel):
    asignatura: str
    carrera: Optional[str] = None
    docente: Optional[str] = None
    nivel: Optional[int] = None
    total_estudiantes: int = 0
    promedio_general: Optional[float] = None
    aprobados: int = 0
    reprobados: int = 0
    porcentaje_aprobacion: Optional[float] = None
    total_repitentes: int = 0
    estudiantes: list = []

    class Config:
        from_attributes = True


@router.get("/asignaturas", response_model=list[AsignaturaAnalytics])
def get_asignaturas_analytics(
    carrera: Optional[str] = None,
    nivel: Optional[int] = None,
    solo_criticas: bool = False,
    periodo: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Vista agregada por asignatura (semestre actual).
    Framework §8.2: promedios, aprobación, reprobación, repitencia,
    materias críticas, actividades no entregadas.
    """
    # Calificaciones del período seleccionado
    query = db.query(
        Grade.asignatura,
        Grade.carrera,
        Grade.docente,
        Grade.nivel,
        Grade.grupo,
        func.count(Grade.id).label("total_estudiantes"),
        func.avg(Grade.nota_final).label("promedio_general"),
        func.max(Grade.nota_final).label("nota_maxima"),
        func.min(Grade.nota_final).label("nota_minima"),
        func.sum(case((Grade.nota_final >= 70, 1), else_=0)).label("aprobados"),
        func.sum(case((and_(Grade.nota_final < 70, Grade.nota_final.isnot(None)), 1), else_=0)).label("reprobados"),
        func.sum(case((Grade.numero_repitencias > 0, 1), else_=0)).label("total_repitentes"),
    )
    query, _ = _apply_periodo_filter(query, periodo)
    query = query.group_by(Grade.asignatura, Grade.carrera, Grade.docente, Grade.nivel, Grade.grupo)

    if carrera:
        query = query.filter(func.lower(Grade.carrera).contains(carrera.lower()))
    if nivel:
        query = query.filter(Grade.nivel == nivel)

    results = query.order_by(Grade.asignatura).all()

    # ── Precomputar datos de riesgo y compromiso en batch (evita N+1) ──
    # Riesgo por asignatura+docente
    risk_batch_q = (
        db.query(
            Grade.asignatura,
            Grade.docente,
            Student.nivel_riesgo,
            func.count(distinct(Student.id)).label("cnt"),
        )
        .join(Student, Student.id == Grade.student_id)
    )
    risk_batch_q, _ = _apply_periodo_filter(risk_batch_q, periodo)
    risk_batch = risk_batch_q.group_by(Grade.asignatura, Grade.docente, Student.nivel_riesgo).all()
    # {(asignatura, docente): {"Alto": N, "Medio": N, ...}}
    risk_lookup = {}
    for rb in risk_batch:
        key = (rb.asignatura, rb.docente)
        if key not in risk_lookup:
            risk_lookup[key] = {}
        risk_lookup[key][rb.nivel_riesgo] = rb.cnt

    # Promedio compromiso por asignatura+docente
    comp_batch_q = (
        db.query(
            Grade.asignatura,
            Grade.docente,
            func.avg(Student.indice_compromiso).label("avg_comp"),
        )
        .join(Student, Student.id == Grade.student_id)
    )
    comp_batch_q, _ = _apply_periodo_filter(comp_batch_q, periodo)
    comp_batch = comp_batch_q.group_by(Grade.asignatura, Grade.docente).all()
    comp_lookup = {(c.asignatura, c.docente): c.avg_comp for c in comp_batch}

    # Intervenciones por asignatura
    interv_batch = (
        db.query(
            Intervention.asignatura,
            func.count(Intervention.id).label("total"),
        )
        .filter(Intervention.asignatura.isnot(None))
        .group_by(Intervention.asignatura)
        .all()
    )
    interv_lookup = {ib.asignatura: ib.total for ib in interv_batch}

    output = []
    for r in results:
        total = r.total_estudiantes or 1
        pct_aprob = round((r.aprobados / total) * 100, 1) if r.aprobados is not None else None
        pct_reprob = round((r.reprobados / total) * 100, 1) if r.reprobados is not None else None

        key = (r.asignatura, r.docente)
        risk_map = risk_lookup.get(key, {})
        avg_compromiso = comp_lookup.get(key)
        total_interv = interv_lookup.get(r.asignatura, 0)

        item = AsignaturaAnalytics(
            asignatura=r.asignatura,
            carrera=r.carrera,
            docente=r.docente,
            nivel=r.nivel,
            grupo=r.grupo,
            total_estudiantes=r.total_estudiantes,
            promedio_general=round(r.promedio_general, 1) if r.promedio_general else None,
            nota_maxima=r.nota_maxima,
            nota_minima=r.nota_minima,
            aprobados=r.aprobados or 0,
            reprobados=r.reprobados or 0,
            porcentaje_aprobacion=pct_aprob,
            porcentaje_reprobacion=pct_reprob,
            total_repitentes=r.total_repitentes or 0,
            estudiantes_riesgo_alto=risk_map.get("Alto", 0),
            estudiantes_riesgo_medio=risk_map.get("Medio", 0),
            estudiantes_riesgo_bajo=risk_map.get("Bajo", 0),
            promedio_compromiso=round(avg_compromiso, 2) if avg_compromiso else None,
            total_intervenciones=total_interv,
        )

        # Filtro materias críticas: >50% reprobación o promedio < 60
        if solo_criticas:
            is_critica = (pct_reprob and pct_reprob > 50) or \
                         (r.promedio_general and r.promedio_general < 60)
            if not is_critica:
                continue

        output.append(item)

    return output


@router.get("/asignaturas/{asignatura}/detalle")
def get_asignatura_detalle(
    asignatura: str,
    docente: Optional[str] = None,
    periodo: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Detalle de una asignatura: lista de estudiantes con sus indicadores.
    """
    query = db.query(Grade).filter(Grade.asignatura == asignatura)
    query, _ = _apply_periodo_filter(query, periodo)
    if docente:
        query = query.filter(Grade.docente == docente)

    grades = query.all()
    if not grades:
        return {"asignatura": asignatura, "estudiantes": [], "total_estudiantes": 0}

    student_ids = [g.student_id for g in grades]
    students = db.query(Student).filter(Student.id.in_(student_ids)).all()
    student_map = {s.id: s for s in students}

    # Intervenciones por estudiante en esta asignatura
    interv_counts = dict(
        db.query(Intervention.student_id, func.count(Intervention.id))
        .filter(Intervention.student_id.in_(student_ids), Intervention.asignatura == asignatura)
        .group_by(Intervention.student_id)
        .all()
    )

    estudiantes_out = []
    for g in grades:
        s = student_map.get(g.student_id)
        if not s:
            continue
        estudiantes_out.append({
            "student_id": s.id,
            "nombre": s.nombre,
            "correo_institucional": s.correo_institucional,
            "cedula": s.cedula,
            "nota_final": g.nota_final,
            "numero_repitencias": g.numero_repitencias,
            "nivel_riesgo": s.nivel_riesgo,
            "indice_compromiso": s.indice_compromiso,
            "dias_sin_acceso": s.dias_sin_acceso,
            "porcentaje_tareas": s.porcentaje_tareas,
            "estado_matricula": s.estado_matricula,
            "intervenciones_asignatura": interv_counts.get(s.id, 0),
        })

    # Ordenar: reprobados primero, luego por nota ascendente
    estudiantes_out.sort(key=lambda x: (x["nota_final"] or 0))

    first_grade = grades[0]
    total = len(estudiantes_out)
    aprobados = sum(1 for e in estudiantes_out if e["nota_final"] and e["nota_final"] >= 70)

    return {
        "asignatura": asignatura,
        "carrera": first_grade.carrera,
        "docente": first_grade.docente or docente,
        "nivel": first_grade.nivel,
        "total_estudiantes": total,
        "promedio_general": round(sum(e["nota_final"] or 0 for e in estudiantes_out) / max(total, 1), 1),
        "aprobados": aprobados,
        "reprobados": total - aprobados,
        "porcentaje_aprobacion": round((aprobados / max(total, 1)) * 100, 1),
        "total_repitentes": sum(1 for e in estudiantes_out if e["numero_repitencias"] and e["numero_repitencias"] > 0),
        "estudiantes": estudiantes_out,
    }


# ─── Módulo 8.3: Analítica Docente ───────────────────────────────────────────

class DocenteAnalytics(BaseModel):
    docente: str
    total_asignaturas: int = 0
    total_estudiantes: int = 0
    carreras: list[str] = []
    niveles: list[int] = []
    promedio_general: Optional[float] = None
    porcentaje_aprobacion: Optional[float] = None
    porcentaje_reprobacion: Optional[float] = None
    estudiantes_riesgo_alto: int = 0
    estudiantes_riesgo_medio: int = 0
    estudiantes_riesgo_bajo: int = 0
    promedio_compromiso: Optional[float] = None
    total_intervenciones: int = 0
    asignaturas: list[str] = []

    class Config:
        from_attributes = True


class DocenteDetalle(BaseModel):
    docente: str
    total_asignaturas: int = 0
    total_estudiantes: int = 0
    carreras: list[str] = []
    promedio_general: Optional[float] = None
    porcentaje_aprobacion: Optional[float] = None
    estudiantes_riesgo_alto: int = 0
    asignaturas_detalle: list = []

    class Config:
        from_attributes = True


@router.get("/docentes", response_model=list[DocenteAnalytics])
def get_docentes_analytics(
    carrera: Optional[str] = None,
    periodo: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Vista agregada por docente.
    Framework §8.3: materias a cargo, carreras, número de estudiantes,
    concentración de estudiantes en riesgo.
    """
    # Obtener docentes únicos del período seleccionado
    docente_query = (
        db.query(Grade.docente)
        .filter(Grade.docente.isnot(None), Grade.docente != "")
    )
    docente_query, _ = _apply_periodo_filter(docente_query, periodo)
    docente_query = docente_query.distinct()
    if carrera:
        docente_query = docente_query.filter(func.lower(Grade.carrera).contains(carrera.lower()))

    docentes = [d.docente for d in docente_query.all()]

    output = []
    for docente_name in docentes:
        # Estadísticas agregadas de este docente
        grades_q = db.query(Grade).filter(Grade.docente == docente_name)
        grades_q, _ = _apply_periodo_filter(grades_q, periodo)
        if carrera:
            grades_q = grades_q.filter(func.lower(Grade.carrera).contains(carrera.lower()))

        all_grades = grades_q.all()
        if not all_grades:
            continue

        asignaturas = list(set(g.asignatura for g in all_grades))
        carreras_set = list(set(g.carrera for g in all_grades if g.carrera))
        niveles_set = sorted(set(g.nivel for g in all_grades if g.nivel))
        student_ids = list(set(g.student_id for g in all_grades))
        total_est = len(student_ids)
        notas = [g.nota_final for g in all_grades if g.nota_final is not None]
        promedio = round(sum(notas) / max(len(notas), 1), 1) if notas else None
        aprobados = sum(1 for n in notas if n >= 70)
        pct_aprob = round((aprobados / max(len(notas), 1)) * 100, 1) if notas else None
        pct_reprob = round(((len(notas) - aprobados) / max(len(notas), 1)) * 100, 1) if notas else None

        # Riesgo de sus estudiantes
        risk_counts = (
            db.query(Student.nivel_riesgo, func.count(Student.id))
            .filter(Student.id.in_(student_ids))
            .group_by(Student.nivel_riesgo)
            .all()
        )
        risk_map = {r[0]: r[1] for r in risk_counts}

        # Promedio compromiso
        avg_comp = (
            db.query(func.avg(Student.indice_compromiso))
            .filter(Student.id.in_(student_ids))
            .scalar()
        )

        # Intervenciones totales en asignaturas de este docente
        total_interv = (
            db.query(func.count(Intervention.id))
            .filter(Intervention.docente == docente_name)
            .scalar()
        ) or 0

        output.append(DocenteAnalytics(
            docente=docente_name,
            total_asignaturas=len(asignaturas),
            total_estudiantes=total_est,
            carreras=carreras_set,
            niveles=niveles_set,
            promedio_general=promedio,
            porcentaje_aprobacion=pct_aprob,
            porcentaje_reprobacion=pct_reprob,
            estudiantes_riesgo_alto=risk_map.get("Alto", 0),
            estudiantes_riesgo_medio=risk_map.get("Medio", 0),
            estudiantes_riesgo_bajo=risk_map.get("Bajo", 0),
            promedio_compromiso=round(avg_comp, 2) if avg_comp else None,
            total_intervenciones=total_interv,
            asignaturas=sorted(asignaturas),
        ))

    # Ordenar por concentración de riesgo alto descendente
    output.sort(key=lambda x: x.estudiantes_riesgo_alto, reverse=True)
    return output


@router.get("/docentes/{docente_nombre}/detalle")
def get_docente_detalle(
    docente_nombre: str,
    periodo: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Ficha detallada del docente: asignaturas con desglose de estudiantes y riesgo.
    """
    grades_q = db.query(Grade).filter(Grade.docente == docente_nombre)
    grades_q, _ = _apply_periodo_filter(grades_q, periodo)
    grades = grades_q.all()
    if not grades:
        return {"docente": docente_nombre, "asignaturas_detalle": [], "total_estudiantes": 0}

    # Agrupar por asignatura
    asig_map = {}
    for g in grades:
        key = g.asignatura
        if key not in asig_map:
            asig_map[key] = {"asignatura": key, "carrera": g.carrera, "nivel": g.nivel, "grades": []}
        asig_map[key]["grades"].append(g)

    all_student_ids = list(set(g.student_id for g in grades))
    students = db.query(Student).filter(Student.id.in_(all_student_ids)).all()
    student_map = {s.id: s for s in students}

    asignaturas_detalle = []
    for key, data in sorted(asig_map.items()):
        gs = data["grades"]
        notas = [g.nota_final for g in gs if g.nota_final is not None]
        sids = [g.student_id for g in gs]

        est_list = []
        for g in gs:
            s = student_map.get(g.student_id)
            if s:
                est_list.append({
                    "student_id": s.id,
                    "nombre": s.nombre,
                    "nota_final": g.nota_final,
                    "nivel_riesgo": s.nivel_riesgo,
                    "indice_compromiso": s.indice_compromiso,
                    "dias_sin_acceso": s.dias_sin_acceso,
                })

        aprobados = sum(1 for n in notas if n >= 70)
        total = len(notas) if notas else 1

        asignaturas_detalle.append({
            "asignatura": data["asignatura"],
            "carrera": data["carrera"],
            "nivel": data["nivel"],
            "total_estudiantes": len(gs),
            "promedio": round(sum(notas) / max(total, 1), 1) if notas else None,
            "aprobados": aprobados,
            "reprobados": len(notas) - aprobados,
            "porcentaje_aprobacion": round((aprobados / max(total, 1)) * 100, 1),
            "riesgo_alto": sum(1 for e in est_list if e["nivel_riesgo"] == "Alto"),
            "estudiantes": sorted(est_list, key=lambda x: (x["nota_final"] or 0)),
        })

    carreras = list(set(g.carrera for g in grades if g.carrera))

    return {
        "docente": docente_nombre,
        "total_asignaturas": len(asignaturas_detalle),
        "total_estudiantes": len(all_student_ids),
        "carreras": carreras,
        "promedio_general": round(
            sum(g.nota_final for g in grades if g.nota_final) / max(sum(1 for g in grades if g.nota_final), 1), 1
        ),
        "asignaturas_detalle": asignaturas_detalle,
    }


# ─── Módulo 8.4: Tutorías por asignatura ─────────────────────────────────────

class TutoriaAsignatura(BaseModel):
    asignatura: str
    docente: Optional[str] = None
    carrera: Optional[str] = None
    nivel: Optional[int] = None
    total_en_riesgo: int = 0
    estudiantes: list = []

    class Config:
        from_attributes = True


@router.get("/tutorias/por-asignatura", response_model=list[TutoriaAsignatura])
def get_tutorias_por_asignatura(
    carrera: Optional[str] = None,
    nivel_riesgo: str = Query("Alto", description="Alto, Medio, o Alto,Medio"),
    periodo: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Framework §8.4 — Listas de tutoría por asignatura.
    Agrupa estudiantes en riesgo por materia para generar convocatorias.
    Lógica: detectar riesgo → clasificar motivo → agrupar por materia →
    entregar listado al docente → convocar a tutoría.
    """
    niveles_filtro = [n.strip() for n in nivel_riesgo.split(",")]

    # Estudiantes en riesgo
    risk_students = (
        db.query(Student)
        .filter(Student.nivel_riesgo.in_(niveles_filtro))
    )
    if carrera:
        risk_students = risk_students.filter(func.lower(Student.carrera).contains(carrera.lower()))

    risk_students = risk_students.all()
    if not risk_students:
        return []

    risk_ids = [s.id for s in risk_students]
    student_map = {s.id: s for s in risk_students}

    # Calificaciones del período seleccionado para estos estudiantes
    grades_q = db.query(Grade).filter(Grade.student_id.in_(risk_ids))
    grades_q, _ = _apply_periodo_filter(grades_q, periodo)
    grades = grades_q.all()

    # Intervenciones existentes por (student_id, asignatura)
    existing_interv = dict(
        db.query(
            Intervention.student_id,
            func.count(Intervention.id),
        )
        .filter(Intervention.student_id.in_(risk_ids))
        .group_by(Intervention.student_id)
        .all()
    )

    # Agrupar por asignatura
    asig_map = {}
    for g in grades:
        key = g.asignatura
        if key not in asig_map:
            asig_map[key] = {
                "asignatura": g.asignatura,
                "docente": g.docente,
                "carrera": g.carrera,
                "nivel": g.nivel,
                "estudiantes": [],
            }
        s = student_map.get(g.student_id)
        if not s:
            continue

        # Determinar motivo principal de riesgo
        motivos = []
        if s.dias_sin_acceso and s.dias_sin_acceso > 14:
            motivos.append("Inactividad AVAC")
        if s.porcentaje_tareas is not None and s.porcentaje_tareas < 50:
            motivos.append("Tareas no entregadas")
        if g.nota_final is not None and g.nota_final < 70:
            motivos.append("Bajo rendimiento")
        if s.indice_compromiso is not None and s.indice_compromiso < 0.4:
            motivos.append("Bajo compromiso")
        if not motivos:
            motivos.append("Riesgo general")

        asig_map[key]["estudiantes"].append({
            "student_id": s.id,
            "nombre": s.nombre,
            "correo_institucional": s.correo_institucional,
            "telefono": s.telefono,
            "whatsapp": s.whatsapp,
            "nivel_riesgo": s.nivel_riesgo,
            "nota_asignatura": g.nota_final,
            "indice_compromiso": s.indice_compromiso,
            "dias_sin_acceso": s.dias_sin_acceso,
            "motivos_riesgo": motivos,
            "intervenciones_previas": existing_interv.get(s.id, 0),
        })

    output = []
    for data in asig_map.values():
        data["total_en_riesgo"] = len(data["estudiantes"])
        # Ordenar estudiantes por gravedad (riesgo Alto primero, luego nota más baja)
        data["estudiantes"].sort(
            key=lambda x: (0 if x["nivel_riesgo"] == "Alto" else 1, x["nota_asignatura"] or 0)
        )
        output.append(TutoriaAsignatura(**data))

    # Ordenar asignaturas por total en riesgo descendente
    output.sort(key=lambda x: x.total_en_riesgo, reverse=True)
    return output


# ─── Módulo 8.5: Resumen de Datos ────────────────────────────────────────────

@router.get("/periodos")
def get_periodos_disponibles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista de períodos disponibles en calificaciones."""
    periodos_raw = (
        db.query(Grade.periodo)
        .distinct()
        .all()
    )
    periodos = []
    for (p,) in periodos_raw:
        if p is None:
            periodos.append({"key": "actual", "label": "Semestre actual"})
        else:
            periodos.append({"key": p, "label": p})
    # Ordenar: "actual" primero, luego por key descendente (P67 > P60)
    periodos.sort(key=lambda x: ("0" if x["key"] == "actual" else "1" + x["key"]), reverse=True)
    periodos.reverse()
    return periodos


@router.get("/resumen")
def get_resumen_datos(
    carrera: Optional[str] = None,
    periodo: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Resumen estadístico general y por carrera:
    estudiantes, niveles, reprobados, repitentes, desertores,
    promedio calificaciones, docentes, ciudades, edad promedio.
    Filtra por período: "actual" = semestre actual, "P60"-"P67" = históricos.
    """
    today = date.today()

    # --- Calificaciones del período seleccionado ---
    grades_q = db.query(Grade)
    grades_q, periodo_filter = _apply_periodo_filter(grades_q, periodo)
    if carrera:
        grades_q = grades_q.filter(func.lower(Grade.carrera).contains(carrera.lower()))
    grades = grades_q.all()

    # Obtener IDs de estudiantes que tienen calificaciones en este período
    grade_student_ids = set(g.student_id for g in grades)

    # --- Base query de estudiantes ---
    # Filtrar solo estudiantes que tienen calificaciones en el período seleccionado.
    # Esto evita incluir desertores de períodos anteriores en el conteo actual.
    base_q = db.query(Student)
    if carrera:
        base_q = base_q.filter(func.lower(Student.carrera).contains(carrera.lower()))
    if periodo_filter != "todos" and grade_student_ids:
        base_q = base_q.filter(Student.id.in_(grade_student_ids))
    students = base_q.all()

    if not students:
        return {"global": {}, "por_carrera": [], "periodos_disponibles": []}

    student_ids = set(s.id for s in students)

    # Reprobados: estudiantes con al menos una nota < 70
    reprobados_ids = set()
    repitentes_ids = set()
    for g in grades:
        if g.student_id in student_ids:
            if g.nota_final is not None and g.nota_final < 70:
                reprobados_ids.add(g.student_id)
            if g.numero_repitencias and g.numero_repitencias > 0:
                repitentes_ids.add(g.student_id)

    # Docentes únicos del período
    docentes_q = db.query(func.count(distinct(Grade.docente))).filter(
        Grade.docente.isnot(None), Grade.docente != ""
    )
    docentes_q, _ = _apply_periodo_filter(docentes_q, periodo)
    if carrera:
        docentes_q = docentes_q.filter(func.lower(Grade.carrera).contains(carrera.lower()))
    total_docentes = docentes_q.scalar() or 0

    # --- Cálculos globales ---
    def compute_stats(student_list, grade_list):
        total = len(student_list)
        if total == 0:
            return {}

        # Niveles académicos
        niveles = {}
        for s in student_list:
            niv = s.nivel_academico or 0
            niveles[niv] = niveles.get(niv, 0) + 1

        # Riesgo — solo contar estudiantes que tienen nivel_riesgo calculado
        riesgo = {"Alto": 0, "Medio": 0, "Bajo": 0}
        for s in student_list:
            r = s.nivel_riesgo
            if r and r in riesgo:
                riesgo[r] += 1

        # Ciudades
        ciudades = {}
        for s in student_list:
            c = s.ciudad or "Sin dato"
            ciudades[c] = ciudades.get(c, 0) + 1

        # Sedes — para períodos históricos usar Grade.sede (más preciso)
        sedes = {}
        if periodo_filter not in ("actual", "todos"):
            sede_students = {}
            for g in grade_list:
                sede = g.sede or "Sin dato"
                sede_students.setdefault(sede, set()).add(g.student_id)
            sedes = {k: len(v) for k, v in sede_students.items()}
        else:
            for s in student_list:
                sede = s.sede or "Sin dato"
                sedes[sede] = sedes.get(sede, 0) + 1

        # Género
        generos = {}
        for s in student_list:
            g = s.genero or "Sin dato"
            generos[g] = generos.get(g, 0) + 1

        # Autoidentificación étnica
        etnias = {}
        for s in student_list:
            e = s.autoidentificacion_etnica or "Sin dato"
            etnias[e] = etnias.get(e, 0) + 1

        # Edad promedio
        edades = []
        for s in student_list:
            if s.fecha_nacimiento:
                edad = (today - s.fecha_nacimiento).days / 365.25
                edades.append(edad)
        promedio_edad = round(sum(edades) / len(edades), 1) if edades else None

        # Promedio calificaciones por estudiante (promedio de promedios, no promedio plano)
        # Esto evita que estudiantes con más materias pesen más que otros
        sid_set_for_grades = set(s.id for s in student_list)
        notas_por_estudiante = {}
        for g in grade_list:
            if g.student_id in sid_set_for_grades and g.nota_final is not None:
                notas_por_estudiante.setdefault(g.student_id, []).append(g.nota_final)
        if notas_por_estudiante:
            promedios_ind = [sum(ns) / len(ns) for ns in notas_por_estudiante.values()]
            promedio_calif = round(sum(promedios_ind) / len(promedios_ind), 1)
        else:
            promedio_calif = None

        # Estado matrícula
        estados = {}
        for s in student_list:
            est = s.estado_matricula or "Sin dato"
            estados[est] = estados.get(est, 0) + 1

        # Reprobados/repitentes de este grupo
        sid_set = set(s.id for s in student_list)
        reprob = len(reprobados_ids & sid_set)
        repit = len(repitentes_ids & sid_set)

        # Prob deserción alta (>0.5)
        desertores_prob = sum(1 for s in student_list if s.prob_desercion and s.prob_desercion > 0.5)

        # Compromiso promedio
        compromisos = [s.indice_compromiso for s in student_list if s.indice_compromiso is not None]
        promedio_compromiso = round(sum(compromisos) / len(compromisos), 2) if compromisos else None

        # Conteos de cobertura de datos
        con_riesgo = sum(1 for s in student_list if s.nivel_riesgo)
        con_calificacion = len(notas_por_estudiante)

        return {
            "total_estudiantes": total,
            "con_riesgo_calculado": con_riesgo,
            "con_calificaciones": con_calificacion,
            "por_nivel": dict(sorted(niveles.items())),
            "por_riesgo": riesgo,
            "reprobados": reprob,
            "repitentes": repit,
            "desertores_prob": desertores_prob,
            "promedio_calificaciones": promedio_calif,
            "promedio_edad": promedio_edad,
            "promedio_compromiso": promedio_compromiso,
            "por_ciudad": dict(sorted(ciudades.items(), key=lambda x: -x[1])),
            "por_sede": dict(sorted(sedes.items(), key=lambda x: -x[1])),
            "por_genero": generos,
            "por_etnia": dict(sorted(etnias.items(), key=lambda x: -x[1])),
            "por_estado_matricula": estados,
        }

    global_stats = compute_stats(students, grades)
    global_stats["total_docentes"] = total_docentes

    # --- Estadísticas de intervenciones ---
    interv_base_q = db.query(Intervention)
    if carrera:
        interv_base_q = interv_base_q.filter(func.lower(Intervention.carrera).contains(carrera.lower()))

    # Filtrar intervenciones solo de estudiantes con calificaciones en el período
    if periodo_filter != "todos" and grade_student_ids:
        interv_base_q = interv_base_q.filter(Intervention.student_id.in_(grade_student_ids))

    total_intervenciones = interv_base_q.count()

    # Por motivo
    por_motivo_interv = (
        interv_base_q.with_entities(Intervention.motivo, func.count(Intervention.id))
        .group_by(Intervention.motivo).all()
    )
    # Por resultado (resueltas vs pendientes)
    por_resultado_interv = (
        interv_base_q.with_entities(Intervention.resultado, func.count(Intervention.id))
        .group_by(Intervention.resultado).all()
    )
    # Por seguimiento
    pendientes_seg = (
        interv_base_q.filter(Intervention.requiere_seguimiento == "si").count()
    )
    resueltas = (
        interv_base_q.filter(Intervention.estado == "Recuperado").count()
    )
    # Por carrera (intervenciones)
    interv_por_carrera = (
        interv_base_q.with_entities(Intervention.carrera, func.count(Intervention.id))
        .group_by(Intervention.carrera).all()
    )

    global_stats["intervenciones"] = {
        "total": total_intervenciones,
        "por_motivo": {m or "Sin motivo": c for m, c in por_motivo_interv},
        "por_resultado": {r or "Sin resultado": c for r, c in por_resultado_interv},
        "pendientes_seguimiento": pendientes_seg,
        "resueltas": resueltas,
        "por_carrera": {car or "Sin carrera": cnt for car, cnt in interv_por_carrera},
    }

    # --- Por carrera ---
    carreras_map = {}
    for s in students:
        c = s.carrera or "Sin carrera"
        if c not in carreras_map:
            carreras_map[c] = []
        carreras_map[c].append(s)

    # Docentes por carrera (del período seleccionado)
    docentes_carrera_q_base = db.query(Grade.carrera, func.count(distinct(Grade.docente))).filter(
        Grade.docente.isnot(None), Grade.docente != ""
    )
    docentes_carrera_q_base, _ = _apply_periodo_filter(docentes_carrera_q_base, periodo)
    docentes_carrera_q = docentes_carrera_q_base.group_by(Grade.carrera).all()
    docentes_por_carrera = {r[0]: r[1] for r in docentes_carrera_q}

    # Intervenciones por carrera con detalle motivo
    interv_carrera_motivo = {}
    for inv in interv_base_q.all():
        car = inv.carrera or "Sin carrera"
        if car not in interv_carrera_motivo:
            interv_carrera_motivo[car] = {"total": 0, "por_motivo": {}, "pendientes": 0, "resueltas": 0}
        interv_carrera_motivo[car]["total"] += 1
        mot = inv.motivo or "Sin motivo"
        interv_carrera_motivo[car]["por_motivo"][mot] = interv_carrera_motivo[car]["por_motivo"].get(mot, 0) + 1
        if inv.requiere_seguimiento == "si":
            interv_carrera_motivo[car]["pendientes"] += 1
        if inv.estado == "Recuperado":
            interv_carrera_motivo[car]["resueltas"] += 1

    por_carrera = []
    for nombre_carrera, sts in sorted(carreras_map.items()):
        # Incluir calificaciones donde la carrera coincide exactamente O por student_id
        sts_ids = set(s.id for s in sts)
        grades_carrera = [g for g in grades if g.student_id in sts_ids]
        stats = compute_stats(sts, grades_carrera)
        stats["carrera"] = nombre_carrera
        stats["total_docentes"] = docentes_por_carrera.get(nombre_carrera, 0)
        stats["intervenciones"] = interv_carrera_motivo.get(nombre_carrera, {"total": 0, "por_motivo": {}, "pendientes": 0, "resueltas": 0})
        por_carrera.append(stats)

    return {"global": global_stats, "por_carrera": por_carrera}


@router.get("/comparativa")
def get_comparativa(
    carrera: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    KPIs por período para gráficos de tendencia.
    Retorna una lista con métricas de cada período disponible.
    """
    # Obtener períodos disponibles
    periodos_raw = (
        db.query(Grade.periodo)
        .distinct()
        .order_by(Grade.periodo)
        .all()
    )
    periodos = []
    for (p,) in periodos_raw:
        if p is not None:
            periodos.append(p)
    periodos.append("actual")  # Agregar período actual al final

    result = []
    for per in periodos:
        # Query de calificaciones del período
        g_q = db.query(Grade)
        if per == "actual":
            g_q = g_q.filter(Grade.periodo.is_(None))
        else:
            g_q = g_q.filter(Grade.periodo == per)
        if carrera:
            g_q = g_q.filter(func.lower(Grade.carrera).contains(carrera.lower()))

        grades = g_q.all()
        if not grades:
            continue

        student_ids = set(g.student_id for g in grades)

        # Total estudiantes únicos
        total_est = len(student_ids)

        # Promedio calificaciones (promedio de promedios por estudiante)
        notas_por_est = {}
        for g in grades:
            if g.nota_final is not None:
                notas_por_est.setdefault(g.student_id, []).append(g.nota_final)
        if notas_por_est:
            promedios = [sum(ns) / len(ns) for ns in notas_por_est.values()]
            promedio_calif = round(sum(promedios) / len(promedios), 1)
        else:
            promedio_calif = None

        # Tasa aprobación (estudiantes con promedio >= 70 / total con notas)
        if notas_por_est:
            aprobados = sum(1 for ns in notas_por_est.values() if (sum(ns) / len(ns)) >= 70)
            tasa_aprob = round(aprobados / len(notas_por_est) * 100, 1)
        else:
            tasa_aprob = None

        # Riesgo alto
        students_with_risk = (
            db.query(func.count(Student.id))
            .filter(Student.id.in_(student_ids), Student.nivel_riesgo == "Alto")
            .scalar() or 0
        )

        # Total docentes
        docentes_set = set()
        for g in grades:
            if g.docente:
                docentes_set.add(g.docente)
        total_doc = len(docentes_set)

        # Total intervenciones de estudiantes de este período
        total_interv = (
            db.query(func.count(Intervention.id))
            .filter(Intervention.student_id.in_(student_ids))
            .scalar() or 0
        )

        label = "Actual" if per == "actual" else per
        result.append({
            "periodo": per,
            "label": label,
            "total_estudiantes": total_est,
            "promedio_calificaciones": promedio_calif,
            "tasa_aprobacion": tasa_aprob,
            "riesgo_alto": students_with_risk,
            "total_docentes": total_doc,
            "total_intervenciones": total_interv,
        })

    return result
