"""
Modelos para el módulo de Prácticas Preprofesionales.

EscuelaPractica: catálogo de instituciones educativas (SEIBE + formularios).
PracticaPreprofesional: asignación de un estudiante a una práctica en una escuela.
"""
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class EscuelaPractica(Base):
    """Institución educativa donde se realizan las prácticas."""
    __tablename__ = "escuelas_practica"

    id = Column(Integer, primary_key=True, index=True)
    amie = Column(String, unique=True, index=True, nullable=False)  # Código AMIE
    nombre = Column(String, nullable=True)

    # Ubicación (cruzada desde SEIBE)
    zona = Column(String, nullable=True)
    provincia = Column(String, nullable=True)
    canton = Column(String, nullable=True)
    parroquia = Column(String, nullable=True)
    direccion = Column(String, nullable=True)

    # Datos del sistema educativo
    distrito = Column(String, nullable=True)
    sistema_educativo = Column(String, nullable=True)  # "Intercultural bilingüe", "Intercultural (hispana)"
    jurisdiccion = Column(String, nullable=True)

    # Datos SEIBE adicionales
    nacionalidad = Column(String, nullable=True)
    lengua_predominante = Column(String, nullable=True)

    # Autoridad
    nombre_autoridad = Column(String, nullable=True)
    cargo_autoridad = Column(String, nullable=True)
    telefono_autoridad = Column(String, nullable=True)

    # Metadata
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    practicas = relationship("PracticaPreprofesional", back_populates="escuela")


class PracticaPreprofesional(Base):
    """Asignación de un estudiante a una práctica preprofesional."""
    __tablename__ = "practicas_preprofesionales"
    __table_args__ = (
        Index("idx_practica_student", "student_id"),
        Index("idx_practica_escuela", "escuela_id"),
        Index("idx_practica_periodo", "periodo"),
    )

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    escuela_id = Column(Integer, ForeignKey("escuelas_practica.id"), nullable=True)

    # Datos del formulario
    nombre_practica = Column(String, nullable=True)  # Ej: "Práctica de Modelos Pedagógicos"
    nivel_practica = Column(String, nullable=True)    # Ej: "4to nivel"
    nivel_y_practica = Column(String, nullable=True)  # Campo original: "4to nivel - Practica de Modelos Pedagógicos"
    centro_apoyo = Column(String, nullable=True)      # Ej: "Cayambe"
    en_mineduc = Column(String, nullable=True)        # "Sí" / "No" (registrada en Mineduc)

    # Datos de la escuela (denormalizados para display rápido)
    amie_escuela = Column(String, nullable=True)
    nombre_escuela = Column(String, nullable=True)
    distrito = Column(String, nullable=True)
    sistema_educativo = Column(String, nullable=True)
    ubicacion_escuela = Column(String, nullable=True)  # Ubicación completa (cantón, parroquia, dirección)

    # Autoridad (del formulario, puede diferir del catálogo SEIBE)
    nombre_autoridad = Column(String, nullable=True)
    cargo_autoridad = Column(String, nullable=True)
    telefono_autoridad = Column(String, nullable=True)

    # Periodo y metadata
    periodo = Column(String, nullable=True)  # Ej: "P68"
    timestamp_formulario = Column(DateTime, nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    student = relationship("Student", backref="practicas_preprofesionales")
    escuela = relationship("EscuelaPractica", back_populates="practicas")
