from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Grade(Base):
    __tablename__ = "grades"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), index=True)
    asignatura = Column(String, index=True, nullable=False)
    carrera = Column(String, nullable=True)
    grupo = Column(String, nullable=True)
    docente = Column(String, nullable=True)
    nota_final = Column(Float, nullable=True)
    periodo = Column(String, nullable=True)
    sede = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("Student", back_populates="grades")
