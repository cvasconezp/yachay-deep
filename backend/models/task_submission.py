from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class TaskSubmission(Base):
    __tablename__ = "task_submissions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), index=True)
    codigo_curso = Column(String, index=True, nullable=False)
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
