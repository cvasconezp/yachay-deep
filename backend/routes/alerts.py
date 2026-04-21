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
from ..auth.jwt import get_current_user
from ..models.user import User


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

    class Config:
        from_attributes = True


class AlertCountResponse(BaseModel):
    total: int = 0
    critico: int = 0
    alto: int = 0
    medio: int = 0


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
        )
        for alert, nombre, student_carrera in rows
    ]


@router.get("/count", response_model=AlertCountResponse)
def get_alert_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna conteo de alertas sin leer por severidad.
    Solo cuenta alertas de estudiantes del periodo activo."""
    if not _active_period_has_data(db):
        return AlertCountResponse(total=0, critico=0, alto=0, medio=0)

    period_sids = _active_period_student_ids(db)

    unread = AlertEvent.leido == False

    def _count(extra_filter=None):
        q = db.query(func.count(AlertEvent.id)).filter(unread)
        if period_sids:
            q = q.filter(AlertEvent.student_id.in_(period_sids))
        if extra_filter is not None:
            q = q.filter(extra_filter)
        return q.scalar() or 0

    total = _count()
    critico = _count(AlertEvent.severidad == "critico")
    alto = _count(AlertEvent.severidad == "alto")
    medio = _count(AlertEvent.severidad == "medio")

    return AlertCountResponse(
        total=total,
        critico=critico,
        alto=alto,
        medio=medio,
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

    Reglas de inactividad (basado en AvacAccess del periodo actual):
    - dias_sin_acceso > 14 → "inactividad" alto
    - dias_sin_acceso > 21 → "inactividad" critico
    - Días capeados al máximo de días desde inicio del bloque actual

    Reglas de calificaciones (solo si ya pasó fecha esperada de notas):
    - Nota final = 0 → "nota_cero" critico (solo del periodo activo)
    - porcentaje_tareas < 40 → "tareas_bajas" alto

    Compromiso: basado en indice_compromiso del estudiante.

    Solo crea alertas que no existan para el mismo student+tipo en los últimos 7 días.
    Solo escanea estudiantes del período activo.
    """
    # ── Limpiar alertas stale: eliminar todas las no leídas antes de regenerar ──
    # Las alertas leídas se conservan como registro histórico.
    stale_deleted = db.query(AlertEvent).filter(AlertEvent.leido == False).delete()
    db.flush()

    # Obtener configuración del semestre activo
    semconfig = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    if not semconfig:
        return {"created": 0, "timestamp": datetime.now(timezone.utc).isoformat(), "detail": "No hay semestre activo"}

    pf = semconfig.semestre.strip() if semconfig.semestre else None
    if not pf:
        return {"created": 0, "timestamp": datetime.now(timezone.utc).isoformat(), "detail": "Semestre sin nombre"}

    # Determinar inicio del bloque actual para capear inactividad
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

    # Excluir cursos del bloque contrario (ej: excluir bloque 2 si estamos en bloque 1)
    excluded_course_codes = set()
    if semconfig:
        other_bloque = "2" if semconfig.bloque_actual == "1" else "1"
        excluded_cc = db.query(CourseConfig.codigo_avac).filter(
            CourseConfig.bloque == other_bloque,
        ).all()
        excluded_course_codes = {r[0] for r in excluded_cc}

    # Pre-load per-period AvacAccess: dias_sin_acceso por estudiante POR CURSO
    # Incluir periodo NULL como fallback (datos cargados antes de configurar periodo)
    periodo_filter = or_(
        AvacAccess.periodo.in_(periodo_variants),
        AvacAccess.periodo.is_(None),
    )

    # Último snapshot disponible
    latest_snap = (
        db.query(func.max(AvacAccess.snapshot_date))
        .filter(periodo_filter, AvacAccess.student_id.isnot(None))
        .scalar()
    )
    avac_q = db.query(
        AvacAccess.student_id,
        AvacAccess.codigo_curso,
        AvacAccess.dias_sin_acceso,
    ).filter(
        periodo_filter,
        AvacAccess.student_id.isnot(None),
        AvacAccess.dias_sin_acceso.isnot(None),
    )
    if latest_snap:
        avac_q = avac_q.filter(AvacAccess.snapshot_date == latest_snap)
    if excluded_course_codes:
        avac_q = avac_q.filter(~AvacAccess.codigo_curso.in_(excluded_course_codes))

    # Dict: student_id → [(codigo_curso, dias_sin_acceso), ...]
    from collections import defaultdict
    avac_por_curso = defaultdict(list)
    for sid, codigo, dias in avac_q.all():
        avac_por_curso[sid].append((codigo, dias))

    # Pre-load asignatura names
    all_codes = {codigo for entries in avac_por_curso.values() for codigo, _ in entries}
    asignatura_map = {}
    if all_codes:
        for cc in db.query(CourseConfig).filter(CourseConfig.codigo_avac.in_(all_codes)).all():
            asignatura_map[cc.codigo_avac] = cc.asignatura

    created = 0
    threshold_date = now - timedelta(days=7)

    def _add_alert(student_id, tipo, severidad, mensaje, codigo_curso=None):
        nonlocal created
        q = db.query(AlertEvent).filter(
            AlertEvent.student_id == student_id,
            AlertEvent.tipo == tipo,
            AlertEvent.created_at >= threshold_date,
        )
        if codigo_curso:
            q = q.filter(AlertEvent.codigo_curso == codigo_curso)
        if not q.first():
            db.add(AlertEvent(
                student_id=student_id, tipo=tipo, mensaje=mensaje,
                severidad=severidad, codigo_curso=codigo_curso,
            ))
            created += 1

    for student in students:
        # ========== Inactividad POR ASIGNATURA (per-period AvacAccess) ==========
        cursos = avac_por_curso.get(student.id, [])
        for codigo_curso, dias in cursos:
            if max_dias_periodo is not None:
                dias = min(dias, max_dias_periodo)
            asig = asignatura_map.get(codigo_curso, codigo_curso)

            if dias > 21:
                _add_alert(student.id, "inactividad", "critico",
                           f"Inactivo {int(dias)} días en {asig} (CRÍTICO)",
                           codigo_curso=codigo_curso)
            elif dias > 14:
                _add_alert(student.id, "inactividad", "alto",
                           f"Inactivo {int(dias)} días en {asig}",
                           codigo_curso=codigo_curso)

        # ========== Compromiso Bajo ==========
        if student.indice_compromiso is not None:
            if student.indice_compromiso < 0.3:
                _add_alert(student.id, "compromiso_bajo", "critico",
                           f"Índice de compromiso muy bajo: {student.indice_compromiso:.2f}")
            elif student.indice_compromiso < 0.55:
                _add_alert(student.id, "compromiso_bajo", "alto",
                           f"Índice de compromiso bajo: {student.indice_compromiso:.2f}")

        # ========== Nota Cero (solo si ya se esperan notas según calendario) ==========
        if hay_notas_esperadas:
            nota_cero = db.query(Grade).filter(
                Grade.student_id == student.id,
                Grade.nota_final == 0,
                or_(Grade.periodo == periodo_variants[0], Grade.periodo == periodo_variants[1]),
            ).first()

            if nota_cero:
                _add_alert(student.id, "nota_cero", "critico",
                           f"Calificación de 0 en {nota_cero.asignatura}")

        # ========== Tareas Bajas (solo si hay datos de tareas del periodo) ==========
        if student.porcentaje_tareas is not None and student.porcentaje_tareas < 40:
            # Solo alertar si hay registros de tareas del periodo actual
            from ..models import TaskSubmission
            has_tasks = db.query(TaskSubmission.id).filter(
                TaskSubmission.student_id == student.id,
                or_(TaskSubmission.periodo == periodo_variants[0], TaskSubmission.periodo == periodo_variants[1]),
            ).limit(1).first()
            if has_tasks:
                _add_alert(student.id, "tareas_bajas", "alto",
                           f"Porcentaje de tareas entregadas muy bajo: {student.porcentaje_tareas:.1f}%")

        # ========== Segunda Matrícula (repitentes con 2 intentos) ==========
        if not student.es_tercera_matricula:
            n_asig_2m = db.query(Enrollment).filter(
                Enrollment.student_id == student.id,
                Enrollment.numero_repitencias == 2,
                or_(Enrollment.periodo == periodo_variants[0], Enrollment.periodo == periodo_variants[1]),
            ).count()
            if n_asig_2m > 0:
                _add_alert(student.id, "segunda_matricula", "alto",
                           f"Estudiante con {n_asig_2m} asignatura(s) en segunda matrícula")

        # ========== Tercera Matrícula (per-student flag) ==========
        if student.es_tercera_matricula:
            n_asig_tm = db.query(Enrollment).filter(
                Enrollment.student_id == student.id,
                Enrollment.es_tercera_matricula == True,
            ).count()
            if n_asig_tm > 0:
                _add_alert(student.id, "tercera_matricula", "critico",
                           f"Estudiante con {n_asig_tm} asignatura(s) en tercera matrícula (oyente condicionado)")

    db.commit()

    detail_parts = []
    if excluded_course_codes:
        detail_parts.append(f"Bloque {semconfig.bloque_actual}: {len(excluded_course_codes)} cursos del otro bloque excluidos")
    if not hay_notas_esperadas:
        detail_parts.append(f"Alertas de nota_cero desactivadas (primera fecha esperada de notas: {fecha_notas.strftime('%d/%m/%Y') if fecha_notas else 'no configurada'})")
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
