from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class AvacAccess(Base):
    __tablename__ = "avac_accesses"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), index=True)
    codigo_curso = Column(String, index=True, nullable=False)
    nombre_estudiante_avac = Column(String, nullable=True)  # as stored in AVAC
    ultimo_acceso_texto = Column(String, nullable=True)     # "8 días 17 horas"
    dias_sin_acceso = Column(Float, nullable=True)          # parsed numeric value
    estado_avac = Column(String, nullable=True)             # "Activo" / etc
    fecha_extraccion = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("Student", back_populates="avac_accesses")
