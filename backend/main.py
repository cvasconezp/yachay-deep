"""
Yachay Deep — API Backend
FastAPI application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from .config import settings
from .database import create_tables
from .auth.routes import router as auth_router
from .routes.students import router as students_router
from .routes.interventions import router as interventions_router
from .routes.dashboard import router as dashboard_router
from .routes.admin import router as admin_router
from .routes.export import router as export_router
from .routes.courses import router as courses_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: crear tablas y admin por defecto si no existen."""
    logger.info("Iniciando Yachay Deep API...")
    create_tables()
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

    admin_email = os.environ.get("ADMIN_EMAIL", "admin@yachay.edu.ec")
    admin_pass = os.environ.get("ADMIN_PASSWORD", "YachayDeep2024!")

    db = SessionLocal()
    try:
        # Si ya existe el usuario con ese email, no hacer nada
        existing = db.query(User).filter(User.email == admin_email).first()
        if existing:
            logger.info(f"✅ Usuario admin ya existe: {admin_email}")
            return

        # Si existe algún admin (con email diferente), actualizar sus credenciales
        admin = db.query(User).filter(User.role == UserRole.admin).first()
        if admin:
            admin.email = admin_email
            admin.hashed_password = hash_password(admin_pass)
            admin.is_active = True
            db.commit()
            logger.info(f"✅ Usuario admin actualizado: {admin_email}")
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
            logger.info(f"✅ Usuario admin creado: {admin_email}")
    finally:
        db.close()


app = FastAPI(
    title="Yachay Deep API",
    description="Sistema de monitoreo académico — Decision Support System para analítica educativa",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — permite el frontend en Vercel
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router)
app.include_router(students_router)
app.include_router(interventions_router)
app.include_router(dashboard_router)
app.include_router(admin_router)
app.include_router(export_router)
app.include_router(courses_router)


@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/debug/fs")
def debug_filesystem():
    """Temporal: diagnóstico de rutas de datos en Railway."""
    import os
    cwd = os.getcwd()
    data_path = os.path.abspath("./data")
    result = {"cwd": cwd, "data_abs": data_path, "dirs": {}}
    for subdir in ["IngresosAVAC", "Tareas"]:
        p = os.path.join(data_path, subdir)
        if os.path.isdir(p):
            files = os.listdir(p)
            result["dirs"][subdir] = {"count": len(files), "sample": files[:3]}
        else:
            result["dirs"][subdir] = {"count": 0, "exists": False}
    return result
