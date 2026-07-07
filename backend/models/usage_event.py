"""
Telemetría de USO — capa AISLADA de las tablas de dominio (chore/estandar-casa, punto 7).

Regla LOPDP: NO se guarda PII directa. El actor se identifica por HMAC (actor_hash),
nunca por correo/cédula/nombre. Los metadatos (props) son no-PII.

Esta tabla no tiene FKs a tablas de dominio ni expone identidades: vive sola para
que la analítica de uso no se mezcle con la de dominio.
"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, Index, func

from ..database import Base

# Set cerrado de eventos permitidos (evita free-text y drift):
EVENTOS = frozenset({
    "login",
    "dashboard_view",
    "ficha360_view",
    "alerta_vista",
    "recomendacion_vista",
    "intervencion_creada",
    "intervencion_cerrada",
    "export_generado",
})


class UsageEvent(Base):
    __tablename__ = "usage_events"
    __table_args__ = (
        Index("idx_usage_event_ts", "event", "ts"),
    )

    id = Column(Integer, primary_key=True, index=True)
    ts = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    event = Column(String(40), index=True, nullable=False)   # uno de EVENTOS
    actor_hash = Column(String(64), index=True, nullable=True)  # HMAC(user_id) — NO PII
    role = Column(String(20), nullable=True)
    tenant = Column(String(64), index=True, nullable=True)
    props = Column(JSON, nullable=True)   # solo no-PII (ids opacos, conteos)
