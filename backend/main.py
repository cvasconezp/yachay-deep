"""
Yachay Deep — API Backend
FastAPI application entry point
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from slowapi.errors import RateLimitExceeded
import logging

from .config import settings, validate_security_settings
from .database import create_tables, upgrade_tables
from .auth.routes import router as auth_router
from .routes.students import router as students_router
from .routes.interventions import router as interventions_router
from .routes.dashboard import router as dashboard_router
from .routes.admin import router as admin_router
from .routes.export import router as export_router
from .routes.courses import router as courses_router
from .routes.analytics import router as analytics_router
from .routes.predictions import router as predictions_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: crear tablas y admin por defecto si no existen."""
    logger.info("Iniciando Yachay Deep API...")
    validate_security_settings()
    create_tables()
    upgrade_tables()   # agrega columnas nuevas sin borrar datos
    _create_default_admin()
    logger.info("✅ Base de datos lista")
    yield
    logger.info("Apagando Yachay Deep API")


def _create_default_admin():
    """Crea o actualiza el usuario admin según las variables de entorno."""
    from .database import SessionLocal
    from .models.user import User, UserRole
    from .auth.jwt import hash_password
    import os

    admin_email = os.environ.get("ADMIN_EMAIL")
    admin_pass = os.environ.get("ADMIN_PASSWORD")

    if not admin_email or not admin_pass:
        if not settings.DEBUG:
            logger.warning(
                "⚠️ ADMIN_EMAIL y ADMIN_PASSWORD no configurados. "
                "No se creará usuario admin por defecto en producción."
            )
            return
        # Solo en DEBUG: usar credenciales de desarrollo
        admin_email = admin_email or "admin@yachay.edu.ec"
        admin_pass = admin_pass or "dev12345"
        logger.warning("⚠️ Usando credenciales admin de desarrollo (DEBUG=True).")

    db = SessionLocal()
    try:
        # Si ya existe el usuario con ese email, no hacer nada
        existing = db.query(User).filter(User.email == admin_email).first()
        if existing:
            logger.info(f"Usuario admin ya existe: {admin_email}")
            return

        # Si existe algún admin (con email diferente), actualizar sus credenciales
        admin = db.query(User).filter(User.role == UserRole.admin).first()
        if admin:
            admin.email = admin_email
            admin.hashed_password = hash_password(admin_pass)
            admin.is_active = True
            db.commit()
            logger.info(f"Usuario admin actualizado: {admin_email}")
        else:
            # No existe ningún admin → crear uno nuevo
            new_admin = User(
                email=admin_email,
                nombre="Administrador",
                hashed_password=hash_password(admin_pass),
                role=UserRole.admin,
                is_active=True,
            )
            db.add(new_admin)
            db.commit()
            logger.info(f"Usuario admin creado: {admin_email}")
    finally:
        db.close()


app = FastAPI(
    title="Yachay Deep API",
    description="Sistema de monitoreo académico — Decision Support System para analítica educativa",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Rate limiting — registrar el state en la app para slowapi
from .auth.routes import limiter
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Demasiados intentos. Intente de nuevo en un momento."},
    )

# CORS — permite el frontend en Vercel
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Routers
app.include_router(auth_router)
app.include_router(students_router)
app.include_router(interventions_router)
app.include_router(dashboard_router)
app.include_router(admin_router)
app.include_router(export_router)
app.include_router(courses_router)
app.include_router(analytics_router)
app.include_router(predictions_router)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if not settings.DEBUG:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/health")
def health_check():
    return {"status": "ok"}


