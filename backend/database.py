from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings

_is_sqlite = "sqlite" in settings.DATABASE_URL

_engine_kwargs = dict(
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)
if not _is_sqlite:
    # Pool más robusto para Railway PostgreSQL (límite de conexiones bajo)
    _engine_kwargs.update(
        pool_size=3,
        max_overflow=5,
        pool_recycle=300,        # reciclar conexiones cada 5 min
        pool_timeout=20,         # timeout más corto para detectar problemas
    )

engine = create_engine(settings.DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ── Demo tenant DB (separate PostgreSQL instance) ──
demo_engine = None
DemoSessionLocal = None

if settings.DEMO_DATABASE_URL:
    _demo_is_sqlite = "sqlite" in settings.DEMO_DATABASE_URL
    _demo_kwargs = dict(
        pool_pre_ping=True,
        connect_args={"check_same_thread": False} if _demo_is_sqlite else {},
    )
    if not _demo_is_sqlite:
        _demo_kwargs.update(pool_size=2, max_overflow=3, pool_recycle=300, pool_timeout=20)
    demo_engine = create_engine(settings.DEMO_DATABASE_URL, **_demo_kwargs)
    DemoSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=demo_engine)
Base = declarative_base()

# Context variable to track current tenant per-request
import contextvars
_current_tenant = contextvars.ContextVar("current_tenant", default=None)

def set_current_tenant(tenant: str | None):
    """Called by middleware to set tenant for current request."""
    _current_tenant.set(tenant)

def get_current_tenant() -> str | None:
    """Get current tenant from context."""
    return _current_tenant.get()

