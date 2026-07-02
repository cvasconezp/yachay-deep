"""
Yachay Deep — API Backend
FastAPI application entry point

[SEC-02] Fase 2: HttpOnly cookies + Sentry integration
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from .config import settings, validate_security_settings
import re as _re

def _is_allowed_origin(origin: str) -> bool:
    """
    Check if origin is allowed: either in the explicit list or matches
    the wildcard subdomain pattern (e.g. *.yachaydeep.com).
    """
    if not origin:
        return False
    if origin in settings.CORS_ORIGINS:
        return True
    wildcard = settings.CORS_WILDCARD_DOMAIN
    if wildcard and origin.startswith("https://") and origin.endswith(wildcard):
        # Ensure the subdomain part is valid (no dots = single level)
        subdomain = origin[len("https://"):-len(wildcard)]
        if subdomain and _re.match(r"^[a-zA-Z0-9-]+$", subdomain):
            return True
    return False


# ── Sentry (opcional) ──
if settings.SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            traces_sample_rate=0.2,
            environment="production" if not settings.DEBUG else "development",
        )
    except ImportError:
        logging.getLogger(__name__).warning("sentry-sdk no instalado. pip install sentry-sdk[fastapi]")
from .database import create_tables, upgrade_tables
from . import crypto_sync  # noqa: F401  registra listeners de cifrado (Fase 2)
from .auth.routes import router as auth_router
from .routes.students import router as students_router
from .routes.interventions import router as interventions_router
from .routes.dashboard import router as dashboard_router
from .routes.admin import router as admin_router
from .routes.export import router as export_router
from .routes.courses import router as courses_router
from .routes.analytics import router as analytics_router
from .routes.predictions import router as predictions_router
from .routes.alerts import router as alerts_router
from .routes.workqueue import router as workqueue_router
from .routes.workflow import router as workflow_router
from .routes.ml_advanced import router as ml_advanced_router
from .routes.institutions import router as institutions_router
from .routes.demo_seed import router as demo_seed_router

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
    _cleanup_stuck_etl_runs()
    _load_persistent_settings()
    _ensure_semester_calendar()
    logger.info("✅ Base de datos lista")
    yield
    logger.info("Apagando Yachay Deep API")


def _cleanup_stuck_etl_runs():
    """Marca como 'failed' cualquier ETL run que quedó en 'running' de un reinicio anterior."""
    from .database import SessionLocal
    from .models.scraping_run import ScrapingRun
    from datetime import datetime, timezone

    db = SessionLocal()
    try:
        stuck = db.query(ScrapingRun).filter(ScrapingRun.status == "running").all()
        for run in stuck:
            run.status = "failed"
            run.finished_at = datetime.now(timezone.utc)
            run.log_output = (run.log_output or "") + "\n[STARTUP] Marcado como failed: el servidor reinició mientras el ETL estaba en ejecución."
        if stuck:
            db.commit()
            logger.warning(f"⚠️ {len(stuck)} ETL run(s) atascados marcados como 'failed' tras reinicio")
    except Exception as e:
        # [BUG-04] FIX: manejo explícito de excepciones con rollback
        logger.error(f"❌ Error limpiando ETL runs atascados: {e}")
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def _load_persistent_settings():
    """Carga configuraciones persistentes de la BD a memoria/env (ej. cookie AVAC)."""
    from .database import SessionLocal
    from .models.system_setting import SystemSetting
    import os

    db = SessionLocal()
    try:
        cookie = SystemSetting.get(db, "avac_session_cookie")
        if cookie:
            os.environ["AVAC_SESSION_COOKIE"] = cookie
            settings.AVAC_SESSION_COOKIE = cookie
            logger.info("🍪 Cookie AVAC cargada desde BD (%s...%s)", cookie[:6], cookie[-4:])
        else:
            logger.info("🍪 No hay cookie AVAC guardada en BD")
    except Exception as e:
        logger.warning(f"⚠️ Error cargando settings persistentes: {e}")
    finally:
        db.close()


def _ensure_semester_calendar():
    """
    Asegura que el SemesterConfig activo tenga el calendario académico cargado.
    Si no tiene calendario, carga el de P68 (abril-julio 2026).
    """
    import json
    from .database import SessionLocal
    from .models.course_config import SemesterConfig

    CALENDARIO_P68 = [
        # Primer bimestre
        {"fecha": "2026-04-06", "tipo": "inicio_bloque", "label": "Inicio primer bimestre"},
        {"fecha": "2026-04-19", "tipo": "entrega", "label": "Entrega actividades 1"},
        {"fecha": "2026-05-03", "tipo": "entrega", "label": "Entrega actividades 2"},
        {"fecha": "2026-05-17", "tipo": "entrega", "label": "Entrega actividades 3"},
        {"fecha": "2026-05-29", "tipo": "entrega", "label": "Paso de notas primer bimestre"},
        # Segundo bimestre
        {"fecha": "2026-06-08", "tipo": "inicio_bloque", "label": "Inicio segundo bimestre"},
        {"fecha": "2026-06-21", "tipo": "entrega", "label": "Entrega actividades 4"},
        {"fecha": "2026-07-05", "tipo": "entrega", "label": "Entrega actividades 5"},
        {"fecha": "2026-07-19", "tipo": "entrega", "label": "Entrega actividades 6"},
        {"fecha": "2026-07-31", "tipo": "entrega", "label": "Paso de notas segundo bimestre"},
    ]

    db = SessionLocal()
    try:
        sc = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
        if not sc:
            return

        updated = False

        # Cargar calendario si no existe
        if not sc.calendario_academico:
            sc.calendario_academico = json.dumps(CALENDARIO_P68)
            updated = True
            logger.info("📅 Calendario académico P68 cargado en SemesterConfig")

        # Asegurar fechas de bloque si no están configuradas
        from datetime import datetime, timezone
        if not sc.bloque1_inicio:
            sc.bloque1_inicio = datetime(2026, 4, 6, tzinfo=timezone.utc)
            updated = True
        if not sc.bloque1_fin:
            sc.bloque1_fin = datetime(2026, 5, 29, tzinfo=timezone.utc)
            updated = True
        if not sc.bloque2_inicio:
            sc.bloque2_inicio = datetime(2026, 6, 8, tzinfo=timezone.utc)
            updated = True
        if not sc.bloque2_fin:
            sc.bloque2_fin = datetime(2026, 7, 31, tzinfo=timezone.utc)
            updated = True

        if updated:
            db.commit()
            logger.info("📅 SemesterConfig actualizado con calendario y fechas de bloque")
    except Exception as e:
        logger.warning(f"⚠️ Error cargando calendario académico: {e}")
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def _create_default_admin():
    """Crea o actualiza el usuario admin según las variables de entorno."""
    from .database import SessionLocal
    from .models.user import User, UserRole
    from .auth.jwt import hash_password
    import os

    admin_email = os.environ.get("ADMIN_EMAIL")
    admin_pass = os.environ.get("ADMIN_PASSWORD")

    if not admin_email or not admin_pass:
        # [SEC-01] FIX: Credenciales hardcodeadas eliminadas.
        # Ya NO se usan valores por defecto, ni siquiera en DEBUG.
        logger.warning(
            "⚠️ ADMIN_EMAIL y/o ADMIN_PASSWORD no configurados. "
            "No se creará usuario admin. Configura ambas variables de entorno."
        )
        return

    db = SessionLocal()
    try:
        # Si ya existe el usuario con ese email, no hacer nada
        existing = db.query(User).filter(User.email == admin_email).first()
        if existing:
            logger.info(f"Usuario admin ya existe: {admin_email}")
            return

        admin = db.query(User).filter(User.role == UserRole.admin).first()
        admin_reset = os.environ.get("ADMIN_RESET", "").lower() in ("1", "true", "yes")

        if admin and not admin_reset:
            # [Opción B] Ya hay un admin: NO sobrescribir (respeta cambios de correo/clave
            # hechos en la app). Para forzar un reseteo de recuperación, usar ADMIN_RESET=true.
            logger.info(
                "Ya existe un admin; no se sobrescribe (cambios en la app se conservan). "
                "Usa ADMIN_RESET=true para forzar reseteo desde variables de entorno."
            )
            return

        if admin and admin_reset:
            # Recuperación explícita: resetear credenciales del primer admin a las del env.
            admin.email = admin_email
            admin.hashed_password = hash_password(admin_pass)
            admin.is_active = True
            db.commit()
            logger.warning(f"[ADMIN_RESET] Credenciales de admin reseteadas a {admin_email}")
        else:
            # No existe ningún admin → crear uno nuevo (bootstrap inicial)
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


# CORS — permite el frontend en Vercel + wildcard *.yachaydeep.com
# allow_origin_regex matches any single-level subdomain of yachaydeep.com
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"https://[a-zA-Z0-9-]+\.yachaydeep\.com",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant"],
)

# ── Global exception handler ─────────────────────────────────────────────
# Evita que excepciones no manejadas dejen al navegador con "NetworkError".
# Captura cualquier Exception, la loguea con traceback completo y retorna
# 500 JSON con headers CORS (la CORSMiddleware los añade automáticamente si
# la respuesta pasa por la cadena).
from fastapi import HTTPException

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Re-lanzar HTTPException estándar para que FastAPI las maneje normalmente
    if isinstance(exc, HTTPException):
        raise exc
    logger.exception(
        "Unhandled exception in %s %s: %s",
        request.method, request.url.path, exc,
    )
    # Origin echo para CORS en error (FastAPI CORSMiddleware no siempre
    # añade headers si el handler lanza antes del middleware)
    origin = request.headers.get("origin")
    cors_headers = {}
    if origin and _is_allowed_origin(origin):
        cors_headers["Access-Control-Allow-Origin"] = origin
        cors_headers["Access-Control-Allow-Credentials"] = "true"
        cors_headers["Vary"] = "Origin"
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {str(exc)[:300]}"},
        headers=cors_headers,
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
app.include_router(alerts_router)
app.include_router(workqueue_router)
app.include_router(workflow_router)
app.include_router(ml_advanced_router)
app.include_router(institutions_router)
app.include_router(demo_seed_router)


@app.middleware("http")
async def tenant_routing_middleware(request: Request, call_next):
    """Set current tenant based on X-Tenant header for DB routing.
    Auth endpoints always use the production DB (JWT user IDs are from production).
    """
    from .database import set_current_tenant
    path = request.url.path
    # Auth routes must always hit the production DB — the JWT contains
    # production user IDs which don't exist in tenant DBs.
    if path.startswith("/auth/"):
        set_current_tenant(None)
    else:
        tenant = request.headers.get("x-tenant", "").lower() or None
        set_current_tenant(tenant)
    response = await call_next(request)
    return response


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    # [CACHE] Evita que CDNs (Vercel) cacheen respuestas de API entre tenants.
    # Sin esto, una respuesta de un tenant podía servirse a otro (envenenamiento de caché).
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["Vary"] = "X-Tenant, Origin"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    # [SEC-08] FIX: Content-Security-Policy
    csp_origins = " ".join(settings.CORS_ORIGINS)
    if settings.CORS_WILDCARD_DOMAIN:
        csp_origins += f" https://*{settings.CORS_WILDCARD_DOMAIN}"
    response.headers["Content-Security-Policy"] = (
        f"default-src 'self'; "
        f"script-src 'self' 'unsafe-inline'; "
        f"style-src 'self' 'unsafe-inline'; "
        f"img-src 'self' data: https: blob:; "
        f"font-src 'self'; "
        f"connect-src 'self' {csp_origins}; "
        f"frame-ancestors 'none'"
    )
    if not settings.DEBUG:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/health/avac")
async def avac_connectivity_check():
    """Check if Railway can reach AVAC (no auth required, for diagnostics)."""
    import socket
    import httpx
    results = {}
    domain = "avac.ups.edu.ec"
    try:
        ip = socket.gethostbyname(domain)
        results["dns_resolved"] = True
        results["dns_ip"] = ip
    except socket.gaierror as e:
        results["dns_resolved"] = False
        results["dns_error"] = str(e)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.head("https://avac.ups.edu.ec/grado68/login/index.php", follow_redirects=True)
            results["http_status"] = resp.status_code
            results["http_ok"] = resp.status_code < 400
    except Exception as e:
        results["http_ok"] = False
        results["http_error"] = str(e)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.head("https://login.microsoftonline.com", follow_redirects=True)
            results["microsoft_sso_ok"] = resp.status_code < 400
    except Exception as e:
        results["microsoft_sso_ok"] = False
    results["all_ok"] = results.get("dns_resolved", False) and results.get("http_ok", False) and results.get("microsoft_sso_ok", False)
    return results


@app.get("/health")
def health_check():
    """Health check mejorado: verifica conexión a BD y versión del código."""
    from sqlalchemy import text
    # Version indicator — update on each significant deploy
    CODE_VERSION = "2026-04-17-network-check-v9"
    try:
        from .database import SessionLocal
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {"status": "ok", "database": "connected", "version": CODE_VERSION}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "error", "detail": str(e), "version": CODE_VERSION},
        )



