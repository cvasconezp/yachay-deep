"""
Generador de alertas reutilizable — lógica extraída del endpoint POST /alerts/generate.

Permite ejecutar la generación de alertas tanto desde el endpoint manual
como automáticamente al final del pipeline ETL.

[Épica 1.1] Pipeline Post-ETL Automático
"""
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from ..models import Student, Grade, AvacAccess, TaskSubmission
from ..models.enrollment import Enrollment
from ..models.alert_event import AlertEvent
from ..models.course_config import SemesterConfig, CourseConfig

logger = logging.getLogger(__name__)


def _get_umbrales(db: Session) -> dict:
    """Carga umbrales académicos desde SemesterConfig activo."""
    from ..routes.analytics._helpers import get_umbrales
    return get_umbrales(db)


def _active_period_student_ids(db: Session) -> set:
    """Retorna set de student_ids para el periodo activo."""
    sem = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    if not sem or not sem.semestre:
        return set()
    pf = sem.semestre.strip()

    if pf.startswith("P"):
        raw = pf[1:]
        g_cond = or_(Grade.periodo == pf, Grade.periodo == raw, Grade.periodo.is_(None))
        e_cond = or_(Enrollment.periodo == pf, Enrollment.periodo == raw)
        a_cond = or_(AvacAccess.periodo == pf, AvacAccess.periodo == raw, AvacAccess.periodo.is_(None))
    else:
        g_cond = or_(Grade.periodo == pf, Grade.periodo == f"P{pf}", Grade.periodo.is_(None))
        e_cond = or_(Enrollment.periodo == pf, Enrollment.periodo == f"P{pf}")
        a_cond = or_(AvacAccess.periodo == pf, AvacAccess.periodo == f"P{pf}", AvacAccess.periodo.is_(None))

    grade_ids = {r[0] for r in db.query(Grade.student_id).filter(g_cond).distinct().all()}
    enroll_ids = {r[0] for r in db.query(Enrollment.student_id).filter(e_cond).distinct().all()}
    avac_ids = {r[0] for r in db.query(AvacAccess.student_id).filter(a_cond, AvacAccess.student_id.isnot(None)).distinct().all()}
    return grade_ids | enroll_ids | avac_ids


def _get_calendario(semconfig) -> list[dict]:
    """Parsea el calendario_academico JSON de SemesterConfig."""
    if not semconfig or not semconfig.calendario_academico:
        return []
    try:
        return json.loads(semconfig.calendario_academico)
    except (json.JSONDecodeError, TypeError):
        return []


def _primera_fecha_notas(calendario: list[dict]) -> Optional[datetime]:
    """Retorna la fecha más temprana en que se esperan notas."""
    entregas = [e for e in calendario if e.get("tipo") in ("entrega", "paso_notas")]
    if not entregas:
        return None
    fechas = []
    for e in entregas:
        try:
            d = datetime.strptime(e["fecha"], "%Y-%m-%d")
            if e.get("tipo") == "entrega":
                d = d + timedelta(days=7)
            fechas.append(d)
        except (ValueError, KeyError):
            continue
    return min(fechas) if fechas else None


