"""
Módulo de Alertas — eventos generados automáticamente basados en umbrales.
[GAP-F6-01] Integración de alertas en el feedback loop.
"""
from typing import Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from pydantic import BaseModel

from ..database import get_db
from ..models import Student, Grade, AvacAccess
from ..models.enrollment import Enrollment
from ..models.alert_event import AlertEvent
from ..models.course_config import SemesterConfig, CourseConfig
from ..models.intervention import Intervention
from ..auth.jwt import get_current_user
from ..models.user import User
from .analytics._helpers import get_umbrales


def _active_period_has_data(db: Session) -> bool:
    """Verifica si hay datos (calificaciones o accesos AVAC) para el semestre activo.
    Incluye grades con periodo=NULL (legacy: cargados antes de etiquetar con periodo).
    Retorna False cuando no hay datos, para evitar mostrar alertas stale."""
    sem = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    if not sem or not sem.semestre:
        return False
    pf = sem.semestre.strip()

    # Check grades
    q_grades = db.query(Grade.id)
    if pf.startswith("P"):
        q_grades = q_grades.filter(or_(Grade.periodo == pf, Grade.periodo == pf[1:], Grade.periodo.is_(None)))
    else:
        q_grades = q_grades.filter(or_(Grade.periodo == pf, Grade.periodo == f"P{pf}", Grade.periodo.is_(None)))
    if q_grades.limit(1).first() is not None:
        return True

    # Check AvacAccess (incluir periodo=NULL como fallback)
    q_avac = db.query(AvacAccess.id).filter(AvacAccess.student_id.isnot(None))
    if pf.startswith("P"):
        q_avac = q_avac.filter(or_(AvacAccess.periodo == pf, AvacAccess.periodo == pf[1:], AvacAccess.periodo.is_(None)))
    else:
        q_avac = q_avac.filter(or_(AvacAccess.periodo == pf, AvacAccess.periodo == f"P{pf}", AvacAccess.periodo.is_(None)))
    return q_avac.limit(1).first() is not None


def _active_period_student_ids(db: Session) -> set:
    """Retorna set de student_ids para el periodo activo (grades + enrollments + avac_accesses).
    Usado para filtrar alertas solo a estudiantes del periodo actual."""
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

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertEventResponse(BaseModel):
    id: int
    student_id: int
    student_nombre: Optional[str] = None
    student_carrera: Optional[str] = None
    tipo: str
    mensaje: Optional[str] = None
    severidad: str
    codigo_curso: Optional[str] = None
    asignatura: Optional[str] = None
    leido: bool
    leido_por: Optional[str] = None
    leido_at: Optional[str] = None
    created_at: str
    # Contexto del estudiante para priorización
    dias_sin_acceso: Optional[int] = None
    porcentaje_tareas: Optional[float] = None
    indice_compromiso: Optional[float] = None
    nivel_riesgo: Optional[str] = None
    score_recuperabilidad: Optional[float] = None
    tiene_intervencion: Optional[bool] = None

    class Config:
        from_attributes = True


class AlertCountResponse(BaseModel):
    total: int = 0
    alto: int = 0
    medio: int = 0
    bajo: int = 0
    por_tipo: dict = {}


