"""[WF4] Refresh tokens persistidos: permiten revocar, rotar y detectar reuso."""
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.sql import func
from ..database import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("idx_refresh_user", "user_id"),)

    id = Column(String, primary_key=True)  # jti (uuid)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False, nullable=False, server_default="false")
    replaced_by = Column(String, nullable=True)  # jti del token que lo reemplazó (rotación)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
