"""
Módulo de Alertas — eventos generados automáticamente basados en umbrales.
[GAP-F6-01] Integración de alertas en el feedback loop.
"""
from typing import Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from ..database import get_db
from ..models import Student, Grade
from ..models.alert_event import AlertEvent
from ..auth.jwt import get_current_user
from ..models.user import User

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna alertas sin leer, ordenadas por recientes primero."""
    alerts = db.query(AlertEvent).filter(
        AlertEvent.leido == False
    ).order_by(
        AlertEvent.created_at.desc()
    ).all()

    result = []
    for alert in alerts:
        student = db.query(Student).filter(Student.id == alert.student_id).first()
        result.append(AlertEventResponse(
            id=alert.id,
            student_id=alert.student_id,
            student_nombre=student.nombre if student else None,
            student_carrera=student.carrera if student else None,
            tipo=alert.tipo,
            mensaje=alert.mensaje,
            severidad=alert.severidad,
            leido=alert.leido,
            leido_por=alert.leido_por,
            leido_at=alert.leido_at.isoformat() if alert.leido_at else None,
            created_at=alert.created_at.isoformat() if alert.created_at else None,
        ))

    return result


@router.get("/count", response_model=AlertCountResponse)
def get_alert_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna conteo de alertas sin leer por severidad."""
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
