import json
from typing import Any, Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings


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
    # CORS_ORIGINS: set via env as JSON array ["url"] or comma-separated "url1,url2"
    # Default covers local dev + Vercel production
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "https://yachay-deep.vercel.app"]

    @model_validator(mode="before")
    @classmethod
    def parse_cors_origins_from_env(cls, values: Any) -> Any:
        """
        pydantic-settings raises SettingsError before field_validators run when
        a list[str] field receives a non-JSON string.  model_validator(mode='before')
        fires first, so we pre-process the raw env string here.
        """
        if isinstance(values, dict):
            cors = values.get("CORS_ORIGINS")
            if isinstance(cors, str):
                cors = cors.strip()
                try:
                    parsed = json.loads(cors)
                    values["CORS_ORIGINS"] = parsed if isinstance(parsed, list) else [str(parsed)]
                except json.JSONDecodeError:
                    values["CORS_ORIGINS"] = [o.strip() for o in cors.split(",") if o.strip()]
        return values

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
