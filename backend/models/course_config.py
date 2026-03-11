"""
CourseConfig — gestión dinámica de cursos AVAC por semestre y bloque.
Reemplaza la lista hardcodeada de códigos en los scripts de scraping.
El admin actualiza esta tabla al inicio de cada semestre.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from ..database import Base


class CourseConfig(Base):
    __tablename__ = "course_configs"

    id = Column(Integer, primary_key=True, index=True)
    codigo_avac = Column(String, index=True, nullable=False)    # ej: "395484"
    nombre = Column(String, nullable=True)                      # nombre del curso en AVAC
    asignatura = Column(String, nullable=True)                  # nombre normalizado
    carrera = Column(String, nullable=True, index=True)
    docente = Column(String, nullable=True)
    semestre = Column(String, nullable=True, index=True)        # ej: "2026-1"
    bloque = Column(String, nullable=True, index=True)          # "1", "2", o "ambos"
    grupo = Column(String, nullable=True)

    # Control de activación
    activo = Column(Boolean, default=True, nullable=False)      # false = no scrapar este semestre
    notas = Column(Text, nullable=True)                         # observaciones del admin

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class SemesterConfig(Base):
    """Configuración global del semestre activo y sus fechas de bloque."""
    __tablename__ = "semester_configs"

    id = Column(Integer, primary_key=True, index=True)
    semestre = Column(String, unique=True, nullable=False)      # ej: "2026-1"
    activo = Column(Boolean, default=False)                     # solo uno activo a la vez
    bloque_actual = Column(String, default="1")                 # "1" o "2"

    # Fechas de los bloques para filtrar actividades
    bloque1_inicio = Column(DateTime(timezone=True), nullable=True)
    bloque1_fin = Column(DateTime(timezone=True), nullable=True)
    bloque2_inicio = Column(DateTime(timezone=True), nullable=True)
    bloque2_fin = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
