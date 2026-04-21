"""
CourseConfig — gestión dinámica de cursos AVAC por semestre y bloque.
Reemplaza la lista hardcodeada de códigos en los scripts de scraping.
El admin actualiza esta tabla al inicio de cada semestre.
"""
from datetime import datetime, timezone as tz
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float
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
    correo_docente = Column(String, nullable=True)              # correo del docente
    semestre = Column(String, nullable=True, index=True)        # ej: "2026-1"
    bloque = Column(String, nullable=True, index=True)          # "1", "2", o "ambos"

    # Nivel académico: semestre/año del plan de estudios (1–8)
    # Ejemplo: NIVEL=7 en ListasASIG de Excel → estudiantes de 7mo semestre
    nivel = Column(Integer, nullable=True, index=True)

    # Grupo / sección dentro de la asignatura (número extraído de NOMBRE_GRUPO)
    # "Grupo - 3 (Educación Intercultural Bilingue)" → grupo="3"
    # Diferente al nivel académico: grupo es la sección del curso, no el año.
    grupo = Column(String, nullable=True)                       # ej: "1", "3", "16"

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

    # Calendario académico: fechas de entrega y paso de notas (JSON)
    # Formato: [{"fecha": "2026-04-19", "tipo": "entrega", "label": "Entrega act. 1"}, ...]
    calendario_academico = Column(String, nullable=True)

    # Umbrales académicos configurables (con defaults sensatos)
    umbral_nota_aprobacion = Column(Float, default=70.0)         # nota mínima para aprobar
    umbral_dias_inactividad = Column(Integer, default=14)        # días sin acceso → inactivo
    umbral_tareas_minimo = Column(Float, default=50.0)           # % mínimo de tareas entregadas
    umbral_compromiso_minimo = Column(Float, default=0.4)        # índice compromiso mínimo

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    @property
    def fecha_fin_actual(self) -> datetime | None:
        """Fecha de fin del bloque activo (o del último bloque con fecha)."""
        if self.bloque_actual == "2" and self.bloque2_fin:
            return self.bloque2_fin
        if self.bloque_actual == "1" and self.bloque1_fin:
            return self.bloque1_fin
        return self.bloque2_fin or self.bloque1_fin

    @property
    def semestre_finalizado(self) -> bool:
        """True si la fecha actual supera la fecha de fin del bloque activo."""
        fin = self.fecha_fin_actual
        if fin is None:
            return False  # sin fechas configuradas, asumir activo
        now = datetime.now(tz.utc)
        if fin.tzinfo is None:
            fin = fin.replace(tzinfo=tz.utc)
        return now > fin
