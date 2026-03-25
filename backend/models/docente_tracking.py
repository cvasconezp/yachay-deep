"""
DocenteTracking — seguimiento de calificación/retroalimentación docente.
Fuente: Resumen_General del scraping AVAC.
Permite monitorear si los docentes califican a tiempo las actividades.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text
from sqlalchemy.sql import func
from ..database import Base


class DocenteTracking(Base):
    """Estado de calificación de actividades por curso y docente."""
    __tablename__ = "docente_tracking"

    id = Column(Integer, primary_key=True, index=True)

    # Identificación del curso
    codigo_curso = Column(String, index=True, nullable=True)
    nombre_curso = Column(String, nullable=True)

    # Actividad
    actividad = Column(String, nullable=True)
    tipo_actividad = Column(String, nullable=True)     # tarea, quiz, foro, etc.

    # Estado de calificación
    calificada = Column(Boolean, nullable=True)         # True si fue calificada
    fecha_limite = Column(DateTime(timezone=True), nullable=True)
    fecha_calificacion = Column(DateTime(timezone=True), nullable=True)

    # Docente responsable
    docente = Column(String, nullable=True, index=True)

    # Métricas calculadas
    dias_retraso = Column(Float, nullable=True)         # días entre límite y calificación (negativo = a tiempo)

    # Semestre/período
    semestre = Column(String, nullable=True, index=True)

    # Metadata
    fuente = Column(String, nullable=True)              # archivo origen
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
