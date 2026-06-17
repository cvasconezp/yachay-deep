from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Date, Float, Boolean, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class TaskSubmission(Base):
    __tablename__ = "task_submissions"
    __table_args__ = (
        Index("idx_task_periodo", "periodo"),
        Index("idx_task_student_periodo", "student_id", "periodo"),
        Index("idx_task_snapshot", "periodo", "snapshot_date"),
        Index("idx_task_student_snapshot", "student_id", "periodo", "snapshot_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, nullable=True, index=True, comment="[WF5] código de institución; NULL = global/single-tenant")
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), index=True)
    codigo_curso = Column(String, index=True, nullable=False)
    periodo = Column(String, nullable=True)             # "P67", "P68" — identifies which semester
    snapshot_date = Column(Date, nullable=True, index=True)  # date of ETL snapshot (for historical trends)
    unidad = Column(String, nullable=True)              # "1", "2", "3", "4"
    estado = Column(String, nullable=True)              # "Enviado para calificar Calificado" etc
    calificacion_texto = Column(String, nullable=True)  # "15,00 / 15,00"
    calificacion = Column(Float, nullable=True)         # parsed: 15.0
    calificacion_maxima = Column(Float, nullable=True)  # parsed: 15.0
    entregada = Column(Boolean, default=False)
    calificada = Column(Boolean, default=False)
    retrasada = Column(Boolean, default=False)
    fecha_entrega = Column(DateTime(timezone=True), nullable=True)
    fecha_calificacion = Column(DateTime(timezone=True), nullable=True)
    archivos_enviados = Column(String, nullable=True)
    comentarios_retroalimentacion = Column(String, nullable=True)
    calificacion_final = Column(Float, nullable=True)
    total_curso = Column(Float, nullable=True)
    total_entregas = Column(Integer, nullable=True)
    total_calificadas = Column(Integer, nullable=True)
    fecha_extraccion = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("Student", back_populates="task_submissions")
