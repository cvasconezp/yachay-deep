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
from ..models import Student, Grade
from ..models.alert_event import AlertEvent
from ..models.course_config import SemesterConfig
from ..auth.jwt import get_current_user
from ..models.user import User


def _active_period_has_grades(db: Session) -> bool:
    """Verifica si hay calificaciones para el semestre activo.
    Retorna False cuando no hay datos, para evitar mostrar alertas stale."""
    sem = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    if not sem or not sem.semestre:
        # Sin semestre activo configurado → no mostrar alertas stale
        return False
    pf = sem.semestre.strip()
    q = db.query(Grade.id)
    # Buscar en todos los formatos posibles: "P68", "68", "2026-1"
    if pf.startswith("P"):
        q = q.filter(or_(Grade.periodo == pf, Grade.periodo == pf[1:]))
    else:
        q = q.filter(or_(Grade.periodo == pf, Grade.periodo == f"P{pf}"))
    return q.limit(1).first() is not None

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna alertas sin leer, ordenadas por recientes primero.
    Si no hay datos de AVAC/calificaciones para el periodo activo, retorna vacío."""
    # Si el periodo activo no tiene grades, no mostrar alertas stale
    if not _active_period_has_grades(db):
        return []

    # JOIN para evitar N+1 queries
    rows = (
        db.query(AlertEvent, Student.nombre, Student.carrera)
        .outerjoin(Student, AlertEvent.student_id == Student.id)
        .filter(AlertEvent.leido == False)
        .order_by(AlertEvent.created_at.desc())
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
    Si no hay datos para el periodo activo, retorna todo en 0."""
    # Si el periodo activo no tiene grades, no mostrar conteo stale
    if not _active_period_has_grades(db):
        return AlertCountResponse(total=0, critico=0, alto=0, medio=0)

    unread = AlertEvent.leido == False
    total = db.query(func.count(AlertEvent.id)).filter(unread).scalar() or 0
    critico = db.query(func.count(AlertEvent.id)).filter(
        unread, AlertEvent.severidad == "critico"
    ).scalar() or 0
    alto = db.query(func.count(AlertEvent.id)).filter(
        unread, AlertEvent.severidad == "alto"
    ).scalar() or 0
    medio = db.query(func.count(AlertEvent.id)).filter(
        unread, AlertEvent.severidad == "medio"
    ).scalar() or 0

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
    """
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
