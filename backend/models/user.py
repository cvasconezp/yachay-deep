from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, JSON
from sqlalchemy.sql import func
import enum
from ..database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    coordinador = "coordinador"
    docente = "docente"
    monitor = "monitor"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    nombre = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.monitor, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    permissions = Column(JSON, nullable=True, default=None, comment="Lista de tabs permitidos, ej: ['dashboard','alertas','ficha']")
    pin_hash = Column(String, nullable=True, comment="BCrypt hash del PIN de 6 dígitos para desbloqueo rápido")
    tenant = Column(String, nullable=True, comment="Código de institución (subdominio) del usuario, ej: 'ups', 'demo'. NULL = acceso global (admins)")
    # [WF3] 2FA (TOTP)
    totp_secret = Column(String, nullable=True, comment="Secreto base32 TOTP")
    totp_enabled = Column(Boolean, default=False, nullable=False, server_default="false", comment="2FA activado")
    recovery_codes = Column(JSON, nullable=True, comment="Lista de hashes argon2 de códigos de recuperación de un solo uso")
    # [SEC-03] Bloqueo por PIN enforced en servidor
    pin_locked = Column(Boolean, default=False, nullable=False, server_default="false", comment="Sesión bloqueada por inactividad; requiere verificar PIN")
