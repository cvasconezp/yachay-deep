from sqlalchemy import Column, Integer, String, DateTime, Float, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    cedula = Column(String, unique=True, index=True, nullable=True)
    nombre = Column(String, index=True, nullable=True)
    correo = Column(String, index=True, nullable=True)
    correo_institucional = Column(String, index=True, nullable=True)
    telefono = Column(String, nullable=True)
    whatsapp = Column(String, nullable=True)           # WhatsApp (reporte o DatosEspecificos)
    carrera = Column(String, index=True, nullable=True)
    sede = Column(String, nullable=True)               # Centro de apoyo (DatosEspecificos > majority-vote)
    campus = Column(String, nullable=True)

    # Academic level: semester number 1–8 (from DatosEspecificos NIVEL)
    nivel_academico = Column(Integer, nullable=True)   # 1 = primero, 7 = séptimo, etc.

    # Computed risk indicators (updated by ETL)
    nivel_riesgo = Column(String, nullable=True)       # Alto / Medio / Bajo
    indice_compromiso = Column(Float, nullable=True)   # 0.0 - 1.0
    dias_sin_acceso = Column(Integer, nullable=True)   # días desde último acceso AVAC
    porcentaje_tareas = Column(Float, nullable=True)   # % tareas entregadas
    promedio_calificaciones = Column(Float, nullable=True)

    # Residence (reporte.xlsx > DatosEspecificos)
    pais = Column(String, nullable=True)               # país de domicilio
    provincia = Column(String, nullable=True)          # provincia
    ciudad = Column(String, nullable=True)             # ciudad / cantón
    parroquia = Column(String, nullable=True)          # parroquia (solo DatosEspecificos)
    barrio = Column(String, nullable=True)             # barrio o comunidad

    # Metadata
    periodo = Column(String, nullable=True)            # e.g. "2026-1"
    estado_matricula = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    avac_accesses = relationship("AvacAccess", back_populates="student", cascade="all, delete-orphan")
    task_submissions = relationship("TaskSubmission", back_populates="student", cascade="all, delete-orphan")
    grades = relationship("Grade", back_populates="student", cascade="all, delete-orphan")
    interventions = relationship("Intervention", back_populates="student", cascade="all, delete-orphan")
