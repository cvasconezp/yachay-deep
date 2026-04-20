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
    grupos: list[str] = []
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
        return query, pf
    elif pf != "todos":
        if pf.startswith("P"):
            raw = pf[1:]
            query = query.filter(or_(col == pf, col == raw))
        else:
            query = query.filter(or_(col == pf, col == f"P{pf}"))
    return query, pf


def _get_enrollment_results(db: Session, periodo: Optional[str], carrera: Optional[str], nivel: Optional[int]):
    """Genera resultados de asignaturas desde Enrollment (sin calificaciones).
    Agrupa SOLO por (asignatura, docente) para evitar duplicados por variaciones
    en carrera/nivel/grupo. Usa distinct student_id para conteo correcto."""
    query = db.query(
        Enrollment.asignatura, Enrollment.docente,
        func.min(Enrollment.carrera).label("carrera"),
        func.min(Enrollment.nivel).label("nivel"),
        func.count(distinct(Enrollment.student_id)).label("total_estudiantes"),
        func.sum(case((Enrollment.numero_repitencias > 1, 1), else_=0)).label("total_repitentes"),
    )
    query, _ = _enrollment_periodo_filter(query, periodo)
    query = query.group_by(Enrollment.asignatura, Enrollment.docente)

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

    # Lookup codigo_avac + grupos from Enrollment per (asignatura, docente)
    enr_avac = {}
    enr_grupos = {}
    for r in results:
        key = (r.asignatura, r.docente)
        # Get all distinct codigo_grupo values
        codes = db.query(Enrollment.codigo_grupo, Enrollment.nombre_grupo).filter(
            Enrollment.asignatura == r.asignatura,
            Enrollment.docente == r.docente,
            Enrollment.codigo_grupo.isnot(None),
        ).distinct().all()
        if codes:
            enr_avac[key] = codes[0][0]  # first codigo_avac
            # Extract grupo numbers from nombre_grupo
            grupos = set()
            for _, ng in codes:
                if ng:
                    for part in ng.replace("-", " ").split():
                        if part.strip().isdigit():
                            grupos.add(part.strip())
                            break
            enr_grupos[key] = sorted(grupos)

    output = []
    for r in results:
        key = (r.asignatura, r.docente)
        risk_map = risk_lookup.get(key, {})
        output.append(AsignaturaAnalytics(
            asignatura=r.asignatura, carrera=r.carrera, docente=r.docente,
            nivel=r.nivel,
            grupos=enr_grupos.get(key, []),
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
        Grade.asignatura, Grade.docente,
        func.min(Grade.carrera).label("carrera"),
        func.min(Grade.nivel).label("nivel"),
        func.count(distinct(Grade.student_id)).label("total_estudiantes"),
        func.avg(Grade.nota_final).label("promedio_general"),
        func.max(Grade.nota_final).label("nota_maxima"),
        func.min(Grade.nota_final).label("nota_minima"),
        func.sum(case((Grade.nota_final >= 70, 1), else_=0)).label("aprobados"),
        func.sum(case((and_(Grade.nota_final < 70, Grade.nota_final.isnot(None)), 1), else_=0)).label("reprobados"),
        func.sum(case((Grade.numero_repitencias > 1, 1), else_=0)).label("total_repitentes"),
    )
    query, _ = apply_periodo_filter(query, periodo)
    query = query.group_by(Grade.asignatura, Grade.docente)

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

    # Batch: codigo_avac + grupos from CourseConfig
    cc_avac_rows = db.query(
        CourseConfig.asignatura, CourseConfig.docente, CourseConfig.codigo_avac, CourseConfig.grupo
    ).filter(CourseConfig.codigo_avac.isnot(None)).all()
    cc_avac_lookup = {}
    cc_grupos_lookup = {}
    for cc in cc_avac_rows:
        if cc.asignatura:
            key = (cc.asignatura, cc.docente)
            if key not in cc_avac_lookup:
                cc_avac_lookup[key] = cc.codigo_avac
            cc_grupos_lookup.setdefault(key, set())
            if cc.grupo:
                cc_grupos_lookup[key].add(cc.grupo)

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
            nivel=r.nivel,
            grupos=sorted(cc_grupos_lookup.get(key, set())),
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

    def _extract_grupo(nombre_grupo):
        if not nombre_grupo:
            return None
        for part in nombre_grupo.replace("-", " ").split():
            if part.strip().isdigit():
                return part.strip()
        return None

    if not grades:
        # Fallback: enrollment data
        eq = db.query(Enrollment).filter(Enrollment.asignatura == asignatura)
        eq, _ = _enrollment_periodo_filter(eq, periodo)
        if docente:
            eq = eq.filter(Enrollment.docente == docente)
        enrolls = eq.all()
        if not enrolls:
            return {"asignatura": asignatura, "grupos_detalle": [], "total_estudiantes": 0}

        all_sids = list(set(e.student_id for e in enrolls))
        students = db.query(Student).filter(Student.id.in_(all_sids)).all()
        student_map = {s.id: s for s in students}
        first_e = enrolls[0]

        # Group by (codigo_grupo) to separate sections
        grupo_map = {}
        for e in enrolls:
            gkey = e.codigo_grupo or "sin_grupo"
            if gkey not in grupo_map:
                grupo_map[gkey] = {
                    "grupo": _extract_grupo(e.nombre_grupo),
                    "codigo_avac": e.codigo_grupo, "enrolls": [],
                }
            grupo_map[gkey]["enrolls"].append(e)

        grupos_detalle = []
        total_all = 0
        for gkey, data in sorted(grupo_map.items(), key=lambda x: x[1]["grupo"] or ""):
            est_list = []
            seen_sids = set()
            for e in data["enrolls"]:
                if e.student_id in seen_sids:
                    continue
                seen_sids.add(e.student_id)
                s = student_map.get(e.student_id)
                if not s:
                    continue
                est_list.append({
                    "student_id": s.id, "nombre": s.nombre,
                    "correo_institucional": s.correo_institucional, "cedula": s.cedula,
                    "nota_final": None, "numero_repitencias": e.numero_repitencias,
                    "nivel_riesgo": s.nivel_riesgo, "indice_compromiso": s.indice_compromiso,
                    "dias_sin_acceso": s.dias_sin_acceso, "porcentaje_tareas": s.porcentaje_tareas,
                    "estado_matricula": s.estado_matricula or e.estado_matriculado,
                    "intervenciones_asignatura": 0,
                })
            est_list.sort(key=lambda x: (x["nombre"] or ""))
            total_all += len(est_list)
            grupos_detalle.append({
                "grupo": data["grupo"], "codigo_avac": data["codigo_avac"],
                "total_estudiantes": len(est_list),
                "promedio": None, "aprobados": 0, "reprobados": 0,
                "porcentaje_aprobacion": None,
                "riesgo_alto": sum(1 for e in est_list if e["nivel_riesgo"] == "Alto"),
                "estudiantes": est_list,
            })

        return {
            "asignatura": asignatura, "carrera": first_e.carrera,
            "docente": first_e.docente or docente, "nivel": first_e.nivel,
            "total_estudiantes": total_all,
            "promedio_general": None,
            "aprobados": 0, "reprobados": 0,
            "porcentaje_aprobacion": None,
            "total_repitentes": sum(
                sum(1 for e in g["estudiantes"] if e["numero_repitencias"] and e["numero_repitencias"] > 1)
                for g in grupos_detalle),
            "grupos_detalle": grupos_detalle,
            "fuente": "enrollment",
        }

    # --- Grades path ---
    # Lookup CourseConfig for codigo_avac + grupo mapping
    cc_rows = db.query(CourseConfig).filter(
        CourseConfig.asignatura == asignatura,
        CourseConfig.docente == (docente or grades[0].docente),
        CourseConfig.codigo_avac.isnot(None),
    ).all()
    cc_by_grupo = {}
    for cc in cc_rows:
        cc_by_grupo[cc.grupo] = cc.codigo_avac

    all_student_ids = list(set(g.student_id for g in grades))
    students = db.query(Student).filter(Student.id.in_(all_student_ids)).all()
    student_map = {s.id: s for s in students}

    interv_counts = dict(
        db.query(Intervention.student_id, func.count(Intervention.id))
        .filter(Intervention.student_id.in_(all_student_ids), Intervention.asignatura == asignatura)
        .group_by(Intervention.student_id).all()
    )

    # Group grades by grupo
    grupo_map = {}
    for g in grades:
        gkey = g.grupo or "sin_grupo"
        if gkey not in grupo_map:
            grupo_map[gkey] = {
                "grupo": g.grupo,
                "codigo_avac": cc_by_grupo.get(g.grupo),
                "grades": [],
            }
        grupo_map[gkey]["grades"].append(g)

    grupos_detalle = []
    total_all = 0
    total_aprobados_all = 0
    sum_notas_all = 0
    count_notas_all = 0

    for gkey, data in sorted(grupo_map.items(), key=lambda x: x[1]["grupo"] or ""):
        gs = data["grades"]
        notas = [g.nota_final for g in gs if g.nota_final is not None]
        est_list = []
        seen_sids = set()
        for g in gs:
            if g.student_id in seen_sids:
                continue
            seen_sids.add(g.student_id)
            s = student_map.get(g.student_id)
            if not s:
                continue
            est_list.append({
                "student_id": s.id, "nombre": s.nombre,
                "correo_institucional": s.correo_institucional, "cedula": s.cedula,
                "nota_final": g.nota_final, "numero_repitencias": g.numero_repitencias,
                "nivel_riesgo": s.nivel_riesgo, "indice_compromiso": s.indice_compromiso,
                "dias_sin_acceso": s.dias_sin_acceso, "porcentaje_tareas": s.porcentaje_tareas,
                "estado_matricula": s.estado_matricula,
                "intervenciones_asignatura": interv_counts.get(s.id, 0),
            })
        est_list.sort(key=lambda x: (x["nota_final"] or 0))
        aprobados = sum(1 for n in notas if n >= 70)
        total = len(notas) if notas else 1
        total_all += len(est_list)
        total_aprobados_all += aprobados
        sum_notas_all += sum(notas)
        count_notas_all += len(notas)

        grupos_detalle.append({
            "grupo": data["grupo"], "codigo_avac": data.get("codigo_avac"),
            "total_estudiantes": len(est_list),
            "promedio": round(sum(notas) / max(total, 1), 1) if notas else None,
            "aprobados": aprobados, "reprobados": len(notas) - aprobados,
            "porcentaje_aprobacion": round((aprobados / max(total, 1)) * 100, 1),
            "riesgo_alto": sum(1 for e in est_list if e["nivel_riesgo"] == "Alto"),
            "estudiantes": est_list,
        })

    first_grade = grades[0]
    return {
        "asignatura": asignatura, "carrera": first_grade.carrera,
        "docente": first_grade.docente or docente, "nivel": first_grade.nivel,
        "total_estudiantes": total_all,
        "promedio_general": round(sum_notas_all / max(count_notas_all, 1), 1) if count_notas_all else None,
        "aprobados": total_aprobados_all,
        "reprobados": count_notas_all - total_aprobados_all,
        "porcentaje_aprobacion": round((total_aprobados_all / max(count_notas_all, 1)) * 100, 1) if count_notas_all else None,
        "total_repitentes": sum(
            sum(1 for e in g["estudiantes"] if e["numero_repitencias"] and e["numero_repitencias"] > 1)
            for g in grupos_detalle),
        "grupos_detalle": grupos_detalle,
    }
