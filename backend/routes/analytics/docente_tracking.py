"""
Módulo 8.4: Analítica Docente Tracking.
Seguimiento de calificación y retroalimentación de actividades por docente.
Fuente: DocenteTracking model.
"""
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from pydantic import BaseModel

from ...database import get_db
from ...models import Student
from ...models.docente_tracking import DocenteTracking
from ...auth.jwt import get_current_user
from ...models.user import User

router = APIRouter(prefix="/analytics", tags=["analytics"])


class DocenteTrackingStats(BaseModel):
    docente: str
    total_actividades: int = 0
    actividades_calificadas: int = 0
    actividades_pendientes: int = 0
    porcentaje_calificacion: float = 0.0
    promedio_dias_retraso: Optional[float] = None
    cursos: list[str] = []
    alerta: str = "ok"  # critico, atencion, ok

    class Config:
        from_attributes = True


class DocenteTrackingDetalle(BaseModel):
    id: int
    codigo_curso: Optional[str] = None
    nombre_curso: Optional[str] = None
    actividad: Optional[str] = None
    tipo_actividad: Optional[str] = None
    calificada: Optional[bool] = None
    fecha_limite: Optional[str] = None
    fecha_calificacion: Optional[str] = None
    dias_retraso: Optional[float] = None

    class Config:
        from_attributes = True


class ResumenDocenteTracking(BaseModel):
    total_docentes: int = 0
    promedio_general_calificacion: float = 0.0
    docentes_en_atencion: int = 0
    docentes_criticos: int = 0


@router.get("/docente-tracking", response_model=list[DocenteTrackingStats])
def get_docente_tracking(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Estadísticas agregadas por docente."""
    docentes_query = db.query(DocenteTracking.docente).filter(
        DocenteTracking.docente.isnot(None),
        DocenteTracking.docente != "",
    ).distinct()

    docentes = [d.docente for d in docentes_query.all()]

    output = []
    for docente_name in docentes:
        actividades = db.query(DocenteTracking).filter(
            DocenteTracking.docente == docente_name
        ).all()

        if not actividades:
            continue

        # Contar calificadas y pendientes
        total = len(actividades)
        calificadas = sum(1 for a in actividades if a.calificada is True)
        pendientes = total - calificadas

        # Porcentaje de calificación
        pct_cal = (calificadas / max(total, 1)) * 100

        # Promedio días de retraso (solo positivos)
        dias_retraso_values = [
            a.dias_retraso for a in actividades
            if a.dias_retraso is not None and a.dias_retraso > 0
        ]
        promedio_retraso = (
            sum(dias_retraso_values) / len(dias_retraso_values)
            if dias_retraso_values
            else None
        )

        # Cursos distintos
        cursos = sorted(list(set(
            a.nombre_curso for a in actividades if a.nombre_curso
        )))

        # Determinar alerta
        if pct_cal < 50:
            alerta = "critico"
        elif pct_cal < 80:
            alerta = "atencion"
        else:
            alerta = "ok"

        output.append(DocenteTrackingStats(
            docente=docente_name,
            total_actividades=total,
            actividades_calificadas=calificadas,
            actividades_pendientes=pendientes,
            porcentaje_calificacion=round(pct_cal, 1),
            promedio_dias_retraso=round(promedio_retraso, 1) if promedio_retraso else None,
            cursos=cursos,
            alerta=alerta,
        ))

    # Ordenar por alerta crítica primero, luego por porcentaje calificación
    output.sort(key=lambda x: (
        0 if x.alerta == "critico" else (1 if x.alerta == "atencion" else 2),
        x.porcentaje_calificacion,
    ))

    return output


@router.get("/docente-tracking/{docente_name}", response_model=list[DocenteTrackingDetalle])
def get_docente_tracking_detalle(
    docente_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Desglose por actividad para un docente específico."""
    actividades = db.query(DocenteTracking).filter(
        DocenteTracking.docente == docente_name
    ).order_by(
        DocenteTracking.nombre_curso,
        DocenteTracking.actividad,
    ).all()

    return [
        DocenteTrackingDetalle(
            id=a.id,
            codigo_curso=a.codigo_curso,
            nombre_curso=a.nombre_curso,
            actividad=a.actividad,
            tipo_actividad=a.tipo_actividad,
            calificada=a.calificada,
            fecha_limite=a.fecha_limite.isoformat() if a.fecha_limite else None,
            fecha_calificacion=a.fecha_calificacion.isoformat() if a.fecha_calificacion else None,
            dias_retraso=a.dias_retraso,
        )
        for a in actividades
    ]


@router.get("/docente-tracking/resumen", response_model=ResumenDocenteTracking)
def get_docente_tracking_resumen(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resumen general del tracking de docentes."""
    # Total docentes únicos
    docentes_query = db.query(distinct(DocenteTracking.docente)).filter(
        DocenteTracking.docente.isnot(None),
        DocenteTracking.docente != "",
    )
    total_docentes = docentes_query.count()

    if total_docentes == 0:
        return ResumenDocenteTracking()

    docentes = [d.docente for d in docentes_query.all()]

    # Calcular estadísticas por docente
    docentes_atencion = 0
    docentes_criticos = 0
    porcentajes_calificacion = []

    for docente_name in docentes:
        actividades = db.query(DocenteTracking).filter(
            DocenteTracking.docente == docente_name
        ).all()

        if not actividades:
            continue

        total = len(actividades)
        calificadas = sum(1 for a in actividades if a.calificada is True)
        pct_cal = (calificadas / max(total, 1)) * 100
        porcentajes_calificacion.append(pct_cal)

        if pct_cal < 50:
            docentes_criticos += 1
        elif pct_cal < 80:
            docentes_atencion += 1

    # Promedio general de calificación
    promedio_general = (
        sum(porcentajes_calificacion) / len(porcentajes_calificacion)
        if porcentajes_calificacion
        else 0.0
    )

    return ResumenDocenteTracking(
        total_docentes=total_docentes,
        promedio_general_calificacion=round(promedio_general, 1),
        docentes_en_atencion=docentes_atencion,
        docentes_criticos=docentes_criticos,
    )
