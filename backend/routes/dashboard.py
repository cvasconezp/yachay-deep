"""
Dashboard de riesgo — equivalente a la hoja EstudiantesEnRiesgo del Excel.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from pydantic import BaseModel

from sqlalchemy import distinct as sa_distinct

from ..database import get_db
from ..models import Student, Intervention, Grade, AvacAccess
from ..models.enrollment import Enrollment
from ..models.course_config import SemesterConfig, CourseConfig
from ..auth.jwt import get_current_user
from ..models.user import User
from ..services.retiro import filtrar_activos


def _active_bloque_courses(db: Session, semconfig) -> set[str] | None:
    """Retorna set de codigo_avac que NO son del bloque contrario, o None si no hay filtro.

    Lógica: en lugar de whitelist (solo cursos configurados), usamos blacklist
    (excluir cursos explícitamente marcados como bloque contrario).
    Así, cursos en AvacAccess que no están en course_configs no se excluyen.
    """
    if not semconfig:
        return None
    bloque = semconfig.bloque_actual  # "1" o "2"
    other_bloque = "2" if bloque == "1" else "1"
    # Obtener códigos explícitamente del otro bloque (excluir estos)
    excluded = set()
    for cc in db.query(CourseConfig.codigo_avac).filter(
        CourseConfig.bloque == other_bloque,
    ).all():
        excluded.add(cc[0])
    return excluded if excluded else None


def _apply_bloque_filter(query, excluded_courses):
    """Aplica filtro de bloque: excluir cursos del bloque contrario."""
    if excluded_courses:
        return query.filter(~AvacAccess.codigo_curso.in_(excluded_courses))
    return query


def _period_student_ids(db: Session, periodo: Optional[str]):
    """Subquery de student_ids filtrados por período (Grades + Enrollments + AvacAccess).

    Para AvacAccess siempre incluye periodo=NULL como fallback (registros
    cargados antes de configurar semestre).
    """
    from sqlalchemy import or_
    pf = periodo if periodo else "actual"

    grade_sq = db.query(Grade.student_id).distinct()
    enroll_sq = db.query(Enrollment.student_id).distinct()
    avac_sq = db.query(AvacAccess.student_id).filter(AvacAccess.student_id.isnot(None)).distinct()

    if pf == "actual":
        grade_sq = grade_sq.filter(Grade.periodo.is_(None))
        enroll_sq = enroll_sq.filter(Enrollment.periodo.is_(None))
        avac_sq = avac_sq.filter(AvacAccess.periodo.is_(None))
    elif pf != "todos":
        # Dual format: "P68" <-> "68"
        if pf.startswith("P"):
            grade_sq = grade_sq.filter(or_(Grade.periodo == pf, Grade.periodo == pf[1:]))
            enroll_sq = enroll_sq.filter(or_(Enrollment.periodo == pf, Enrollment.periodo == pf[1:]))
            avac_sq = avac_sq.filter(or_(
                AvacAccess.periodo == pf, AvacAccess.periodo == pf[1:],
                AvacAccess.periodo.is_(None),
            ))
        else:
            grade_sq = grade_sq.filter(or_(Grade.periodo == pf, Grade.periodo == f"P{pf}"))
            enroll_sq = enroll_sq.filter(or_(Enrollment.periodo == pf, Enrollment.periodo == f"P{pf}"))
            avac_sq = avac_sq.filter(or_(
                AvacAccess.periodo == pf, AvacAccess.periodo == f"P{pf}",
                AvacAccess.periodo.is_(None),
            ))

    sq = grade_sq.union(enroll_sq).union(avac_sq)
    return sq, pf


def _period_has_data(db: Session, periodo: Optional[str]) -> bool:
    """Verifica si existen datos (calificaciones O accesos AVAC) para el período dado."""
    from sqlalchemy import or_
    pf = periodo if periodo else "actual"

    # Check grades
    q_grades = db.query(Grade.id)
    q_avac = db.query(AvacAccess.id).filter(AvacAccess.student_id.isnot(None))

    if pf == "actual":
        q_grades = q_grades.filter(Grade.periodo.is_(None))
        q_avac = q_avac.filter(AvacAccess.periodo.is_(None))
    elif pf == "todos":
        return True
    else:
        if pf.startswith("P"):
            q_grades = q_grades.filter(or_(Grade.periodo == pf, Grade.periodo == pf[1:]))
            q_avac = q_avac.filter(or_(
                AvacAccess.periodo == pf, AvacAccess.periodo == pf[1:],
                AvacAccess.periodo.is_(None),
            ))
        else:
            q_grades = q_grades.filter(or_(Grade.periodo == pf, Grade.periodo == f"P{pf}"))
            q_avac = q_avac.filter(or_(
                AvacAccess.periodo == pf, AvacAccess.periodo == f"P{pf}",
                AvacAccess.periodo.is_(None),
            ))

    return q_grades.limit(1).first() is not None or q_avac.limit(1).first() is not None

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class RiskStudentOut(BaseModel):
    id: int
    nombre: str
    correo_institucional: Optional[str]
    cedula: Optional[str]
    carrera: Optional[str]
    nivel_riesgo: Optional[str]
    indice_compromiso: Optional[float]
    dias_sin_acceso: Optional[int]
    porcentaje_tareas: Optional[float]
    promedio_calificaciones: Optional[float]
    estado_matricula: Optional[str]
    prob_desercion: Optional[float] = None
    prob_reprobacion: Optional[float] = None
    es_tercera_matricula: bool = False
    total_intervenciones: int
    ultima_intervencion: Optional[str]

    class Config:
        from_attributes = True


@router.get("/risk", response_model=list[RiskStudentOut])
def get_risk_dashboard(
    carrera: Optional[str] = None,
    nivel_riesgo: Optional[str] = None,
    solo_sin_intervencion: bool = False,
    periodo: Optional[str] = None,
    asignatura: Optional[str] = None,
    tercera_matricula: Optional[bool] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(500, le=2500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lista de estudiantes en riesgo con sus indicadores.
    Equivalente a EstudiantesEnRiesgo, pero filtrable y paginada.
    """
    from datetime import datetime, timezone
    from sqlalchemy import or_

    # ── Capear dias_sin_acceso al inicio del bloque actual ──────────────
    semconfig = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    max_dias_periodo = None
    if semconfig:
        bloque_inicio = None
        if semconfig.bloque_actual == "2" and semconfig.bloque2_inicio:
            bloque_inicio = semconfig.bloque2_inicio
        elif semconfig.bloque1_inicio:
            bloque_inicio = semconfig.bloque1_inicio
        if bloque_inicio:
            if bloque_inicio.tzinfo is None:
                bloque_inicio = bloque_inicio.replace(tzinfo=timezone.utc)
            max_dias_periodo = (datetime.now(timezone.utc) - bloque_inicio).days

    # Determinar variantes de periodo para AvacAccess
    _, pf = _period_student_ids(db, periodo)
    # "actual" no matchea en AvacAccess — resolver al semestre activo real
    if pf == "actual" and semconfig:
        pf = semconfig.semestre
    if pf.startswith("P"):
        periodo_variants = (pf, pf[1:])
    else:
        periodo_variants = (pf, f"P{pf}")

    # Excluir cursos del bloque contrario (ej: excluir bloque 2 si estamos en bloque 1)
    excluded_courses = _active_bloque_courses(db, semconfig)

    # Pre-load per-period AvacAccess: max dias_sin_acceso por estudiante
    avac_q = db.query(
        AvacAccess.student_id,
        func.max(AvacAccess.dias_sin_acceso),
    ).filter(
        AvacAccess.student_id.isnot(None),
        AvacAccess.dias_sin_acceso.isnot(None),
    )
    if pf != "todos":
        from sqlalchemy import or_ as _or
        avac_q = avac_q.filter(_or(
            AvacAccess.periodo.in_(periodo_variants),
            AvacAccess.periodo.is_(None),
        ))
    avac_q = _apply_bloque_filter(avac_q, excluded_courses)
    avac_inactividad = dict(avac_q.group_by(AvacAccess.student_id).all())

    # Subquery: contar intervenciones y última intervención por estudiante
    interv_sq = (
        db.query(
            Intervention.student_id,
            func.count(Intervention.id).label("total_intervenciones"),
            func.max(Intervention.created_at).label("ultima_intervencion"),
        )
        .group_by(Intervention.student_id)
        .subquery()
    )

    query = (
        db.query(Student, interv_sq.c.total_intervenciones, interv_sq.c.ultima_intervencion)
        .outerjoin(interv_sq, Student.id == interv_sq.c.student_id)
        .filter(Student.nivel_riesgo.isnot(None))
    )

    # Filtrar por período: solo estudiantes que tienen calificaciones en ese período
    period_sq, _ = _period_student_ids(db, periodo)
    query = query.filter(Student.id.in_(period_sq))

    if carrera:
        query = query.filter(func.lower(Student.carrera).contains(carrera.lower()))
    if asignatura:
        # Filtrar: solo estudiantes que tienen AvacAccess en cursos de esa asignatura
        asig_codes = [r[0] for r in db.query(CourseConfig.codigo_avac).filter(
            func.lower(CourseConfig.asignatura).contains(asignatura.lower()),
        ).all()]
        if asig_codes:
            asig_students = db.query(AvacAccess.student_id).filter(
                AvacAccess.codigo_curso.in_(asig_codes),
                AvacAccess.student_id.isnot(None),
            ).distinct()
            query = query.filter(Student.id.in_(asig_students))
        else:
            return []  # no matching courses
    if nivel_riesgo:
        query = query.filter(Student.nivel_riesgo == nivel_riesgo)
    if solo_sin_intervencion:
        query = query.filter(interv_sq.c.total_intervenciones.is_(None))
    if tercera_matricula is not None:
        query = query.filter(Student.es_tercera_matricula == tercera_matricula)

    # Ordenar: de más urgente a menos. "Sin riesgo" al final, que es el punto de tenerlo.
    risk_order = case(
        (Student.nivel_riesgo == "Alto", 0),
        (Student.nivel_riesgo == "Medio", 1),
        (Student.nivel_riesgo == "Bajo", 2),
        (Student.nivel_riesgo == "Sin riesgo", 3),
        else_=4,
    )
    results = (
        query
        .order_by(
            risk_order,
            Student.dias_sin_acceso.desc().nullslast(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    output = []
    for student, total_interv, ultima_interv in results:
        # Usar dias_sin_acceso del periodo (AvacAccess), capeado al inicio del bloque
        dias = avac_inactividad.get(student.id)
        if dias is None:
            dias = student.dias_sin_acceso  # fallback al global
        if dias is not None and max_dias_periodo is not None:
            dias = min(dias, max_dias_periodo)
        if dias is not None:
            dias = int(dias)

        output.append(RiskStudentOut(
            id=student.id,
            nombre=student.nombre,
            correo_institucional=student.correo_institucional,
            cedula=student.cedula,
            carrera=student.carrera,
            nivel_riesgo=student.nivel_riesgo,
            indice_compromiso=student.indice_compromiso,
            dias_sin_acceso=dias,
            porcentaje_tareas=student.porcentaje_tareas,
            promedio_calificaciones=student.promedio_calificaciones,
            estado_matricula=student.estado_matricula,
            prob_desercion=student.prob_desercion,
            prob_reprobacion=student.prob_reprobacion,
            es_tercera_matricula=student.es_tercera_matricula or False,
            total_intervenciones=total_interv or 0,
            ultima_intervencion=ultima_interv.isoformat() if ultima_interv else None,
        ))
    return output


class CourseInactivityOut(BaseModel):
    codigo_curso: str
    asignatura: Optional[str] = None
    dias_sin_acceso: int
    ultimo_acceso_texto: Optional[str] = None
    estado_avac: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/risk/{student_id}/inactividad", response_model=list[CourseInactivityOut])
def get_student_inactivity_by_course(
    student_id: int,
    periodo: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Desglose de inactividad por asignatura para un estudiante."""
    from datetime import datetime, timezone
    from ..models.course_config import CourseConfig

    # Resolver periodo
    semconfig = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    pf = periodo if periodo else (semconfig.semestre if semconfig else None)
    if not pf:
        return []

    if pf.startswith("P"):
        periodo_variants = (pf, pf[1:])
    else:
        periodo_variants = (pf, f"P{pf}")

    # Tope de días desde el inicio del bloque — misma fuente que el ETL y las alertas.
    # Estaba duplicado en tres sitios con lógicas distintas: por eso Dashboard y Ficha
    # mostraban números diferentes del mismo estudiante.
    from ..services.bloques import dias_maximos_del_bloque
    max_dias_periodo = dias_maximos_del_bloque(semconfig)

    # Excluir cursos del bloque contrario
    excluded_courses = _active_bloque_courses(db, semconfig)

    # Incluir periodo NULL como fallback (datos cargados antes de configurar periodo)
    from sqlalchemy import or_
    periodo_filter = or_(
        AvacAccess.periodo.in_(periodo_variants),
        AvacAccess.periodo.is_(None),
    )

    # Último snapshot por curso para este estudiante en el periodo
    latest_snap = (
        db.query(func.max(AvacAccess.snapshot_date))
        .filter(
            AvacAccess.student_id == student_id,
            periodo_filter,
        )
        .scalar()
    )

    records = (
        db.query(AvacAccess)
        .filter(
            AvacAccess.student_id == student_id,
            periodo_filter,
            AvacAccess.dias_sin_acceso.isnot(None),
        )
    )
    records = _apply_bloque_filter(records, excluded_courses)
    if latest_snap:
        records = records.filter(AvacAccess.snapshot_date == latest_snap)

    records = records.order_by(AvacAccess.dias_sin_acceso.desc()).all()

    # Dedup por ASIGNATURA, no por código de curso.
    #
    # Una misma asignatura puede tener varios códigos AVAC para el mismo estudiante
    # (cambio de grupo: AVAC lo sigue listando en el aula vieja, que nunca vuelve a pisar).
    # Deduplicando solo por codigo_curso, "PANADERÍA BÁSICA" salía dos veces: una con 2
    # días (el aula real) y otra con 99 (el aula fantasma). Se conserva el acceso MÁS
    # RECIENTE: si entró hace 2 días a esa asignatura, decir que lleva 99 sin entrar es falso.
    seen_asig = {}
    output = []
    for r in records:
        cc = db.query(CourseConfig).filter(CourseConfig.codigo_avac == r.codigo_curso).first()
        asignatura = cc.asignatura if cc else None

        dias = int(r.dias_sin_acceso)
        if max_dias_periodo is not None:
            dias = min(dias, max_dias_periodo)

        item = CourseInactivityOut(
            codigo_curso=r.codigo_curso,
            asignatura=asignatura,
            dias_sin_acceso=dias,
            ultimo_acceso_texto=r.ultimo_acceso_texto,
            estado_avac=r.estado_avac,
        )

        clave = (asignatura or "").strip().upper() or f"__cod__{r.codigo_curso}"
        anterior = seen_asig.get(clave)
        if anterior is None:
            seen_asig[clave] = item
            output.append(item)
        elif dias < anterior.dias_sin_acceso:
            # Gana el acceso más reciente: sustituye al aula abandonada
            output[output.index(anterior)] = item
            seen_asig[clave] = item

    output.sort(key=lambda x: x.dias_sin_acceso, reverse=True)
    return output


@router.get("/stats")
def get_stats(
    periodo: Optional[str] = None,
    carrera: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resumen institucional: totales por riesgo, carreras, aulas virtuales, etc."""
    from sqlalchemy import or_ as _or

    period_sq, pf = _period_student_ids(db, periodo)
    # Los retirados falsean todo KPI: sus días sin acceso siguen creciendo
    # mecánicamente y nunca van a mejorar. Se consultan en /students/retirados.
    base = filtrar_activos(db.query(Student).filter(Student.id.in_(period_sq)))

    if carrera:
        base = base.filter(func.lower(Student.carrera).contains(carrera.lower()))

    total = base.count()
    por_riesgo = (
        base.with_entities(Student.nivel_riesgo, func.count(Student.id).label("total"))
        .filter(Student.nivel_riesgo.isnot(None))
        .group_by(Student.nivel_riesgo)
        .all()
    )
    por_carrera = (
        base.with_entities(Student.carrera, func.count(Student.id).label("total"))
        .filter(Student.carrera.isnot(None))
        .group_by(Student.carrera)
        .order_by(func.count(Student.id).desc())
        .limit(20)
        .all()
    )
    total_intervenciones = db.query(func.count(Intervention.id)).scalar()
    estudiantes_intervenidos = db.query(func.count(func.distinct(Intervention.student_id))).scalar()

    # ── Aulas virtuales: contar código_curso distintos para el periodo ──
    semconfig = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    # Resolver periodo para AvacAccess
    avac_pf = pf
    if avac_pf == "actual" and semconfig:
        avac_pf = semconfig.semestre or "actual"
    if avac_pf in ("actual", "todos"):
        periodo_variants = None  # no filtrar por periodo
    elif avac_pf.startswith("P"):
        periodo_variants = (avac_pf, avac_pf[1:])
    else:
        periodo_variants = (avac_pf, f"P{avac_pf}")

    aulas_q = db.query(func.count(sa_distinct(AvacAccess.codigo_curso))).filter(
        AvacAccess.codigo_curso.isnot(None),
    )
    if periodo_variants:
        aulas_q = aulas_q.filter(_or(
            AvacAccess.periodo.in_(periodo_variants),
            AvacAccess.periodo.is_(None),
        ))
    # Filtrar por carrera: solo cursos de esa carrera via CourseConfig
    if carrera:
        carrera_codes = [r[0] for r in db.query(CourseConfig.codigo_avac).filter(
            func.lower(CourseConfig.carrera).contains(carrera.lower()),
        ).all()]
        if carrera_codes:
            aulas_q = aulas_q.filter(AvacAccess.codigo_curso.in_(carrera_codes))
        else:
            aulas_q = aulas_q.filter(AvacAccess.codigo_curso == "__NO_MATCH__")
    # Excluir cursos del bloque contrario
    excluded_courses = _active_bloque_courses(db, semconfig)
    if excluded_courses:
        aulas_q = aulas_q.filter(~AvacAccess.codigo_curso.in_(excluded_courses))

    total_aulas_virtuales = aulas_q.scalar() or 0

    # Detectar si hay datos reales (grades o accesos AVAC) para el periodo
    has_data = _period_has_data(db, periodo)

    # ── Repitentes: estudiantes con numero_repitencias > 1 ──
    from .analytics._helpers import apply_periodo_filter as _apf
    rep_grade_q = db.query(Grade.student_id).filter(Grade.numero_repitencias > 1).distinct()
    rep_grade_q, _ = _apf(rep_grade_q, periodo)
    rep_enroll_q = db.query(Enrollment.student_id).filter(Enrollment.numero_repitencias > 1).distinct()
    rep_enroll_q, _ = _apf(rep_enroll_q, periodo, column=Enrollment.periodo)
    rep_sids = set(r[0] for r in rep_grade_q.union(rep_enroll_q).all())
    # Intersect with period students
    period_sids = set(r[0] for r in period_sq.all())
    rep_sids &= period_sids
    if carrera:
        carrera_sids = set(s_id for (s_id,) in db.query(Student.id).filter(
            func.lower(Student.carrera).contains(carrera.lower())).all())
        rep_sids &= carrera_sids
    total_repitentes = len(rep_sids)

    # ── Terceras matrículas (oyentes condicionados) ──
    tm_q = base.filter(Student.es_tercera_matricula == True)
    total_terceras_matriculas = tm_q.count()

    return {
        "total_estudiantes": total,
        "por_nivel_riesgo": [{"nivel": r.nivel_riesgo, "total": r.total} for r in por_riesgo],
        "por_carrera": [{"carrera": r.carrera, "total": r.total} for r in por_carrera],
        "total_intervenciones": total_intervenciones,
        "estudiantes_intervenidos": estudiantes_intervenidos,
        "total_aulas_virtuales": total_aulas_virtuales,
        "total_repitentes": total_repitentes,
        "total_terceras_matriculas": total_terceras_matriculas,
        "tiene_datos_periodo": has_data,
    }


@router.get("/carreras")
def get_carreras(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista única de carreras para filtros del dashboard."""
    carreras = (
        db.query(Student.carrera)
        .filter(Student.carrera.isnot(None), Student.carrera != "")
        .distinct()
        .order_by(Student.carrera)
        .all()
    )
    return [c.carrera for c in carreras]


@router.get("/asignaturas")
def get_asignaturas(
    carrera: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista única de asignaturas, opcionalmente filtradas por carrera."""
    q = db.query(CourseConfig.asignatura).filter(
        CourseConfig.asignatura.isnot(None),
        CourseConfig.asignatura != "",
        CourseConfig.activo == True,
    )
    if carrera:
        q = q.filter(func.lower(CourseConfig.carrera).contains(carrera.lower()))
    return [r[0] for r in q.distinct().order_by(CourseConfig.asignatura).all()]


# ── Seguimiento docente: tareas pendientes de calificación ─────────────────

class DocenteGradingSummary(BaseModel):
    docente: Optional[str] = None
    correo_docente: Optional[str] = None
    codigo_curso: str
    asignatura: Optional[str] = None
    carrera: Optional[str] = None
    total_tareas: int = 0
    calificadas: int = 0
    pendientes: int = 0
    pct_calificadas: Optional[float] = None
    estudiantes_afectados: int = 0
    snapshot_date: Optional[str] = None


@router.get("/docentes/calificacion", response_model=list[DocenteGradingSummary])
def get_docente_grading_status(
    periodo: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Estado de calificación por docente/curso — identifica docentes con tareas sin calificar.

    Útil para seguimiento institucional: ¿qué docentes aún no califican actividades?
    """
    from sqlalchemy import or_
    from ..models import TaskSubmission
    from ..models.course_config import SemesterConfig, CourseConfig

    # Determinar periodo
    active_sem = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    active_periodo = active_sem.semestre if active_sem else None

    req_p = periodo if periodo else active_periodo
    if not req_p:
        return []

    raw_p = req_p[1:] if req_p.startswith("P") else req_p

    # Obtener último snapshot
    latest_snap = (
        db.query(func.max(TaskSubmission.snapshot_date))
        .filter(or_(TaskSubmission.periodo == req_p, TaskSubmission.periodo == raw_p))
        .scalar()
    )
    if not latest_snap:
        # Fallback: buscar registros sin snapshot_date (legacy)
        latest_snap = None

    snap_filter = (
        or_(TaskSubmission.snapshot_date == latest_snap, TaskSubmission.snapshot_date.is_(None))
        if latest_snap else TaskSubmission.snapshot_date.is_(None)
    )

    # Agrupar por codigo_curso
    from collections import defaultdict
    tareas = (
        db.query(TaskSubmission)
        .filter(
            or_(TaskSubmission.periodo == req_p, TaskSubmission.periodo == raw_p),
            snap_filter,
        )
        .all()
    )

    curso_data = defaultdict(lambda: {"tasks": [], "students": set()})
    for t in tareas:
        curso_data[t.codigo_curso]["tasks"].append(t)
        curso_data[t.codigo_curso]["students"].add(t.student_id)

    result = []
    for codigo, data in curso_data.items():
        cc = db.query(CourseConfig).filter(CourseConfig.codigo_avac == codigo).first()
        tasks = data["tasks"]
        total = len(tasks)
        calificadas = sum(1 for t in tasks if t.calificada)
        pendientes = total - calificadas

        result.append(DocenteGradingSummary(
            docente=cc.docente if cc else None,
            correo_docente=cc.correo_docente if cc else None,
            codigo_curso=codigo,
            asignatura=cc.asignatura if cc else None,
            carrera=cc.carrera if cc else None,
            total_tareas=total,
            calificadas=calificadas,
            pendientes=pendientes,
            pct_calificadas=round(calificadas / total * 100, 1) if total else None,
            estudiantes_afectados=len(data["students"]),
            snapshot_date=str(latest_snap) if latest_snap else None,
        ))

    # Ordenar: más pendientes primero
    result.sort(key=lambda x: x.pendientes, reverse=True)
    return result