def get_db():
    """Tenant-aware DB session. Routes to correct DB based on context tenant."""
    tenant = _current_tenant.get()
    if tenant == "demo" and DemoSessionLocal:
        db = DemoSessionLocal()
    else:
        db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_prod_db():
    """Always returns a production DB session (ignores tenant). Used for auth."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    from . import models  # noqa: import all models to register them
    Base.metadata.create_all(bind=engine)
    # Also create tables in demo DB if configured
    if demo_engine:
        Base.metadata.create_all(bind=demo_engine)


def upgrade_tables():
    """
    Agrega columnas nuevas a tablas existentes sin borrar datos.
    Se ejecuta en cada startup después de create_tables().
    Compatible con PostgreSQL (Railway) y SQLite (dev).
    """
    from sqlalchemy import inspect, text

    # Mapa tabla → columnas nuevas a agregar si no existen
    # Las tablas nuevas (escuelas_practica, practicas_preprofesionales) se crean
    # automáticamente por create_tables() ya que están registradas en models/__init__.py.
    # Aquí solo gestionamos ALTER TABLE para columnas nuevas en tablas existentes.

    new_columns: dict[str, list[tuple[str, str]]] = {
        "users": [
            ("permissions", "JSON"),
            ("pin_hash", "VARCHAR"),
            ("tenant", "VARCHAR"),
            ("totp_secret", "VARCHAR"),
            ("totp_enabled", "BOOLEAN DEFAULT false"),
            ("recovery_codes", "JSON"),
            ("pin_locked", "BOOLEAN DEFAULT false"),
        ],
        "institutions": [],  # new table, created by create_all()
    "students": [
            ("whatsapp",       "VARCHAR"),
            ("nivel_academico", "INTEGER"),
            ("pais",           "VARCHAR"),
            ("provincia",      "VARCHAR"),
            ("ciudad",         "VARCHAR"),
            ("parroquia",      "VARCHAR"),
            ("barrio",         "VARCHAR"),
            # Nuevas columnas del reporte institucional (fix data quality)
            ("fecha_nacimiento", "DATE"),
            ("genero",           "VARCHAR"),
            ("autoidentificacion_etnica", "VARCHAR"),
            ("grupo",            "VARCHAR"),
            # ML predictions (Phase 2)
            ("prob_desercion",         "FLOAT"),
            ("prob_reprobacion",       "FLOAT"),
            ("prediccion_updated_at",  "TIMESTAMP"),
        ],
        "course_configs": [
            ("nivel", "INTEGER"),
            ("correo_docente", "VARCHAR"),
            ("es_especial", "BOOLEAN DEFAULT false"),
        ],
        "grades": [
            ("periodo", "VARCHAR"),
            ("numero_repitencias", "INTEGER"),
            ("nivel", "INTEGER"),
        ],
        "interventions": [
            ("derivar_bienestar", "BOOLEAN"),
            ("tipo_evento_critico", "VARCHAR"),
            ("reporte_bienestar", "TEXT"),
            ("email_enviado", "BOOLEAN"),
            # [GAP-F5-01] Snapshot de indicadores al crear intervención
            ("snapshot_compromiso", "FLOAT"),
            ("snapshot_dias_sin_acceso", "INTEGER"),
            ("snapshot_porcentaje_tareas", "FLOAT"),
            ("snapshot_prob_desercion", "FLOAT"),
            ("snapshot_prob_reprobacion", "FLOAT"),
            ("snapshot_nivel_riesgo", "VARCHAR"),
            # Periodo de la intervención (P67, P68, etc.)
            ("periodo", "VARCHAR"),
            # Derivaciones ampliadas
            ("derivar_financiero", "BOOLEAN"),
            ("derivar_coordinacion", "BOOLEAN"),
            ("derivar_docente", "BOOLEAN"),
            ("reporte_derivacion", "TEXT"),
            # Workflow de intervención (Fase 3)
            ("estado_workflow", "VARCHAR DEFAULT 'pendiente'"),
            ("asignado_a", "INTEGER"),
            ("asignado_nombre", "VARCHAR"),
            ("fecha_asignacion", "TIMESTAMP"),
            ("fecha_limite", "TIMESTAMP"),
            ("fecha_contacto", "TIMESTAMP"),
            ("fecha_resolucion", "TIMESTAMP"),
            ("escalado", "BOOLEAN DEFAULT false"),
            ("escalado_a", "VARCHAR"),
            ("prioridad", "INTEGER DEFAULT 2"),
            ("overdue", "BOOLEAN DEFAULT false"),
        ],
        "intervention_logs": [
            # tabla nueva — upgrade_tables() la creará si no existe
        ],
        "scraping_runs": [
            ("descripcion", "VARCHAR"),
        ],
        "avac_accesses": [
            ("periodo", "VARCHAR"),
            ("snapshot_date", "DATE"),
        ],
        "task_submissions": [
            ("periodo", "VARCHAR"),
            ("snapshot_date", "DATE"),
        ],
        "semester_configs": [
            ("calendario_academico", "VARCHAR"),
            ("umbral_nota_aprobacion", "FLOAT"),
            ("umbral_dias_inactividad", "INTEGER"),
            ("umbral_tareas_minimo", "FLOAT"),
            ("umbral_compromiso_minimo", "FLOAT"),
            ("auto_alertas", "BOOLEAN DEFAULT true"),
            ("retrain_cada_n_etl", "INTEGER DEFAULT 5"),
            ("retrain_contador_etl", "INTEGER DEFAULT 0"),
            ("ultimo_retrain", "TIMESTAMP"),
        ],
        "alert_events": [
            ("codigo_curso", "VARCHAR"),
        ],
        "students": [
            ("es_tercera_matricula", "BOOLEAN DEFAULT false"),
        ("institution_id", "INTEGER"),
            ("score_recuperabilidad", "FLOAT"),
            ("nivel_recuperabilidad", "VARCHAR"),
        ],
        "enrollments": [
            ("es_tercera_matricula", "BOOLEAN DEFAULT false"),
            ("tipo_aprobacion", "VARCHAR"),
            ("estado_solicitud", "VARCHAR"),
        ],
    }

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    with engine.connect() as conn:
        for table, columns in new_columns.items():
            if table not in existing_tables:
                continue  # la tabla se creará completa con create_tables()
            existing_cols = {c["name"] for c in inspector.get_columns(table)}
            for col_name, col_type in columns:
                if col_name not in existing_cols:
                    conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{col_name}" {col_type}'))

        # ── Data migration: etiquetar registros AVAC sin periodo como P67 ──
        # Los datos AVAC cargados antes de esta migración corresponden al P67.
        for tbl in ("avac_accesses", "task_submissions"):
            if tbl in existing_tables:
                conn.execute(text(f'UPDATE "{tbl}" SET periodo = \'P67\' WHERE periodo IS NULL'))

        # ── Sanitización de NaN/Inf en columnas float ──
        # Celdas vacías en CSVs de pandas llegaban como NaN y se insertaban
        # en la BD. JSON estándar no soporta NaN/Infinity, por lo que
        # serializar respuestas con esos valores rompe el endpoint con
        # "ValueError: Out of range float values are not JSON compliant".
        # Solo aplica en PostgreSQL (SQLite no soporta 'nan'::float literal).
        is_postgres = "postgres" in str(engine.url).lower()

        # ── Make enrollments.codigo_grupo nullable (for 3ra matrícula without grupo) ──
        if "enrollments" in existing_tables and is_postgres:
            conn.execute(text('ALTER TABLE "enrollments" ALTER COLUMN "codigo_grupo" DROP NOT NULL'))

        if is_postgres:
            nan_cleanups = [
                ("avac_accesses", ["dias_sin_acceso"]),
                ("task_submissions", ["calificacion", "calificacion_maxima",
                                       "calificacion_final", "total_curso"]),
                ("grades", ["nota_final"]),
                ("students", ["indice_compromiso", "porcentaje_tareas",
                              "promedio_calificaciones", "prob_desercion",
                              "prob_reprobacion"]),
            ]
            for tbl, cols in nan_cleanups:
                if tbl not in existing_tables:
                    continue
                existing_cols = {c["name"] for c in inspector.get_columns(tbl)}
                for col in cols:
                    if col not in existing_cols:
                        continue
                    try:
                        result = conn.execute(text(
                            f'UPDATE "{tbl}" SET "{col}" = NULL '
                            f'WHERE "{col}"::text IN (\'NaN\', \'Infinity\', \'-Infinity\')'
                        ))
                        if result.rowcount:
                            import logging as _lg
                            _lg.getLogger(__name__).warning(
                                "Sanitizados %d NaN/Inf en %s.%s", result.rowcount, tbl, col,
                            )
                    except Exception as _e:  # pragma: no cover
                        import logging as _lg
                        _lg.getLogger(__name__).warning(
                            "No se pudo limpiar NaN en %s.%s: %s", tbl, col, _e,
                        )

        conn.commit()
