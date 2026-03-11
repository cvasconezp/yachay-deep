from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from sqlalchemy.sql import func
from ..database import Base


class ScrapingRun(Base):
    __tablename__ = "scraping_runs"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String, nullable=False)           # "ingresos_avac" / "estado_tareas" / "calificaciones" / "full"
    status = Column(String, default="running")      # running / success / error / partial
    cursos_procesados = Column(Integer, default=0)
    cursos_error = Column(Integer, default=0)
    registros_insertados = Column(Integer, default=0)
    errores = Column(JSON, nullable=True)           # list of {curso, error}
    triggered_by = Column(String, nullable=True)    # "github_actions" / "admin_manual" / user email
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    log_output = Column(Text, nullable=True)
