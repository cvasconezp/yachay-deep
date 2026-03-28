"""
Yachay Deep — API Backend
FastAPI application entry point

[SEC-02] Fase 2: HttpOnly cookies + Sentry integration
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from .config import settings, validate_security_settings

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
app.include_router(alerts_router)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    # [SEC-08] FIX: Content-Security-Policy
    csp_origins = " ".join(settings.CORS_ORIGINS)
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


@app.get("/health")
def health_check():
    """Health check mejorado: verifica conexión a BD y versión del código."""
    from sqlalchemy import text
    # Version indicator — update on each significant deploy
    CODE_VERSION = "2026-03-28-malla-reference-json-v8"
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


@app.get("/debug/malla-diagnostico")
def debug_malla_diagnostico():  # TODO: eliminar endpoint temporal después de resolver malla
    """
    Endpoint temporal de diagnóstico — muestra distribución de Grade.carrera
    para entender la contaminación cruzada en la malla canónica.
    ELIMINAR después de resolver el problema.
    """
    from sqlalchemy import text, func
    from .database import SessionLocal
    from .models import Student, Grade

    db = SessionLocal()
    try:
        # 1. Buscar a FERNANDEZ FERNANDEZ
        student = db.query(Student).filter(
            Student.nombre.ilike("%FERNANDEZ FERNANDEZ LIZBETH%")
        ).first()

        if not student:
            return {"error": "Estudiante no encontrada"}

        student_carrera = student.carrera

        # 2. Distribución de Grade.carrera para TODOS los grades de estudiantes EIB
        carrera_key = student_carrera.upper() if student_carrera else "?"

        # Contar grades por carrera para estudiantes de esta carrera
        career_students = db.query(Student.id).filter(
            func.upper(Student.carrera) == carrera_key
        ).subquery()

        grade_carrera_dist = (
            db.query(
                func.coalesce(Grade.carrera, "NULL"),
                func.count()
            )
            .filter(Grade.student_id.in_(db.query(career_students.c.id)))
            .group_by(func.coalesce(Grade.carrera, "NULL"))
            .all()
        )

        # 3. Último ETL run
        last_run = db.execute(text(
            "SELECT id, status, started_at, finished_at, log_output "
            "FROM scraping_runs ORDER BY started_at DESC LIMIT 1"
        )).fetchone()

        etl_info = None
        etl_log_backfill = None
        if last_run:
            etl_info = {
                "id": last_run[0],
                "status": last_run[1],
                "started_at": str(last_run[2]),
                "finished_at": str(last_run[3]),
            }
            log = last_run[4] or ""
            # Extraer líneas relevantes del log
            etl_log_backfill = [l for l in log.split("\n") if "backfill" in l.lower() or "canónic" in l.lower() or "carrera" in l.lower() or "merged" in l.lower() or "ERROR" in l]

        # 4. Total asignaturas únicas que pasarían el filtro estricto
        strict_count = (
            db.query(func.count(func.distinct(func.upper(func.trim(Grade.asignatura)))))
            .filter(
                Grade.student_id.in_(db.query(career_students.c.id)),
                func.upper(Grade.carrera) == carrera_key,
                Grade.nivel.isnot(None),
                Grade.nivel >= 1,
                Grade.nivel <= 12,
            )
            .scalar()
        )

        # 5. Total sin filtro de carrera (para comparar)
        no_filter_count = (
            db.query(func.count(func.distinct(func.upper(func.trim(Grade.asignatura)))))
            .filter(
                Grade.student_id.in_(db.query(career_students.c.id)),
                Grade.nivel.isnot(None),
                Grade.nivel >= 1,
                Grade.nivel <= 12,
            )
            .scalar()
        )

        # 6. Listar TODAS las asignaturas únicas del canonical actual
        from .routes.students import _get_canonical_for_career
        canonical = _get_canonical_for_career(db, student_carrera)
        # Agrupar por nivel para ver distribución
        by_nivel = {}
        for asig, niv in canonical.items():
            by_nivel.setdefault(niv, []).append(asig)
        for niv in by_nivel:
            by_nivel[niv].sort()

        # 7. Contar materias únicas por Strategy B (periodo inference, con filtro)
        from sqlalchemy import distinct
        strategy_b_subjects = (
            db.query(func.distinct(func.upper(func.trim(Grade.asignatura))))
            .filter(
                Grade.student_id.in_(db.query(career_students.c.id)),
                func.upper(Grade.carrera) == carrera_key,
                Grade.periodo.isnot(None),
            )
            .all()
        )

        # 8. Buscar estudiantes EIB que tienen grades de otra carrera original
        #    (carrera del CSV != carrera del student)
        cross_career = db.execute(text("""
            SELECT DISTINCT g.carrera as grade_carrera, s.carrera as student_carrera, count(*) as cnt
            FROM grades g
            JOIN students s ON g.student_id = s.id
            WHERE upper(s.carrera) = :ck
              AND g.carrera IS NOT NULL
              AND g.carrera != ''
              AND upper(g.carrera) != :ck
            GROUP BY g.carrera, s.carrera
        """), {"ck": carrera_key}).fetchall()

        return {
            "estudiante": student.nombre,
            "student_carrera": student_carrera,
            "carrera_key": carrera_key,
            "grade_carrera_distribution": {str(k): v for k, v in grade_carrera_dist},
            "asignaturas_con_filtro_estricto_A": strict_count,
            "asignaturas_sin_filtro_carrera_A": no_filter_count,
            "strategy_b_subjects_count": len(strategy_b_subjects),
            "canonical_total": len(canonical),
            "canonical_by_nivel": {str(k): {"count": len(v), "asignaturas": v} for k, v in sorted(by_nivel.items())},
            "cross_career_grades": [{"grade_carrera": r[0], "student_carrera": r[1], "count": r[2]} for r in cross_career],
            "etl_last_run": etl_info,
            "etl_log_relevante": etl_log_backfill,
        }
    finally:
        db.close()


