import json
from typing import Any, Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./yachay.db"  # dev default; Railway sets PostgreSQL
    DEMO_DATABASE_URL: Optional[str] = None  # separate DB for demo tenant

    # JWT
    SECRET_KEY: str = "change-this-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30   # [WF4] access corto; renovación vía refresh token
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30     # [WF4] vida del refresh token
    REQUIRE_ADMIN_2FA: bool = False  # [WF3] si True, los admin deben tener 2FA activo para usar /admin/*
    REQUIRE_2FA: bool = False        # [WF3] si True, TODOS los usuarios deben tener 2FA activo (enrolamiento forzado)

    # AVAC scraping credentials (stored as Railway/GitHub env vars)
    AVAC_USERNAME: Optional[str] = None
    AVAC_PASSWORD: Optional[str] = None
    AVAC_TOTP_SECRET: Optional[str] = None   # secret base32 de la app autenticadora
    AVAC_SESSION_COOKIE: Optional[str] = None  # MoodleSession cookie for direct access (bypasses SSO)
    AVAC_BASE_URL: str = "https://avac.ups.edu.ec/grado68"

    # Data paths (for ETL pipeline - where CSVs are stored)
    DATA_PATH_INGRESOS: str = "./data/IngresosAVAC"
    DATA_PATH_TAREAS: str = "./data/Tareas"
    DATA_PATH_CALIFICACIONES: str = "./data/calificaciones.csv"
    # Carpeta con los archivos TableauHistorico (Detalle de Calificaciones _data(P6X).csv)
    # Calificaciones institucionales históricas por período (P60–P67+)
    DATA_PATH_CALIFICACIONES_HISTORICO: str = "./data/TableauHistorico"
    # Carpeta con los archivos *_reporte.xlsx (datos personales de estudiantes)
    DATA_PATH_REPORTE: str = "./data/Reportes"
    # Carpeta con los archivos DatosEspecificos*.xlsx (formulario Microsoft Forms EIB)
    # Contiene: nivel académico, sede, residencia, whatsapp, etnia, lengua, trabajo
    DATA_PATH_DATOS_ESPECIFICOS: str = "./data/DatosEspecificos"
    # Carpeta con archivos de Prácticas Preprofesionales
    # - Formularios Practica P*.xlsx: datos de estudiantes y escuelas asignadas
    # - Escuelas Bilingues SEIBE*.xlsx: catálogo de escuelas con ubicaciones
    DATA_PATH_PRACTICAS: str = "./data/Practicas"
    # Carpeta con reportes de terceras matrículas (oyentes condicionados)
    DATA_PATH_TERCERAS_MATRICULAS: str = "./data/TercerasMatriculas"

    # Email (SMTP para derivaciones a Bienestar Estudiantil)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    BIENESTAR_EMAIL: Optional[str] = None  # destinatario del departamento
    FRONTEND_URL: str = "https://yachaydeep.com"

    # App
    APP_NAME: str = "Yachay Deep"
    DEBUG: bool = False

    # [SEC-02] Cookie config for HttpOnly JWT
    COOKIE_DOMAIN: Optional[str] = ".yachaydeep.com"  # shared across *.yachaydeep.com (works because Vercel proxy makes it same-origin)
    COOKIE_SECURE: bool = True                    # False for localhost dev
    COOKIE_SAMESITE: str = "lax"                   # "lax" is safe since Vercel proxies API requests (same-origin)

    # GitHub API — para disparar scraping desde la UI sin esperar al cron
    GITHUB_TOKEN: Optional[str] = None
    GITHUB_REPO: str = "cvasconezp/yachay-deep"
    GITHUB_WORKFLOW: str = "daily_scraping.yml"
    # Sentry DSN (optional, for error monitoring)
    SENTRY_DSN: Optional[str] = None
    # CORS_ORIGINS: set via env as JSON array ["url"] or comma-separated "url1,url2"
    # Default covers local dev + Vercel production
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "https://yachay-deep.vercel.app",
        "https://yachaydeep.com",
    ]
    # Wildcard domain: any subdomain of this domain is auto-allowed for CORS
    # e.g. ".yachaydeep.com" allows ups.yachaydeep.com, kapak.yachaydeep.com, etc.
    CORS_WILDCARD_DOMAIN: Optional[str] = ".yachaydeep.com"

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

_DEFAULT_SECRET_KEY = "change-this-in-production-use-openssl-rand-hex-32"


def validate_security_settings():
    """Valida configuraciones de seguridad. Falla en producción si son inseguras."""
    import logging
    _logger = logging.getLogger(__name__)
    if settings.SECRET_KEY == _DEFAULT_SECRET_KEY:
        if not settings.DEBUG:
            raise RuntimeError(
                "SECRET_KEY usa el valor por defecto y DEBUG=False. "
                "Esto permite forjar tokens JWT. Genera una clave segura con: "
                "openssl rand -hex 32  y configúrala como variable de entorno."
            )
        _logger.warning(
            "⚠️ SECRET_KEY usa el valor por defecto. Los tokens JWT son predecibles. "
            "Genera una clave segura con: openssl rand -hex 32"
        )
