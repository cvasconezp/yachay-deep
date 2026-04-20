"""
Módulo 8.2: Analítica de Asignaturas.
Separado de analytics.py monolítico — [ARCH-03] Remediación.

Cuando no hay calificaciones (grades) para un periodo, usa datos de
Enrollment como fallback, mostrando la estructura académica matriculada
sin métricas de rendimiento (inicio de semestre).
"""
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, distinct, or_
from pydantic import BaseModel

from ...database import get_db
from ...models import Student, Grade, Intervention, Enrollment
from ...models.course_config import CourseConfig
from ...auth.jwt import get_current_user
from ...models.user import User
from ._helpers import apply_periodo_filter

router = APIRouter(prefix="/analytics", tags=["analytics"])


class AsignaturaAnalytics(BaseModel):
    asignatura: str
    carrera: Optional[str] = None
    docente: Optional[str] = None
    nivel: Optional[int] = None
    grupo: Optional[str] = None
    codigo_avac: Optional[str] = None
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


def _enrollment_periodo_filter(query, periodo: Optional[str]):
    """Aplica filtro de periodo a Enrollment (mismo dual-format que grades)."""
    col = Enrollment.periodo
    pf = periodo if periodo else "actual"
    if pf == "actual":
        # Para enrollment, 'actual' usa semestre activo
        from ...models.semester_config import SemesterConfig
        from sqlalchemy.orm import Session as _S
        return query, pf
    elif pf != "todos":
        if pf.startswith("P"):
            raw = pf[1:]
            query = query.filter(or_(col == pf, col == raw))
        else:
            query = query.filter(or_(col == pf, col == f"P{pf}"))
    return query, pf


def _get_enrollment_results(db: Session, periodo: Optional[str], carrera: Optional[str], nivel: Optional[int]):
    """Genera resultados de asignaturas desde Enrollment (sin calificaciones)."""
    query = db.query(
        Enrollment.asignatura, Enrollment.carrera, Enrollment.docente,
        Enrollment.nivel, Enrollment.nombre_grupo.label("grupo"),
        func.count(Enrollment.id).label("total_estudiantes"),
        func.sum(case((Enrollment.numero_repitencias > 1, 1), else_=0)).label("total_repitentes"),
    )
    query, _ = _enrollment_periodo_filter(query, periodo)
    query = query.group_by(
        Enrollment.asignatura, Enrollment.carrera, Enrollment.docente,
        Enrollment.nivel, Enrollment.nombre_grupo,
    )
    if carrera:
        query = query.filter(func.lower(Enrollment.carrera).contains(carrera.lower()))
    if nivel:
        query = query.filter(Enrollment.nivel == nivel)

    results = query.order_by(Enrollment.asignatura).all()

    # Riesgo por asignatura+docente desde enrollments
    risk_q = (
        db.query(Enrollment.asignatura, Enrollment.docente, Student.nivel_riesgo,
                 func.count(distinct(Student.id)).label("cnt"))
        .join(Student, Student.id == Enrollment.student_id)
    )
    risk_q, _ = _enrollment_periodo_filter(risk_q, periodo)
    risk_batch = risk_q.group_by(Enrollment.asignatura, Enrollment.docente, Student.nivel_riesgo).all()
    risk_lookup = {}
    for rb in risk_batch:
        key = (rb.asignatura, rb.docente)
        risk_lookup.setdefault(key, {})[rb.nivel_riesgo] = rb.cnt

    # Lookup codigo_avac from Enrollment.codigo_grupo
    enr_avac = {}
    for r in results:
        # codigo_grupo from Enrollment acts as codigo_avac
        enr_code_q = db.query(Enrollment.codigo_grupo).filter(
            Enrollment.asignatura == r.asignatura,
            Enrollment.docente == r.docente,
            Enrollment.codigo_grupo.isnot(None),
        ).first()
        if enr_code_q and enr_code_q[0]:
            enr_avac[(r.asignatura, r.docente)] = enr_code_q[0]

    output = []
    for r in results:
        key = (r.asignatura, r.docente)
        risk_map = risk_lookup.get(key, {})
        output.append(AsignaturaAnalytics(
            asignatura=r.asignatura, carrera=r.carrera, docente=r.docente,
            nivel=r.nivel, grupo=r.grupo,
            codigo_avac=enr_avac.get(key),
            total_estudiantes=r.total_estudiantes,
            promedio_general=None, nota_maxima=None, nota_minima=None,
            aprobados=0, reprobados=0,
            porcentaje_aprobacion=None, porcentaje_reprobacion=None,
            total_repitentes=r.total_repitentes or 0,
            estudiantes_riesgo_alto=risk_map.get("Alto", 0),
            estudiantes_riesgo_medio=risk_map.get("Medio", 0),
            estudiantes_riesgo_bajo=risk_map.get("Bajo", 0),
            promedio_compromiso=None, total_intervenciones=0,
        ))
    return output


