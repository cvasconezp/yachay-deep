"""
[GAP-F4-02] Persistencia de recomendaciones generadas.

Permite rastrear qué recomendaciones se generaron, cuándo, y si se actuó
sobre ellas (vinculación con intervención).
"""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, Boolean
from sqlalchemy.sql import func
from ..database import Base


class RecommendationLog(Base):
    __tablename__ = "recommendation_logs"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), index=True)

    # Datos de la recomendación generada
    categoria = Column(String, nullable=False)        # inactividad, desercion, reprobacion, etc.
    prioridad = Column(String, nullable=False)         # urgente, importante, sugerida
    accion = Column(String, nullable=False)
    motivo = Column(String, nullable=True)
    medio = Column(String, nullable=True)
    destinatario = Column(String, nullable=True)

    # Contexto al momento de generar
    prob_desercion = Column(Float, nullable=True)
    prob_reprobacion = Column(Float, nullable=True)

    # Trazabilidad
    fue_ejecutada = Column(Boolean, default=False)     # ¿Se creó una intervención a partir de esta?
    intervention_id = Column(Integer, ForeignKey("interventions.id"), nullable=True)
    ejecutada_por = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
