from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Grade(Base):
    __tablename__ = "grades"
    # [PERF-02] Índices para queries de analytics (asignaturas, docentes, períodos)
    __table_args__ = (
        Index("idx_grade_periodo", "periodo"),
        Index("idx_grade_docente", "docente"),
        Index("idx_grade_student_periodo", "student_id", "periodo"),
        Index("idx_grade_asig_docente", "asignatura", "docente"),
    )

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), index=True)
    asignatura = Column(String, index=True, nullable=False)
    carrera = Column(String, nullable=True)
    grupo = Column(String, nullable=True)
    docente = Column(String, nullable=True)
    nota_final = Column(Float, nullable=True)
    periodo = Column(String, nullable=True)
    sede = Column(String, nullable=True)
    numero_repitencias = Column(Integer, nullable=True)
    nivel = Column(Integer, nullable=True)          # academic level of the subject (1-8)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("Student", back_populates="grades")