@router.get("/asignaturas", response_model=list[AsignaturaAnalytics])
def get_asignaturas_analytics(
    carrera: Optional[str] = None,
    nivel: Optional[int] = None,
    solo_criticas: bool = False,
    periodo: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Vista agregada por asignatura. Framework §8.2.
    Si no hay grades para el periodo, usa Enrollment como fallback."""
    query = db.query(
        Grade.asignatura, Grade.carrera, Grade.docente, Grade.nivel, Grade.grupo,
        func.count(Grade.id).label("total_estudiantes"),
        func.avg(Grade.nota_final).label("promedio_general"),
        func.max(Grade.nota_final).label("nota_maxima"),
        func.min(Grade.nota_final).label("nota_minima"),
        func.sum(case((Grade.nota_final >= 70, 1), else_=0)).label("aprobados"),
        func.sum(case((and_(Grade.nota_final < 70, Grade.nota_final.isnot(None)), 1), else_=0)).label("reprobados"),
        func.sum(case((Grade.numero_repitencias > 1, 1), else_=0)).label("total_repitentes"),
    )
    query, _ = apply_periodo_filter(query, periodo)
    query = query.group_by(Grade.asignatura, Grade.carrera, Grade.docente, Grade.nivel, Grade.grupo)

    if carrera:
        carrera_student_ids = [s_id for (s_id,) in db.query(Student.id).filter(
            func.lower(Student.carrera).contains(carrera.lower())
        ).all()]
        if carrera_student_ids:
            query = query.filter(Grade.student_id.in_(carrera_student_ids))
        else:
            # Sin grades con esa carrera, intentar enrollment
            return _get_enrollment_results(db, periodo, carrera, nivel)
    if nivel:
        query = query.filter(Grade.nivel == nivel)

    results = query.order_by(Grade.asignatura).all()

    # Fallback a Enrollment si no hay grades
    if not results:
        return _get_enrollment_results(db, periodo, carrera, nivel)

    # Batch: riesgo por asignatura+docente
    risk_batch_q = (
        db.query(Grade.asignatura, Grade.docente, Student.nivel_riesgo, func.count(distinct(Student.id)).label("cnt"))
        .join(Student, Student.id == Grade.student_id)
    )
    risk_batch_q, _ = apply_periodo_filter(risk_batch_q, periodo)
    risk_batch = risk_batch_q.group_by(Grade.asignatura, Grade.docente, Student.nivel_riesgo).all()
    risk_lookup = {}
    for rb in risk_batch:
        key = (rb.asignatura, rb.docente)
        risk_lookup.setdefault(key, {})[rb.nivel_riesgo] = rb.cnt

    # Batch: compromiso
    comp_batch_q = (
        db.query(Grade.asignatura, Grade.docente, func.avg(Student.indice_compromiso).label("avg_comp"))
        .join(Student, Student.id == Grade.student_id)
    )
    comp_batch_q, _ = apply_periodo_filter(comp_batch_q, periodo)
    comp_batch = comp_batch_q.group_by(Grade.asignatura, Grade.docente).all()
    comp_lookup = {(c.asignatura, c.docente): c.avg_comp for c in comp_batch}

    # Batch: intervenciones
    interv_batch = (
        db.query(Intervention.asignatura, func.count(Intervention.id).label("total"))
        .filter(Intervention.asignatura.isnot(None))
        .group_by(Intervention.asignatura).all()
    )
    interv_lookup = {ib.asignatura: ib.total for ib in interv_batch}

    # Batch: codigo_avac from CourseConfig
    cc_avac_rows = db.query(
        CourseConfig.asignatura, CourseConfig.docente, CourseConfig.codigo_avac
    ).filter(CourseConfig.codigo_avac.isnot(None)).all()
    cc_avac_lookup = {}
    for cc in cc_avac_rows:
        if cc.asignatura:
            cc_avac_lookup[(cc.asignatura, cc.docente)] = cc.codigo_avac

    output = []
    for r in results:
        total = r.total_estudiantes or 1
        pct_aprob = round((r.aprobados / total) * 100, 1) if r.aprobados is not None else None
        pct_reprob = round((r.reprobados / total) * 100, 1) if r.reprobados is not None else None
        key = (r.asignatura, r.docente)
        risk_map = risk_lookup.get(key, {})
        avg_comp = comp_lookup.get(key)

        item = AsignaturaAnalytics(
            asignatura=r.asignatura, carrera=r.carrera, docente=r.docente,
            nivel=r.nivel, grupo=r.grupo,
            codigo_avac=cc_avac_lookup.get(key),
            total_estudiantes=r.total_estudiantes,
            promedio_general=round(r.promedio_general, 1) if r.promedio_general else None,
            nota_maxima=r.nota_maxima, nota_minima=r.nota_minima,
            aprobados=r.aprobados or 0, reprobados=r.reprobados or 0,
            porcentaje_aprobacion=pct_aprob, porcentaje_reprobacion=pct_reprob,
            total_repitentes=r.total_repitentes or 0,
            estudiantes_riesgo_alto=risk_map.get("Alto", 0),
            estudiantes_riesgo_medio=risk_map.get("Medio", 0),
            estudiantes_riesgo_bajo=risk_map.get("Bajo", 0),
            promedio_compromiso=round(avg_comp, 2) if avg_comp else None,
            total_intervenciones=interv_lookup.get(r.asignatura, 0),
        )

        if solo_criticas:
            is_critica = (pct_reprob and pct_reprob > 50) or (r.promedio_general and r.promedio_general < 60)
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
    """Detalle de una asignatura: lista de estudiantes con indicadores.
    Si no hay grades, usa Enrollment como fallback."""
    query = db.query(Grade).filter(Grade.asignatura == asignatura)
    query, _ = apply_periodo_filter(query, periodo)
    if docente:
        query = query.filter(Grade.docente == docente)

    grades = query.all()

    if not grades:
        # Fallback: enrollment data
        eq = db.query(Enrollment).filter(Enrollment.asignatura == asignatura)
        eq, _ = _enrollment_periodo_filter(eq, periodo)
        if docente:
            eq = eq.filter(Enrollment.docente == docente)
        enrolls = eq.all()
        if not enrolls:
            return {"asignatura": asignatura, "estudiantes": [], "total_estudiantes": 0}

        student_ids = list(set(e.student_id for e in enrolls))
        students = db.query(Student).filter(Student.id.in_(student_ids)).all()
        student_map = {s.id: s for s in students}
        first_e = enrolls[0]
        estudiantes_out = []
        for e in enrolls:
            s = student_map.get(e.student_id)
            if not s:
                continue
            estudiantes_out.append({
                "student_id": s.id, "nombre": s.nombre,
                "correo_institucional": s.correo_institucional, "cedula": s.cedula,
                "nota_final": None, "numero_repitencias": e.numero_repitencias,
                "nivel_riesgo": s.nivel_riesgo, "indice_compromiso": s.indice_compromiso,
                "dias_sin_acceso": s.dias_sin_acceso, "porcentaje_tareas": s.porcentaje_tareas,
                "estado_matricula": s.estado_matricula or e.estado_matriculado,
                "intervenciones_asignatura": 0,
            })
        estudiantes_out.sort(key=lambda x: (x["nombre"] or ""))
        # codigo_avac from enrollment
        enr_avac = first_e.codigo_grupo if first_e.codigo_grupo else None
        return {
            "asignatura": asignatura, "carrera": first_e.carrera,
            "docente": first_e.docente or docente, "nivel": first_e.nivel,
            "codigo_avac": enr_avac,
            "total_estudiantes": len(estudiantes_out),
            "promedio_general": None,
            "aprobados": 0, "reprobados": 0,
            "porcentaje_aprobacion": None,
            "total_repitentes": sum(1 for e in estudiantes_out if e["numero_repitencias"] and e["numero_repitencias"] > 1),
            "estudiantes": estudiantes_out,
            "fuente": "enrollment",
        }

    student_ids = [g.student_id for g in grades]
    students = db.query(Student).filter(Student.id.in_(student_ids)).all()
    student_map = {s.id: s for s in students}

    interv_counts = dict(
        db.query(Intervention.student_id, func.count(Intervention.id))
        .filter(Intervention.student_id.in_(student_ids), Intervention.asignatura == asignatura)
        .group_by(Intervention.student_id).all()
    )

    estudiantes_out = []
    for g in grades:
        s = student_map.get(g.student_id)
        if not s:
            continue
        estudiantes_out.append({
            "student_id": s.id, "nombre": s.nombre,
            "correo_institucional": s.correo_institucional, "cedula": s.cedula,
            "nota_final": g.nota_final, "numero_repitencias": g.numero_repitencias,
            "nivel_riesgo": s.nivel_riesgo, "indice_compromiso": s.indice_compromiso,
            "dias_sin_acceso": s.dias_sin_acceso, "porcentaje_tareas": s.porcentaje_tareas,
            "estado_matricula": s.estado_matricula,
            "intervenciones_asignatura": interv_counts.get(s.id, 0),
        })

    estudiantes_out.sort(key=lambda x: (x["nota_final"] or 0))
    first_grade = grades[0]
    total = len(estudiantes_out)
    aprobados = sum(1 for e in estudiantes_out if e["nota_final"] and e["nota_final"] >= 70)

    # Lookup codigo_avac from CourseConfig
    cc_avac = db.query(CourseConfig.codigo_avac).filter(
        CourseConfig.asignatura == asignatura,
        CourseConfig.docente == (docente or first_grade.docente),
        CourseConfig.codigo_avac.isnot(None),
    ).first()
    codigo_avac = cc_avac[0] if cc_avac else None

    return {
        "asignatura": asignatura, "carrera": first_grade.carrera,
        "docente": first_grade.docente or docente, "nivel": first_grade.nivel,
        "codigo_avac": codigo_avac,
        "total_estudiantes": total,
        "promedio_general": round(sum(e["nota_final"] or 0 for e in estudiantes_out) / max(total, 1), 1),
        "aprobados": aprobados, "reprobados": total - aprobados,
        "porcentaje_aprobacion": round((aprobados / max(total, 1)) * 100, 1),
        "total_repitentes": sum(1 for e in estudiantes_out if e["numero_repitencias"] and e["numero_repitencias"] > 1),
        "estudiantes": estudiantes_out,
    }
