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
    new_columns: dict[str, list[tuple[str, str]]] = {
        "students": [
            ("whatsapp",       "VARCHAR"),
            ("nivel_academico", "INTEGER"),
            ("pais",           "VARCHAR"),
            ("provincia",      "VARCHAR"),
            ("ciudad",         "VARCHAR"),
            ("parroquia",      "VARCHAR"),
            ("barrio",         "VARCHAR"),
        ],
        "course_configs": [
            ("nivel", "INTEGER"),
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
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))
        conn.commit()
