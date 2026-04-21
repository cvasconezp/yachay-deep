"""
Enrollment — asignaturas matriculadas por estudiante desde el reporte institucional.

Cada fila del reporte (estudiante × asignatura) se convierte en un registro Enrollment.
Esto permite mostrar las materias matriculadas en la ficha del estudiante incluso
ANTES de que haya actividad AVAC o calificaciones.
"""
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        Index("idx_enrollment_student_periodo", "student_id", "periodo"),
        Index("idx_enrollment_codigo_grupo", "codigo_grupo"),
    )

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), index=True)

    # Datos de la asignatura (del reporte)
    codigo_grupo = Column(String, nullable=False)          # CODIGO_GRUPO (ej: 408364)
    codigo_asignatura = Column(String, nullable=True)       # CODIGO_ASIGNATURA (ej: C-HU-201)
    asignatura = Column(String, nullable=False)             # ASIGNATURA (ej: METODOLOGÍA DE LA INVESTIGACIÓN)
    tipo_asignatura = Column(String, nullable=True)         # TIPO_ASIGNATURA (COMUN/GENERICA/ESPECIFICA)
    carrera = Column(String, nullable=True)
    nivel = Column(Integer, nullable=True)                  # NIVEL (1-8)
    nombre_grupo = Column(String, nullable=True)            # NOMBRE_GRUPO (ej: GRUPO - 1 (MARKETING...))
    bloque = Column(Integer, nullable=True)                 # BLOQUE (1 o 2)

    # Docente
    docente = Column(String, nullable=True)                 # DOCENTE
    correo_docente = Column(String, nullable=True)          # CORREO_DOCENTE

    # Estado de matrícula
    numero_repitencias = Column(Integer, nullable=True)     # NUMERO_REPITENCIAS
    pagado = Column(String, nullable=True)                  # PAGADO (SI/NO)
    estado_matriculado = Column(String, nullable=True)      # ESTADO_MATRICULADOS

    # Tercera matrícula (oyente condicionado)
    es_tercera_matricula = Column(Boolean, default=False, nullable=False, server_default="false")
    tipo_aprobacion = Column(String, nullable=True)         # CONDICIONADO / None
    estado_solicitud = Column(String, nullable=True)        # Aprobado / Trámite / No aplica

    # Período
    periodo = Column(String, nullable=True, index=True)     # PERIODO (ej: "68")
    fecha_matricula = Column(DateTime(timezone=True), nullable=True)  # FECHA_MATRICULA

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    student = relationship("Student", back_populates="enrollments")