@router.get("/pending", response_model=list[AlertEventResponse])
def get_pending_alerts(
    limit: int = Query(200, le=1000),
    offset: int = Query(0, ge=0),
    carrera: Optional[str] = None,
    asignatura: Optional[str] = None,
    periodo: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna alertas sin leer, ordenadas por recientes primero.
    Solo incluye alertas de estudiantes del periodo activo.
    Filtros opcionales: carrera, asignatura, periodo."""

    # Si se proporciona periodo explícito, construir student_ids para ese periodo
    if periodo:
        pf = periodo.strip()

        if pf.startswith("P"):
            raw = pf[1:]
            g_cond = or_(Grade.periodo == pf, Grade.periodo == raw, Grade.periodo.is_(None))
            e_cond = or_(Enrollment.periodo == pf, Enrollment.periodo == raw)
            a_cond = or_(AvacAccess.periodo == pf, AvacAccess.periodo == raw)
        else:
            g_cond = or_(Grade.periodo == pf, Grade.periodo == f"P{pf}", Grade.periodo.is_(None))
            e_cond = or_(Enrollment.periodo == pf, Enrollment.periodo == f"P{pf}")
            a_cond = or_(AvacAccess.periodo == pf, AvacAccess.periodo == f"P{pf}")

        grade_ids = {r[0] for r in db.query(Grade.student_id).filter(g_cond).distinct().all()}
        enroll_ids = {r[0] for r in db.query(Enrollment.student_id).filter(e_cond).distinct().all()}
        avac_ids = {r[0] for r in db.query(AvacAccess.student_id).filter(a_cond, AvacAccess.student_id.isnot(None)).distinct().all()}
        period_sids = grade_ids | enroll_ids | avac_ids
    else:
        if not _active_period_has_data(db):
            return []
        period_sids = _active_period_student_ids(db)

    q = (
        db.query(AlertEvent, Student.nombre, Student.carrera)
        .outerjoin(Student, AlertEvent.student_id == Student.id)
        .filter(AlertEvent.leido == False)
    )

    # Filtrar solo estudiantes del periodo
    if period_sids:
        q = q.filter(AlertEvent.student_id.in_(period_sids))

    # Filtrar por carrera (case-insensitive contains)
    if carrera:
        q = q.filter(func.lower(Student.carrera).contains(carrera.lower()))

    # Filtrar por asignatura: solo alertas cuyo codigo_curso pertenece a esa asignatura
    if asignatura:
        asig_codes = [r[0] for r in db.query(CourseConfig.codigo_avac).filter(
            func.lower(CourseConfig.asignatura).contains(asignatura.lower()),
        ).all()]
        if asig_codes:
            q = q.filter(AlertEvent.codigo_curso.in_(asig_codes))
        else:
            return []

    rows = (
        q.order_by(AlertEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Pre-load asignatura names for alerts that have codigo_curso
    from ..models.course_config import CourseConfig
    curso_codes = {alert.codigo_curso for alert, _, _ in rows if alert.codigo_curso}
    asignatura_map = {}
    if curso_codes:
        for cc in db.query(CourseConfig).filter(CourseConfig.codigo_avac.in_(curso_codes)).all():
            asignatura_map[cc.codigo_avac] = cc.asignatura

    # Pre-load student context (metrics + intervention status)
    student_ids = list({alert.student_id for alert, _, _ in rows})
    student_context = {}

    # ── Calcular dias_sin_acceso filtrado por bloque actual ──
    dias_por_estudiante = {}
    try:
        semconfig_q = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
        bloque_course_codes = set()
        if semconfig_q and semconfig_q.bloque_actual:
            other_bloque = "2" if semconfig_q.bloque_actual == "1" else "1"
            excluded_cc = db.query(CourseConfig.codigo_avac).filter(
                CourseConfig.bloque == other_bloque,
            ).all()
            excluded_codes = {r[0] for r in excluded_cc if r[0]}
            all_cc = db.query(CourseConfig.codigo_avac).filter(
                CourseConfig.codigo_avac.isnot(None),
            ).all()
            bloque_course_codes = {r[0] for r in all_cc if r[0]} - excluded_codes

        if student_ids and bloque_course_codes:
            latest_snap = db.query(func.max(AvacAccess.snapshot_date)).filter(
                AvacAccess.student_id.in_(student_ids),
                AvacAccess.dias_sin_acceso.isnot(None),
                AvacAccess.codigo_curso.in_(bloque_course_codes),
            ).scalar()
            if latest_snap:
                for sid, dias in db.query(
                    AvacAccess.student_id,
                    func.max(AvacAccess.dias_sin_acceso),
                ).filter(
                    AvacAccess.student_id.in_(student_ids),
                    AvacAccess.dias_sin_acceso.isnot(None),
                    AvacAccess.codigo_curso.in_(bloque_course_codes),
                    AvacAccess.snapshot_date == latest_snap,
                ).group_by(AvacAccess.student_id).all():
                    dias_por_estudiante[sid] = int(dias) if dias is not None else None
    except Exception:
        pass  # Fallback: use Student.dias_sin_acceso below

    if student_ids:
        for s in db.query(Student).filter(Student.id.in_(student_ids)).all():
            # Use bloque-filtered dias_sin_acceso; if student has no courses
            # in the current bloque, show None instead of stale data from other bloque
            if bloque_course_codes:
                dias = dias_por_estudiante.get(s.id)  # None if no bloque courses
            else:
                dias = s.dias_sin_acceso  # No bloque filter → use stored value
            student_context[s.id] = {
                "dias_sin_acceso": dias,
                "porcentaje_tareas": s.porcentaje_tareas,
                "indice_compromiso": s.indice_compromiso,
                "nivel_riesgo": s.nivel_riesgo,
                "score_recuperabilidad": s.score_recuperabilidad,
            }
        # Check active interventions
        active_states = ("pendiente", "en_progreso", "contactado")
        interv_ids = {r[0] for r in db.query(Intervention.student_id).filter(
            Intervention.student_id.in_(student_ids),
            Intervention.estado_workflow.in_(active_states),
        ).distinct().all()}
        for sid in student_ids:
            if sid in student_context:
                student_context[sid]["tiene_intervencion"] = sid in interv_ids

    return [
        AlertEventResponse(
            id=alert.id,
            student_id=alert.student_id,
            student_nombre=nombre,
            student_carrera=student_carrera,
            tipo=alert.tipo,
            mensaje=alert.mensaje,
            severidad=alert.severidad,
            codigo_curso=alert.codigo_curso,
            asignatura=asignatura_map.get(alert.codigo_curso) if alert.codigo_curso else None,
            leido=alert.leido,
            leido_por=alert.leido_por,
            leido_at=alert.leido_at.isoformat() if alert.leido_at else None,
            created_at=alert.created_at.isoformat() if alert.created_at else None,
            **(student_context.get(alert.student_id, {})),
        )
        for alert, nombre, student_carrera in rows
    ]


@router.get("/count", response_model=AlertCountResponse)
def get_alert_count(
    carrera: Optional[str] = None,
    asignatura: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna conteo de alertas sin leer por severidad y tipo.
    Acepta filtros opcionales de carrera y asignatura.
    Solo cuenta alertas de estudiantes del periodo activo."""
    if not _active_period_has_data(db):
        return AlertCountResponse(total=0, alto=0, medio=0, bajo=0, por_tipo={})

    period_sids = _active_period_student_ids(db)

    unread = AlertEvent.leido == False

    # Base filter: unread + period students
    base_filters = [unread]
    if period_sids:
        base_filters.append(AlertEvent.student_id.in_(period_sids))

    # Carrera filter: restrict to students of that carrera
    if carrera:
        carrera_sids = set(r[0] for r in db.query(Student.id).filter(
            func.lower(Student.carrera).contains(carrera.lower()),
        ).all())
        base_filters.append(AlertEvent.student_id.in_(carrera_sids))

    # Asignatura filter: restrict to alerts whose codigo_curso matches
    if asignatura:
        asig_codes = [r[0] for r in db.query(CourseConfig.codigo_avac).filter(
            func.lower(CourseConfig.asignatura).contains(asignatura.lower()),
        ).all()]
        if asig_codes:
            base_filters.append(AlertEvent.codigo_curso.in_(asig_codes))
        else:
            return AlertCountResponse(total=0, alto=0, medio=0, bajo=0, por_tipo={})

    def _count(extra_filter=None):
        q = db.query(func.count(AlertEvent.id))
        for f in base_filters:
            q = q.filter(f)
        if extra_filter is not None:
            q = q.filter(extra_filter)
        return q.scalar() or 0

    total = _count()
    alto = _count(AlertEvent.severidad == "alto")
    medio = _count(AlertEvent.severidad == "medio")
    bajo = _count(AlertEvent.severidad == "bajo")

    # Per-type counts
    tipo_q = db.query(AlertEvent.tipo, func.count(AlertEvent.id))
    for f in base_filters:
        tipo_q = tipo_q.filter(f)
    tipo_rows = tipo_q.group_by(AlertEvent.tipo).all()
    por_tipo = {tipo: cnt for tipo, cnt in tipo_rows}

    return AlertCountResponse(
        total=total,
        alto=alto,
        medio=medio,
        bajo=bajo,
        por_tipo=por_tipo,
    )


@router.patch("/{alert_id}/read")
def mark_alert_read(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Marca una alerta como leída."""
    alert = db.query(AlertEvent).filter(AlertEvent.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")

    alert.leido = True
    alert.leido_por = current_user.email
    alert.leido_at = datetime.now(timezone.utc)
    db.commit()

    return {"id": alert.id, "leido": alert.leido}


def _get_calendario(semconfig) -> list[dict]:
    """Parsea el calendario_academico JSON de SemesterConfig."""
    import json
    if not semconfig or not semconfig.calendario_academico:
        return []
    try:
        return json.loads(semconfig.calendario_academico)
    except (json.JSONDecodeError, TypeError):
        return []


def _primera_fecha_notas(calendario: list[dict]) -> datetime | None:
    """Retorna la fecha más temprana en que se esperan notas (primera entrega + 7 días)."""
    from datetime import date as date_type
    entregas = [e for e in calendario if e.get("tipo") in ("entrega", "paso_notas")]
    if not entregas:
        return None
    fechas = []
    for e in entregas:
        try:
            d = datetime.strptime(e["fecha"], "%Y-%m-%d")
            if e.get("tipo") == "entrega":
                d = d + timedelta(days=7)  # Se esperan notas 7 días después de entrega
            fechas.append(d)
        except (ValueError, KeyError):
            continue
    return min(fechas) if fechas else None


@router.post("/generate")
def generate_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Genera alertas barriendo todos los estudiantes por umbrales.
    Delega a generate_alerts_batch() para permitir reutilización desde el pipeline ETL.
    """
    from ..services.alert_generator import generate_alerts_batch
    return generate_alerts_batch(db)


@router.post("/digest/send")
def send_digest_endpoint(
    email: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Envía el Daily Digest por email.
    Si se proporciona email, envía solo a ese destinatario.
    Si no, envía a todos los admin/monitor.
    Solo admin puede ejecutar este endpoint.
    [Épica 2.1]
    """
    if current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Solo admin puede enviar digest")

    from ..services.daily_digest import send_daily_digest
    result = send_daily_digest(db, recipient_email=email)
    return result


@router.get("/digest/preview")
def preview_digest(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retorna el HTML del Daily Digest para preview sin enviar email.
    [Épica 2.1]
    """
    from ..services.daily_digest import build_digest_data, build_digest_html
    from fastapi.responses import HTMLResponse

    data = build_digest_data(db)
    html = build_digest_html(data)
    return HTMLResponse(content=html)


@router.get("/debug/conditions")
def debug_alert_conditions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Diagnóstico: muestra el estado de cada condición que activa cada tipo de alerta.
    Solo accesible por admins.
    """
    import json
    from ..models import TaskSubmission

    result = {}

    # Semestre activo
    semconfig = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    if not semconfig:
        return {"error": "No hay semestre activo"}

    pf = semconfig.semestre.strip() if semconfig.semestre else ""
    if pf.startswith("P"):
        periodo_variants = (pf, pf[1:])
    else:
        periodo_variants = (pf, f"P{pf}")

    result["semestre"] = pf
    result["bloque_actual"] = semconfig.bloque_actual

    # Calendario y fecha de notas
    calendario = []
    if semconfig.calendario_academico:
        try:
            calendario = json.loads(semconfig.calendario_academico)
        except Exception:
            pass

    from ..services.alert_generator import _primera_fecha_notas
    fecha_notas = _primera_fecha_notas(calendario)
    now = datetime.now(timezone.utc)
    hay_notas_esperadas = fecha_notas is not None and now >= fecha_notas.replace(tzinfo=timezone.utc)

    result["nota_cero"] = {
        "hay_notas_esperadas": hay_notas_esperadas,
        "primera_fecha_notas": fecha_notas.isoformat() if fecha_notas else None,
        "calendario_entries": [e for e in calendario if e.get("tipo") in ("entrega", "paso_notas")],
        "calendario_total_entries": len(calendario),
    }

    # Grades con nota 0 o NULL
    grade_periodo_cond = or_(
        Grade.periodo == periodo_variants[0],
        Grade.periodo == periodo_variants[1],
    )
    total_grades = db.query(func.count(Grade.id)).filter(grade_periodo_cond).scalar()
    null_grades = db.query(func.count(Grade.id)).filter(
        grade_periodo_cond, Grade.nota_final.is_(None)
    ).scalar()
    zero_grades = db.query(func.count(Grade.id)).filter(
        grade_periodo_cond, Grade.nota_final == 0
    ).scalar()
    result["nota_cero"]["total_grades_periodo"] = total_grades
    result["nota_cero"]["grades_null"] = null_grades
    result["nota_cero"]["grades_zero"] = zero_grades

    # Included asignaturas (bloque filter)
    included_course_codes = set()
    if semconfig:
        other_bloque = "2" if semconfig.bloque_actual == "1" else "1"
        excluded_cc = db.query(CourseConfig.codigo_avac).filter(
            CourseConfig.bloque == other_bloque,
        ).all()
        excluded_codes = {r[0] for r in excluded_cc if r[0]}
        all_cc = db.query(CourseConfig.codigo_avac).filter(
            CourseConfig.codigo_avac.isnot(None),
        ).all()
        included_course_codes = {r[0] for r in all_cc if r[0]} - excluded_codes

    included_asignaturas = set()
    if included_course_codes:
        for cc in db.query(CourseConfig.asignatura).filter(
            CourseConfig.codigo_avac.in_(included_course_codes),
            CourseConfig.asignatura.isnot(None),
        ).distinct().all():
            included_asignaturas.add(cc[0])

    result["nota_cero"]["included_asignaturas"] = sorted(included_asignaturas)[:20]

    # Filter grades by included_asignaturas
    if included_asignaturas:
        filtered_null = db.query(func.count(Grade.id)).filter(
            grade_periodo_cond, Grade.nota_final.is_(None),
            Grade.asignatura.in_(included_asignaturas)
        ).scalar()
        filtered_zero = db.query(func.count(Grade.id)).filter(
            grade_periodo_cond, Grade.nota_final == 0,
            Grade.asignatura.in_(included_asignaturas)
        ).scalar()
        result["nota_cero"]["filtered_null_in_bloque"] = filtered_null
        result["nota_cero"]["filtered_zero_in_bloque"] = filtered_zero

    # TaskSubmissions
    task_total = db.query(func.count(TaskSubmission.id)).filter(
        or_(TaskSubmission.periodo == periodo_variants[0],
            TaskSubmission.periodo == periodo_variants[1]),
    ).scalar()
    task_calificada = db.query(func.count(TaskSubmission.id)).filter(
        or_(TaskSubmission.periodo == periodo_variants[0],
            TaskSubmission.periodo == periodo_variants[1]),
        TaskSubmission.calificada == True,
        TaskSubmission.calificacion.isnot(None),
        TaskSubmission.calificacion_maxima.isnot(None),
        TaskSubmission.calificacion_maxima > 0,
    ).scalar()

    UMBRAL = 0.47
    # Students with low task grades
    task_cal_q = db.query(
        TaskSubmission.student_id,
        func.avg(TaskSubmission.calificacion).label("avg_cal"),
        func.avg(TaskSubmission.calificacion_maxima).label("avg_max"),
        func.count(TaskSubmission.id).label("n"),
    ).filter(
        or_(TaskSubmission.periodo == periodo_variants[0],
            TaskSubmission.periodo == periodo_variants[1]),
        TaskSubmission.calificada == True,
        TaskSubmission.calificacion.isnot(None),
        TaskSubmission.calificacion_maxima.isnot(None),
        TaskSubmission.calificacion_maxima > 0,
    )
    if included_course_codes:
        task_cal_q = task_cal_q.filter(TaskSubmission.codigo_curso.in_(included_course_codes))
    task_cal_q = task_cal_q.group_by(TaskSubmission.student_id)

    low_count = 0
    sample_low = []
    for sid, avg_cal, avg_max, n in task_cal_q.all():
        if avg_max and avg_max > 0 and n >= 2:
            pct = float(avg_cal) / float(avg_max)
            if pct < UMBRAL:
                low_count += 1
                if len(sample_low) < 3:
                    sample_low.append({
                        "student_id": sid,
                        "avg_cal": round(float(avg_cal), 2),
                        "avg_max": round(float(avg_max), 2),
                        "pct": round(pct * 100, 1),
                        "n_tareas": int(n),
                    })

    result["notas_bajas_tareas"] = {
        "total_task_submissions": task_total,
        "calificadas_con_nota": task_calificada,
        "students_below_threshold": low_count,
        "threshold_pct": UMBRAL * 100,
        "sample": sample_low,
    }

    # Segunda/Tercera matrícula
    periodo_cond = or_(
        Enrollment.periodo == periodo_variants[0],
        Enrollment.periodo == periodo_variants[1],
    )
    segunda = db.query(func.count(func.distinct(Enrollment.student_id))).filter(
        Enrollment.numero_repitencias > 1, Enrollment.es_tercera_matricula == False, periodo_cond
    ).scalar()
    tercera = db.query(func.count(func.distinct(Enrollment.student_id))).filter(
        Enrollment.es_tercera_matricula == True
    ).scalar()
    tercera_flag = db.query(func.count(Student.id)).filter(Student.es_tercera_matricula == True).scalar()

    result["segunda_matricula"] = {"students": segunda}
    result["tercera_matricula"] = {
        "enrollment_count": tercera,
        "student_flag_count": tercera_flag,
    }

    # Current alert counts by type
    alert_counts = dict(db.query(
        AlertEvent.tipo, func.count(AlertEvent.id)
    ).group_by(AlertEvent.tipo).all())
    result["current_alerts_by_type"] = alert_counts

    return result


@router.get("/student-tasks-detail/{student_id}")
def get_student_tasks_detail(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retorna detalle de tareas pendientes de un estudiante agrupadas por asignatura.
    Usado para generar mensaje personalizado de seguimiento.
    Formato: [{ asignatura, grupo, tareas_pendientes: ["Actividad 1", "Actividad 3"] }]
    """
    from ..models import TaskSubmission
    from ..models.course_config import CourseConfig

    semconfig, pf, periodo_variants = None, None, ()
    sem = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    if sem and sem.semestre:
        pf = sem.semestre.strip()
        if pf.startswith("P"):
            periodo_variants = (pf, pf[1:])
        else:
            periodo_variants = (pf, f"P{pf}")

    if not pf:
        return []

    # Determinar unidades vencidas según calendario académico
    import json as _json
    from ..services.alert_generator import _unidades_vencidas
    calendario = []
    if sem and sem.calendario_academico:
        try:
            calendario = _json.loads(sem.calendario_academico)
        except Exception:
            pass
    unidades_ok = _unidades_vencidas(calendario)

    # Build periodo filter
    if len(periodo_variants) == 2:
        pf_filter = or_(
            TaskSubmission.periodo == periodo_variants[0],
            TaskSubmission.periodo == periodo_variants[1],
        )
    else:
        pf_filter = TaskSubmission.periodo == periodo_variants[0]

    # Get latest snapshot per course for this student
    snaps = db.query(
        TaskSubmission.codigo_curso,
        func.max(TaskSubmission.snapshot_date).label("max_snap"),
    ).filter(
        TaskSubmission.student_id == student_id,
        pf_filter,
    ).group_by(TaskSubmission.codigo_curso).all()

    if not snaps:
        return []

    # Get all pending tasks (entregada but not calificada, OR not entregada at all)
    result = []
    for snap_row in snaps:
        cod = snap_row.codigo_curso
        snap = snap_row.max_snap

        subs = db.query(TaskSubmission).filter(
            TaskSubmission.student_id == student_id,
            TaskSubmission.codigo_curso == cod,
            TaskSubmission.snapshot_date == snap,
            pf_filter,
        ).all()

        # Find unidades where not entregada (solo actividades vencidas según calendario)
        no_entregadas = [s.unidad for s in subs if not s.entregada and s.unidad and s.unidad in unidades_ok]
        # Find unidades entregadas pero sin calificar aún
        sin_calificar = [s.unidad for s in subs if s.entregada and not s.calificada and s.unidad and s.unidad in unidades_ok]
        # Find unidades with nota cero or very low (solo actividades vencidas)
        notas_bajas = [s.unidad for s in subs if s.calificada and s.calificacion is not None
                       and s.calificacion_maxima and s.calificacion_maxima > 0
                       and (s.calificacion / s.calificacion_maxima) < 0.47 and s.unidad
                       and s.unidad in unidades_ok]

        if not no_entregadas and not notas_bajas and not sin_calificar:
            continue

        # Get asignatura info
        cc = db.query(CourseConfig).filter(CourseConfig.codigo_avac == cod).first()
        asignatura = cc.asignatura if cc else cod
        grupo = cc.grupo if cc else None

        entry = {"asignatura": asignatura, "grupo": grupo, "detalles": []}

        if no_entregadas:
            tareas_txt = " y ".join([f"Actividad {u}" for u in sorted(no_entregadas)])
            entry["detalles"].append(f"{tareas_txt} sin entrega")

        if sin_calificar:
            tareas_txt = " y ".join([f"Actividad {u}" for u in sorted(sin_calificar)])
            entry["detalles"].append(f"{tareas_txt} entregada sin calificar")

        if notas_bajas:
            tareas_txt = " y ".join([f"Actividad {u}" for u in sorted(notas_bajas)])
            entry["detalles"].append(f"{tareas_txt} con calificación baja")

        result.append(entry)

    result.sort(key=lambda x: x["asignatura"])
    return result
