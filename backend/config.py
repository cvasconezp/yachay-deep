import json
from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./yachay.db"  # dev default; Railway sets PostgreSQL

    # JWT
    SECRET_KEY: str = "change-this-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours

    # AVAC scraping credentials (stored as Railway/GitHub env vars)
    AVAC_USERNAME: Optional[str] = None
    AVAC_PASSWORD: Optional[str] = None
    AVAC_TOTP_SECRET: Optional[str] = None   # secret base32 de la app autenticadora
    AVAC_BASE_URL: str = "https://avac.ups.edu.ec/grado67"

    # Data paths (for ETL pipeline - where CSVs are stored)
    DATA_PATH_INGRESOS: str = "./data/IngresosAVAC"
    DATA_PATH_TAREAS: str = "./data/Tareas"
    DATA_PATH_CALIFICACIONES: str = "./data/calificaciones.csv"

    # App
    APP_NAME: str = "Yachay Deep"
    DEBUG: bool = False
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "https://yachay-deep.vercel.app"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Accept JSON array, comma-separated string, or plain URL string."""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            v = v.strip()
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
                return [str(parsed)]
            except json.JSONDecodeError:
                return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
