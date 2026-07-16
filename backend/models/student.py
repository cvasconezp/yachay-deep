from sqlalchemy import Column, Integer, String, DateTime, Float, Text, Date, Boolean, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base
from ..crypto import EncryptedString


class Student(Base):
    __tablename__ = "students"
    # [PERF-02] Índices compuestos para queries frecuentes del dashboard y analytics
    __table_args__ = (
        Index("idx_student_risk_level", "nivel_riesgo"),
        Index("idx_student_carrera_riesgo", "carrera", "nivel_riesgo"),
    )

    id = Column(Integer, primary_key=True, index=True)
    cedula = Column("cedula_cif", EncryptedString, nullable=True)  # [2.3a] lee/escribe cifrado; búsqueda por cedula_bidx
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
    # OJO con la semántica de estos dos campos: NO son lo mismo.
    #   dias_sin_acceso      = MÁXIMO entre asignaturas = "la asignatura más descuidada".
    #   dias_desde_ultimo_acceso = MÍNIMO = "cuándo pisó AVAC por última vez".
    # Llamar "Días sin AVAC: 99d" al máximo es FALSO si el estudiante entró hace 2 días a
    # otra asignatura. El mínimo ya se calculaba en el ETL y se descartaba sin guardarse.
    dias_sin_acceso = Column(Integer, nullable=True)   # MÁXIMO entre asignaturas
    dias_desde_ultimo_acceso = Column(Integer, nullable=True)  # MÍNIMO: último acceso real a AVAC
    porcentaje_tareas = Column(Float, nullable=True)   # % tareas entregadas
    promedio_calificaciones = Column(Float, nullable=True)

    # Residence (reporte.xlsx > DatosEspecificos)
    pais = Column("pais_cif", EncryptedString, nullable=True)       # país de domicilio (cifrado)
    provincia = Column("provincia_cif", EncryptedString, nullable=True)  # provincia (cifrado)
    ciudad = Column("ciudad_cif", EncryptedString, nullable=True)   # ciudad / cantón (cifrado)
    parroquia = Column("parroquia_cif", EncryptedString, nullable=True)  # parroquia (cifrado)
    barrio = Column("barrio_cif", EncryptedString, nullable=True)   # barrio o comunidad (cifrado)

    # Personal demographics (from 2505060014_reporte.xlsx)
    fecha_nacimiento = Column(Date, nullable=True)
    genero = Column("genero_cif", EncryptedString, nullable=True)
    autoidentificacion_etnica = Column("autoidentificacion_etnica_cif", EncryptedString, nullable=True)

    # Academic group from institutional reporte (NOMBRE_GRUPO → "3")
    grupo = Column(String, nullable=True)

    # ML predictions (Phase 2)
    prob_desercion = Column(Float, nullable=True)          # 0.0-1.0
    prob_reprobacion = Column(Float, nullable=True)        # 0.0-1.0
    prediccion_updated_at = Column(DateTime, nullable=True)

    # Tercera matrícula (oyente condicionado)
    es_tercera_matricula = Column(Boolean, default=False, nullable=False, server_default="false")

    # Score de recuperabilidad (Épica 1.4)
    score_recuperabilidad = Column(Float, nullable=True)       # 0-100
    nivel_recuperabilidad = Column(String, nullable=True)      # alto / medio / bajo

    # ── Retiro: congela la foto del estudiante ──────────────────────────────
    # Un retirado seguía sumando días sin acceso mecánicamente, generando alertas y
    # contando como intervención "no exitosa" para siempre — nunca iba a mejorar, porque
    # ya no está. Eso contaminaba las métricas de impacto y llenaba de ruido a los
    # monitores. Al marcar el retiro se congelan los indicadores del momento.
    retirado = Column(Boolean, default=False, nullable=False, server_default="false", index=True)
    fecha_retiro = Column(DateTime(timezone=True), nullable=True)
    motivo_retiro = Column(String, nullable=True)
    # Indicadores en el instante del retiro (a partir de aquí no se actualizan)
    retiro_snapshot_dias_sin_acceso = Column(Integer, nullable=True)
    retiro_snapshot_compromiso = Column(Float, nullable=True)
    retiro_snapshot_porcentaje_tareas = Column(Float, nullable=True)
    retiro_snapshot_nivel_riesgo = Column(String, nullable=True)

    # Metadata
    periodo = Column(String, nullable=True)            # e.g. "2026-1"
    estado_matricula = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # ── [Cifrado en reposo — Fase 2 Expand] ──────────────────────────────────
    # Columnas cifradas (texto Fernet) + blind index (HMAC hex) para PII.
    # Se llenan por el listener de doble escritura (backend/crypto_sync.py).
    # NOTA: son columnas de texto planas a proposito; el ciphertext se asigna
    # ya cifrado. En la fase Contract el atributo canonico pasara a EncryptedString.
    cedula_bidx = Column(String(64), nullable=True, index=True)
    nombre_cif = Column(Text, nullable=True)
    nombre_bidx = Column(String(64), nullable=True, index=True)
    correo_cif = Column(Text, nullable=True)
    correo_bidx = Column(String(64), nullable=True, index=True)
    correo_institucional_cif = Column(Text, nullable=True)
    correo_institucional_bidx = Column(String(64), nullable=True, index=True)
    telefono_cif = Column(Text, nullable=True)
    whatsapp_cif = Column(Text, nullable=True)
    fecha_nacimiento_cif = Column(Text, nullable=True)

    # Relationships
    avac_accesses = relationship("AvacAccess", back_populates="student", cascade="all, delete-orphan")
    task_submissions = relationship("TaskSubmission", back_populates="student", cascade="all, delete-orphan")
    grades = relationship("Grade", back_populates="student", cascade="all, delete-orphan")
    interventions = relationship("Intervention", back_populates="student", cascade="all, delete-orphan")
    enrollments = relationship("Enrollment", back_populates="student", cascade="all, delete-orphan")
