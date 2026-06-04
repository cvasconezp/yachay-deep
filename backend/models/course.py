from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from ..database import Base


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    codigo_avac = Column(String, unique=True, index=True, nullable=False)
    nombre = Column(String, nullable=True)
    carrera = Column(String, nullable=True)
    docente = Column(String, nullable=True)
    periodo = Column(String, nullable=True)
    grupo = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
