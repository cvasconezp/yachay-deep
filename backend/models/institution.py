"""
Épica 5.4: Multi-tenancy Institucional

Modelo Institution para configuración independiente por institución.
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float
from sqlalchemy import func

from ..database import Base


class Institution(Base):
    """Institución educativa. Base del multi-tenancy."""
    __tablename__ = "institutions"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False, unique=True)
    codigo = Column(String, nullable=True, unique=True)  # código corto
    logo_url = Column(String, nullable=True)
    avac_url = Column(String, nullable=True)              # URL del Moodle/AVAC
    moodle_api_token = Column(String, nullable=True)      # Token API Moodle
    activa = Column(Boolean, default=True)

    # Umbrales personalizables
    umbral_riesgo_alto = Column(Float, default=0.70)
    umbral_riesgo_medio = Column(Float, default=0.40)
    umbral_dias_critico = Column(Integer, default=14)
    umbral_compromiso_bajo = Column(Float, default=0.30)

    # Configuración
    carreras = Column(Text, nullable=True)                # JSON lista de carreras
    periodos_activos = Column(Text, nullable=True)        # JSON lista de períodos

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
