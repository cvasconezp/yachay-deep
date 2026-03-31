from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    # For SQLite (dev), use connect_args
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    from . import models  # noqa: import all models to register them
    Base.metadata.create_all(bind=engine)


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
        ],
        "scraping_runs": [
            ("descripcion", "VARCHAR"),
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
        conn.commit()
