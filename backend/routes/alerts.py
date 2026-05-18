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
