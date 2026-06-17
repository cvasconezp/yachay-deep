from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, Date, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class AvacAccess(Base):
    __tablename__ = "avac_accesses"
    __table_args__ = (
        Index("idx_avac_periodo", "periodo"),
        Index("idx_avac_student_periodo", "student_id", "periodo"),
        Index("idx_avac_snapshot", "periodo", "snapshot_date"),
        Index("idx_avac_student_snapshot", "student_id", "periodo", "snapshot_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, nullable=True, index=True, comment="[WF5] código de institución; NULL = global/single-tenant")
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), index=True)
    codigo_curso = Column(String, index=True, nullable=False)
    periodo = Column(String, nullable=True)                 # "P67", "P68" — identifies which semester
    snapshot_date = Column(Date, nullable=True, index=True) # date of ETL snapshot (for historical trends)
    nombre_estudiante_avac = Column(String, nullable=True)  # as stored in AVAC
    ultimo_acceso_texto = Column(String, nullable=True)     # "8 días 17 horas"
    dias_sin_acceso = Column(Float, nullable=True)          # parsed numeric value
    estado_avac = Column(String, nullable=True)             # "Activo" / etc
    fecha_extraccion = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("Student", back_populates="avac_accesses")