def generate_alerts_batch(db: Session) -> dict:
    """
    Genera alertas barriendo todos los estudiantes por umbrales.

    Función reutilizable que puede ser llamada desde:
    - El endpoint POST /alerts/generate (manual por admin)
    - El pipeline ETL run_full() (automático post-ETL)

    Retorna dict con: created, cleaned, timestamp, detail
    """
    # ── Full-refresh: eliminar TODAS las alertas auto-generadas antes de regenerar ──
    # Esto evita duplicados cuando el mismo estudiante tiene la misma condición
    # en múltiples ejecuciones. Las alertas se regeneran si la condición persiste.
    stale_deleted = db.query(AlertEvent).delete()
    db.flush()

    # Obtener configuración del semestre activo
    semconfig = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    if not semconfig:
        return {"created": 0, "cleaned": stale_deleted,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "detail": "No hay semestre activo"}

    pf = semconfig.semestre.strip() if semconfig.semestre else None
    if not pf:
        return {"created": 0, "cleaned": stale_deleted,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "detail": "Semestre sin nombre"}

    # Cargar umbrales configurables
    umbrales = _get_umbrales(db)
    umbral_dias_inactividad = umbrales["dias_inactividad"]
    umbral_dias_inactividad_alto = umbral_dias_inactividad + 7
    umbral_tareas = umbrales["tareas_minimo"]
    umbral_compromiso = umbrales["compromiso_minimo"]
    umbral_compromiso_alto = umbral_compromiso * 0.6

    # Determinar inicio del bloque actual
    bloque_inicio = None
    if semconfig.bloque_actual == "2" and semconfig.bloque2_inicio:
        bloque_inicio = semconfig.bloque2_inicio
    elif semconfig.bloque1_inicio:
        bloque_inicio = semconfig.bloque1_inicio

    now = datetime.now(timezone.utc)
    max_dias_periodo = None
    if bloque_inicio:
        if bloque_inicio.tzinfo is None:
            from datetime import timezone as tz
            bloque_inicio = bloque_inicio.replace(tzinfo=tz.utc)
        max_dias_periodo = (now - bloque_inicio).days

    # Calendario académico: ¿ya se esperan notas?
    calendario = _get_calendario(semconfig)
    fecha_notas = _primera_fecha_notas(calendario)
    hay_notas_esperadas = fecha_notas is not None and now >= fecha_notas.replace(tzinfo=timezone.utc)

    # Period format normalization
    if pf.startswith("P"):
        raw_p = pf[1:]
        periodo_variants = (pf, raw_p)
    else:
        raw_p = pf
        periodo_variants = (pf, f"P{pf}")

    period_sids = _active_period_student_ids(db)
    if period_sids:
        students = db.query(Student).filter(Student.id.in_(period_sids)).all()
    else:
        students = db.query(Student).all()

    # Filtrar cursos por bloque actual
    excluded_course_codes = set()
    included_course_codes = set()
    if semconfig:
        other_bloque = "2" if semconfig.bloque_actual == "1" else "1"
        excluded_cc = db.query(CourseConfig.codigo_avac).filter(
            CourseConfig.bloque == other_bloque,
        ).all()
        excluded_course_codes = {r[0] for r in excluded_cc}
        included_cc = db.query(CourseConfig.codigo_avac).filter(
            or_(CourseConfig.bloque == semconfig.bloque_actual,
                CourseConfig.bloque == "ambos",
                CourseConfig.bloque.is_(None)),
        ).all()
        included_course_codes = {r[0] for r in included_cc}

    included_asignaturas = set()
    if included_course_codes:
        for cc in db.query(CourseConfig.asignatura).filter(
            CourseConfig.codigo_avac.in_(included_course_codes),
            CourseConfig.asignatura.isnot(None),
        ).distinct().all():
            included_asignaturas.add(cc[0])

    # Estudiantes del bloque actual
    bloque_actual_sids = set()
    if included_course_codes:
        bloque_avac_sids = set(r[0] for r in db.query(AvacAccess.student_id).filter(
            AvacAccess.codigo_curso.in_(included_course_codes),
            AvacAccess.student_id.isnot(None),
        ).distinct().all())
        bloque_enroll_sids = set(r[0] for r in db.query(Enrollment.student_id).filter(
            Enrollment.codigo_grupo.in_(included_course_codes),
            or_(Enrollment.periodo == periodo_variants[0], Enrollment.periodo == periodo_variants[1]),
        ).distinct().all())
        bloque_actual_sids = bloque_avac_sids | bloque_enroll_sids

    # Pre-load AvacAccess
    periodo_filter = or_(
        AvacAccess.periodo.in_(periodo_variants),
        AvacAccess.periodo.is_(None),
    )
    latest_snap = (
        db.query(func.max(AvacAccess.snapshot_date))
        .filter(periodo_filter, AvacAccess.student_id.isnot(None))
        .scalar()
    )
    avac_q = db.query(
        AvacAccess.student_id, AvacAccess.codigo_curso, AvacAccess.dias_sin_acceso,
    ).filter(
        periodo_filter, AvacAccess.student_id.isnot(None), AvacAccess.dias_sin_acceso.isnot(None),
    )
    if latest_snap:
        avac_q = avac_q.filter(AvacAccess.snapshot_date == latest_snap)
    if excluded_course_codes:
        avac_q = avac_q.filter(~AvacAccess.codigo_curso.in_(excluded_course_codes))

    avac_por_curso = defaultdict(list)
    for sid, codigo, dias in avac_q.all():
        avac_por_curso[sid].append((codigo, dias))

    # Pre-load asignatura names
    all_codes = {codigo for entries in avac_por_curso.values() for codigo, _ in entries}
    asignatura_map = {}
    if all_codes:
        for cc in db.query(CourseConfig).filter(CourseConfig.codigo_avac.in_(all_codes)).all():
            asignatura_map[cc.codigo_avac] = cc.asignatura

    # ========== PRE-CARGA BATCH ==========
    periodo_cond = or_(
        Enrollment.periodo == periodo_variants[0],
        Enrollment.periodo == periodo_variants[1],
    )
    grade_periodo_cond = or_(
        Grade.periodo == periodo_variants[0],
        Grade.periodo == periodo_variants[1],
    )

    # Nota cero
    nota_cero_map = {}
    if hay_notas_esperadas:
        nota_cero_q = db.query(Grade).filter(Grade.nota_final == 0, grade_periodo_cond)
        if included_asignaturas:
            nota_cero_q = nota_cero_q.filter(Grade.asignatura.in_(included_asignaturas))
        for g in nota_cero_q.all():
            if g.student_id not in nota_cero_map:
                nota_cero_map[g.student_id] = g.asignatura

    # Tareas
    task_q = db.query(TaskSubmission.student_id).filter(
        or_(TaskSubmission.periodo == periodo_variants[0], TaskSubmission.periodo == periodo_variants[1]),
    )
    if included_course_codes:
        task_q = task_q.filter(TaskSubmission.codigo_curso.in_(included_course_codes))
    task_sids = set(r[0] for r in task_q.distinct().all())

    # Segunda matrícula (enrollments)
    rep_enroll_counts = defaultdict(int)
    for sid, in db.query(Enrollment.student_id).filter(
        Enrollment.numero_repitencias > 1, Enrollment.es_tercera_matricula == False, periodo_cond,
    ).all():
        rep_enroll_counts[sid] += 1

    # Segunda matrícula (grades fallback)
    rep_grade_counts = defaultdict(int)
    for sid, in db.query(Grade.student_id).filter(
        Grade.numero_repitencias > 1, grade_periodo_cond,
    ).all():
        rep_grade_counts[sid] += 1

    # Tercera matrícula
    tm_enroll_counts = defaultdict(int)
    for sid, in db.query(Enrollment.student_id).filter(
        Enrollment.es_tercera_matricula == True,
    ).all():
        tm_enroll_counts[sid] += 1

    all_tm_sids = set(r[0] for r in db.query(Student.id).filter(
        Student.es_tercera_matricula == True,
    ).all())
    all_rep_sids = set(rep_enroll_counts.keys()) | set(rep_grade_counts.keys())

    # Dedup: evitar duplicados dentro de la misma ejecución
    # (No necesitamos ventana temporal ya que hacemos full-refresh)
    existing_alerts = set()

    created = 0

    def _add_alert_fast(student_id, tipo, severidad, mensaje, codigo_curso=None):
        nonlocal created
        key = (student_id, tipo, codigo_curso)
        if key in existing_alerts:
            return
        existing_alerts.add(key)
        db.add(AlertEvent(
            student_id=student_id, tipo=tipo, mensaje=mensaje,
            severidad=severidad, codigo_curso=codigo_curso,
        ))
        created += 1

    # ========== Procesar estudiantes ==========
    processed_ids = {s.id for s in students}
    extra_sids = (all_tm_sids | all_rep_sids) - processed_ids
    all_students = list(students)
    if extra_sids:
        extra_students = db.query(Student).filter(Student.id.in_(extra_sids)).all()
        all_students.extend(extra_students)

    for student in all_students:
        # Inactividad
        cursos = avac_por_curso.get(student.id, [])
        worst_dias = 0
        worst_codigo = None
        inactive_courses = []
        for codigo_curso, dias in cursos:
            if max_dias_periodo is not None:
                dias = min(dias, max_dias_periodo)
            if dias > umbral_dias_inactividad:
                asig = asignatura_map.get(codigo_curso, codigo_curso)
                inactive_courses.append((asig, int(dias)))
                if dias > worst_dias:
                    worst_dias = dias
                    worst_codigo = codigo_curso

        if worst_dias > umbral_dias_inactividad and inactive_courses:
            n_materias = len(inactive_courses)
            worst_asig = asignatura_map.get(worst_codigo, worst_codigo)
            if n_materias == 1:
                msg = f"Inactivo {int(worst_dias)} días en {worst_asig}"
            else:
                msg = f"Inactivo en {n_materias} materias (peor: {int(worst_dias)} días en {worst_asig})"
            if worst_dias > umbral_dias_inactividad_alto:
                _add_alert_fast(student.id, "inactividad", "alto",
                                msg + " (CRÍTICO)", codigo_curso=worst_codigo)
            else:
                _add_alert_fast(student.id, "inactividad", "medio",
                                msg, codigo_curso=worst_codigo)

        # Compromiso Bajo
        in_bloque = not bloque_actual_sids or student.id in bloque_actual_sids
        if in_bloque and student.indice_compromiso is not None:
            if student.indice_compromiso < umbral_compromiso_alto:
                _add_alert_fast(student.id, "compromiso_bajo", "alto",
                                f"Índice de compromiso muy bajo: {student.indice_compromiso:.2f}")
            elif student.indice_compromiso < umbral_compromiso:
                _add_alert_fast(student.id, "compromiso_bajo", "medio",
                                f"Índice de compromiso bajo: {student.indice_compromiso:.2f}")

        # Nota Cero
        if hay_notas_esperadas and student.id in nota_cero_map:
            _add_alert_fast(student.id, "nota_cero", "alto",
                            f"Calificación de 0 en {nota_cero_map[student.id]}")

        # Tareas Bajas
        if (in_bloque and student.porcentaje_tareas is not None
                and student.porcentaje_tareas < umbral_tareas
                and student.id in task_sids):
            _add_alert_fast(student.id, "tareas_bajas", "medio",
                            f"Porcentaje de tareas entregadas bajo: {student.porcentaje_tareas:.1f}% (umbral: {umbral_tareas}%)")

        # Segunda Matrícula
        if not student.es_tercera_matricula:
            n_asig_2m = rep_enroll_counts.get(student.id, 0)
            if n_asig_2m == 0:
                n_asig_2m = rep_grade_counts.get(student.id, 0)
            if n_asig_2m > 0:
                _add_alert_fast(student.id, "segunda_matricula", "medio",
                                f"Estudiante con {n_asig_2m} asignatura(s) en segunda matrícula")

        # Tercera Matrícula
        if student.es_tercera_matricula:
            n_asig_tm = tm_enroll_counts.get(student.id, 0)
            if n_asig_tm > 0:
                _add_alert_fast(student.id, "tercera_matricula", "alto",
                                f"Estudiante con {n_asig_tm} asignatura(s) en tercera matrícula (oyente condicionado)")

    # ─── Deterioro Progresivo [Épica 1.3] ───
    try:
        from .deterioro_detector import detectar_deterioro_progresivo
        deterioro_alertas = detectar_deterioro_progresivo(db)
        for alerta in deterioro_alertas:
            _add_alert_fast(
                alerta["student_id"],
                alerta["tipo"],
                alerta["severidad"],
                alerta["mensaje"],
                codigo_curso=alerta.get("codigo_curso"),
            )
    except Exception as det_err:
        logger.warning(f"Error en detección de deterioro progresivo: {det_err}")

    db.commit()

    # Build detail
    detail_parts = [
        f"Umbrales: inactividad>{umbral_dias_inactividad}d, compromiso<{umbral_compromiso}, tareas<{umbral_tareas}%",
        f"Estudiantes analizados: {len(all_students)}",
    ]
    if excluded_course_codes:
        detail_parts.append(f"Bloque {semconfig.bloque_actual}: {len(excluded_course_codes)} cursos del otro bloque excluidos")
    if not hay_notas_esperadas:
        detail_parts.append(f"Alertas de nota_cero desactivadas (primera fecha esperada: {fecha_notas.strftime('%d/%m/%Y') if fecha_notas else 'no configurada'})")
    if max_dias_periodo is not None:
        detail_parts.append(f"Inactividad capeada a máx {max_dias_periodo} días (inicio bloque: {bloque_inicio.strftime('%d/%m/%Y')})")
    if stale_deleted:
        detail_parts.append(f"{stale_deleted} alertas anteriores eliminadas")

    return {
        "created": created,
        "cleaned": stale_deleted,
        "timestamp": now.isoformat(),
        "detail": " | ".join(detail_parts) if detail_parts else None,
    }
