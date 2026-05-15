"""
AlertEvent — eventos de alerta generados automáticamente basados en umbrales.
Tipos: inactividad, compromiso_bajo, nota_cero, tareas_bajas, calificacion_docente_pendiente
Severidad: critico, alto, medio
"""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class AlertEvent(Base):
    """Evento de alerta para estudiante."""
    __tablename__ = "alert_events"

    id = Column(Integer, primary_key=True, index=True)

    # Referencia al estudiante
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), index=True)

    # Tipo de alerta
    tipo = Column(String, nullable=False, index=True)  # inactividad, compromiso_bajo, nota_cero, tareas_bajas, segunda_matricula, tercera_matricula, deterioro_progresivo

    # Curso específico (para alertas por asignatura)
    codigo_curso = Column(String, nullable=True, index=True)

    # Mensaje descriptivo
    mensaje = Column(Text, nullable=True)

    # Severidad del evento
    severidad = Column(String, nullable=False)  # critico, alto, medio

    # Estado de lectura
    leido = Column(Boolean, nullable=False, default=False, index=True)
    leido_por = Column(String, nullable=True)  # usuario que marcó como leído
    leido_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationship
    student = relationship("Student", backref="alert_events")
