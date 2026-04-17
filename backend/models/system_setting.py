"""
SystemSetting — tabla key-value para configuración persistente del sistema.
Almacena valores como la cookie AVAC que deben sobrevivir redeployments.
"""
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime, timezone

from ..database import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False, index=True)
    value = Column(String, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    @classmethod
    def get(cls, db, key: str, default=None) -> str | None:
        """Lee un valor de configuración."""
        row = db.query(cls).filter(cls.key == key).first()
        return row.value if row else default

    @classmethod
    def set(cls, db, key: str, value: str):
        """Crea o actualiza un valor de configuración."""
        row = db.query(cls).filter(cls.key == key).first()
        if row:
            row.value = value
            row.updated_at = datetime.now(timezone.utc)
        else:
            row = cls(key=key, value=value)
            db.add(row)
        db.commit()
        return row
