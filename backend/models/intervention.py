from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Intervention(Base):
    __tablename__ = "interventions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), index=True)
    monitor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    monitor_nombre = Column(String, nullable=True)   # denormalized for history display

    # Fields matching GuardarMonitoreoEnReporte()
    carrera = Column(String, nullable=True)
    medio = Column(String, nullable=True)            # WhatsApp / Llamada / Email / etc
    motivo = Column(String, nullable=True)           # Bajo rendimiento / Inactividad / etc
    estado = Column(String, nullable=True)           # Activo / SNA / Retirado / etc
    asignatura = Column(String, nullable=True)
    docente = Column(String, nullable=True)
    observacion = Column(Text, nullable=True)
    periodo = Column(String, nullable=True, index=True)  # P67, P68, etc.

    # Additional web-app fields
    resultado = Column(String, nullable=True)        # Contactado / No contestó / etc
    requiere_seguimiento = Column(String, nullable=True)  # "si" / "no"

    # Derivación a Bienestar Estudiantil (Fase 4)
    derivar_bienestar = Column(Boolean, nullable=True, default=False)
    tipo_evento_critico = Column(String, nullable=True)   # Enfermedad / Pérdida laboral / etc
    reporte_bienestar = Column(Text, nullable=True)       # Descripción detallada del caso
    email_enviado = Column(Boolean, nullable=True, default=False)

    # [GAP-F5-01] Snapshot de indicadores al momento de la intervención
    # Permite medir impacto: comparar estos valores con los actuales del estudiante
    snapshot_compromiso = Column(Float, nullable=True)
    snapshot_dias_sin_acceso = Column(Integer, nullable=True)
    snapshot_porcentaje_tareas = Column(Float, nullable=True)
    snapshot_prob_desercion = Column(Float, nullable=True)
    snapshot_prob_reprobacion = Column(Float, nullable=True)
    snapshot_nivel_riesgo = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("Student", back_populates="interventions")
    monitor = relationship("User")
