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
    nota_cierre = Column(Text, nullable=True)        # Notas de resolución/cierre

    # Derivaciones (Fase 4+)
    derivar_bienestar = Column(Boolean, nullable=True, default=False)
    derivar_financiero = Column(Boolean, nullable=True, default=False)
    derivar_coordinacion = Column(Boolean, nullable=True, default=False)
    derivar_docente = Column(Boolean, nullable=True, default=False)
    tipo_evento_critico = Column(String, nullable=True)   # Enfermedad / Pérdida laboral / etc
    reporte_bienestar = Column(Text, nullable=True)       # Descripción detallada del caso
    reporte_derivacion = Column(Text, nullable=True)      # Nota para otras derivaciones
    email_enviado = Column(Boolean, nullable=True, default=False)

    # [GAP-F5-01] Snapshot de indicadores al momento de la intervención
    # Permite medir impacto: comparar estos valores con los actuales del estudiante
    snapshot_compromiso = Column(Float, nullable=True)
    snapshot_dias_sin_acceso = Column(Integer, nullable=True)
    snapshot_porcentaje_tareas = Column(Float, nullable=True)
    snapshot_prob_desercion = Column(Float, nullable=True)
    snapshot_prob_reprobacion = Column(Float, nullable=True)
    snapshot_nivel_riesgo = Column(String, nullable=True)

    # Workflow de intervención (Fase 3 — Épica 3.1)
    estado_workflow = Column(String, nullable=True, default="pendiente", index=True)  # pendiente/en_progreso/contactado/resuelto/escalado/sin_respuesta/cerrado
    asignado_a = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)   # monitor asignado (Épica 3.2)
    asignado_nombre = Column(String, nullable=True)          # denormalized
    fecha_asignacion = Column(DateTime(timezone=True), nullable=True)
    fecha_limite = Column(DateTime(timezone=True), nullable=True)       # SLA deadline (Épica 3.3)
    fecha_contacto = Column(DateTime(timezone=True), nullable=True)     # cuándo se contactó al estudiante
    fecha_resolucion = Column(DateTime(timezone=True), nullable=True)   # cuándo se resolvió
    escalado = Column(Boolean, default=False)                           # fue escalada
    escalado_a = Column(String, nullable=True)                          # a quién se escaló
    prioridad = Column(Integer, nullable=True, default=2)               # 1=urgente, 2=normal, 3=baja
    overdue = Column(Boolean, default=False)                            # SLA vencido

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("Student", back_populates="interventions")
    monitor = relationship("User", foreign_keys=[monitor_id])
