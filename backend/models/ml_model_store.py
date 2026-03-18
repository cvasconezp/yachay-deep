"""
[GAP-F2-02] Persistencia de modelos ML en PostgreSQL.

Almacena modelos entrenados (.joblib) y sus metadatos como BLOBs en la BD,
eliminando la dependencia del filesystem efímero de Railway.
"""
from sqlalchemy import Column, Integer, String, DateTime, LargeBinary, Text
from sqlalchemy.sql import func
from ..database import Base


class MLModelStore(Base):
    __tablename__ = "ml_model_store"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)  # ej: "global_desercion"
    model_data = Column(LargeBinary, nullable=False)                # joblib serializado
    metadata_json = Column(Text, nullable=True)                     # stats JSON para XAI
    created_at = Column(DateTime(timezone=True), server_default=func.now())
