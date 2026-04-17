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
from ..models.course_config import SemesterConfig
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

    # Check AvacAccess
    q_avac = db.query(AvacAccess.id).filter(AvacAccess.student_id.isnot(None))
    if pf.startswith("P"):
        q_avac = q_avac.filter(or_(AvacAccess.periodo == pf, AvacAccess.periodo == pf[1:]))
    else:
        q_avac = q_avac.filter(or_(AvacAccess.periodo == pf, AvacAccess.periodo == f"P{pf}"))
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
        a_cond = or_(AvacAccess.periodo == pf, AvacAccess.periodo == raw)
    else:
        g_cond = or_(Grade.periodo == pf, Grade.periodo == f"P{pf}", Grade.periodo.is_(None))
        e_cond = or_(Enrollment.periodo == pf, Enrollment.periodo == f"P{pf}")
        a_cond = or_(AvacAccess.periodo == pf, AvacAccess.periodo == f"P{pf}")

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
    periodo: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna alertas sin leer, ordenadas por recientes primero.
    Solo incluye alertas de estudiantes del periodo activo.
    Filtros opcionales: carrera (case-insensitive contains), periodo (override del activo)."""

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

    rows = (
        q.order_by(AlertEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        AlertEventResponse(
            id=alert.id,
            student_id=alert.student_id,
            student_nombre=nombre,
            student_carrera=carrera,
            tipo=alert.tipo,
            mensaje=alert.mensaje,
            severidad=alert.severidad,
            leido=alert.leido,
            leido_por=alert.leido_por,
            leido_at=alert.leido_at.isoformat() if alert.leido_at else None,
            created_at=alert.created_at.isoformat() if alert.created_at else None,
        )
        for alert, nombre, carrera in rows
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


@router.post("/generate")
def generate_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Genera alertas barriendo todos los estudiantes por umbrales.
    - dias_sin_acceso > 14 → "inactividad" (critico si > 21, alto si > 14)
    - indice_compromiso < 0.3 → "compromiso_bajo" (critico)
    - indice_compromiso < 0.55 → "compromiso_bajo" (alto)
    - Nota final = 0 → "nota_cero" (critico)
    - porcentaje_tareas < 40 → "tareas_bajas" (alto)

    Solo crea alertas que no existan para el mismo student+tipo en los últimos 7 días.
    Solo escanea estudiantes del período activo.
    """
    period_sids = _active_period_student_ids(db)
    if period_sids:
        students = db.query(Student).filter(
            Student.id.in_(period_sids)
        ).all()
    else:
        students = db.query(Student).all()
    created = 0
    threshold_date = datetime.now(timezone.utc) - timedelta(days=7)

    for student in students:
        # ========== Inactividad ==========
        if student.dias_sin_acceso is not None:
            if student.dias_sin_acceso > 21:
                tipo, severidad = "inactividad", "critico"
                mensaje = f"Estudiante inactivo por {student.dias_sin_acceso} días (CRÍTICO)"
            elif student.dias_sin_acceso > 14:
                tipo, severidad = "inactividad", "alto"
                mensaje = f"Estudiante inactivo por {student.dias_sin_acceso} días"
            else:
                tipo = None

            if tipo:
                # Verificar si existe alerta similar reciente
                existing = db.query(AlertEvent).filter(
                    AlertEvent.student_id == student.id,
                    AlertEvent.tipo == tipo,
                    AlertEvent.created_at >= threshold_date,
                ).first()

                if not existing:
                    alert = AlertEvent(
                        student_id=student.id,
                        tipo=tipo,
                        mensaje=mensaje,
                        severidad=severidad,
                    )
                    db.add(alert)
                    created += 1

        # ========== Compromiso Bajo ==========
        if student.indice_compromiso is not None:
            if student.indice_compromiso < 0.3:
                severidad = "critico"
                mensaje = f"Índice de compromiso muy bajo: {student.indice_compromiso:.2f}"
            elif student.indice_compromiso < 0.55:
                severidad = "alto"
                mensaje = f"Índice de compromiso bajo: {student.indice_compromiso:.2f}"
            else:
                severidad = None

            if severidad:
                tipo = "compromiso_bajo"
                existing = db.query(AlertEvent).filter(
                    AlertEvent.student_id == student.id,
                    AlertEvent.tipo == tipo,
                    AlertEvent.created_at >= threshold_date,
                ).first()

                if not existing:
                    alert = AlertEvent(
                        student_id=student.id,
                        tipo=tipo,
                        mensaje=mensaje,
                        severidad=severidad,
                    )
                    db.add(alert)
                    created += 1

        # ========== Nota Cero ==========
        # Verificar si hay alguna nota = 0
        nota_cero = db.query(Grade).filter(
            Grade.student_id == student.id,
            Grade.nota_final == 0,
        ).first()

        if nota_cero:
            tipo = "nota_cero"
            severidad = "critico"
            mensaje = f"Calificación de 0 en {nota_cero.asignatura}"

            existing = db.query(AlertEvent).filter(
                AlertEvent.student_id == student.id,
                AlertEvent.tipo == tipo,
                AlertEvent.created_at >= threshold_date,
            ).first()

            if not existing:
                alert = AlertEvent(
                    student_id=student.id,
                    tipo=tipo,
                    mensaje=mensaje,
                    severidad=severidad,
                )
                db.add(alert)
                created += 1

        # ========== Tareas Bajas ==========
        if student.porcentaje_tareas is not None and student.porcentaje_tareas < 40:
            tipo = "tareas_bajas"
            severidad = "alto"
            mensaje = f"Porcentaje de tareas entregadas muy bajo: {student.porcentaje_tareas:.1f}%"

            existing = db.query(AlertEvent).filter(
                AlertEvent.student_id == student.id,
                AlertEvent.tipo == tipo,
                AlertEvent.created_at >= threshold_date,
            ).first()

            if not existing:
                alert = AlertEvent(
                    student_id=student.id,
                    tipo=tipo,
                    mensaje=mensaje,
                    severidad=severidad,
                )
                db.add(alert)
                created += 1

    db.commit()
    return {"created": created, "timestamp": datetime.now(timezone.utc).isoformat()}
