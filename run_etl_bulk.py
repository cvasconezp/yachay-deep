"""
run_etl_bulk.py — Carga masiva de datos ETL usando bulk SQL, evitando
el cuello de botella de inserciones fila-a-fila a 100ms de latencia.

Usa psycopg2 execute_values para inserciones por lotes de 500 filas.
"""
import os, sys, time
import math

# ── 1. Env vars ANTES de importar backend ─────────────────────────────────────
DB_URL = (
    "postgresql://postgres:YUWSEEhtRKAhiTmnoDOulELqGNbItcPu"
    "@maglev.proxy.rlwy.net:30786/railway"
)
os.environ["DATABASE_URL"] = DB_URL

BASE = os.path.dirname(os.path.abspath(__file__))
AUTO = os.path.join(os.path.dirname(BASE), "Automatizacion")
DATA_INGRESOS = os.path.join(AUTO, "IngresosAVAC")
DATA_TAREAS   = os.path.join(AUTO, "Tareas")

os.environ["DATA_PATH_INGRESOS"] = DATA_INGRESOS
os.environ["DATA_PATH_TAREAS"]   = DATA_TAREAS

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, BASE)

import psycopg2
from psycopg2.extras import execute_values
import pandas as pd
from datetime import datetime

from backend.etl.transformers import (
    transform_ingresos_avac,
    transform_estado_tareas,
    calcular_indicadores_estudiantes,
)
from backend.database import SessionLocal
from backend.models.course_config import CourseConfig, SemesterConfig


def nan_to_none(val):
    if val is None:
        return None
    try:
        if math.isnan(float(val)) or math.isinf(float(val)):
            return None
    except (TypeError, ValueError):
        pass
    return val


def batch_insert(conn, sql, records, batch_size=500):
    """Inserta registros en lotes usando execute_values."""
    total = 0
    with conn.cursor() as cur:
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            execute_values(cur, sql, batch)
            total += len(batch)
            logger.info(f"  Lote {i//batch_size + 1}: {total}/{len(records)} insertados")
        conn.commit()
    return total


t_start = time.time()

# ── 2. Obtener codigos activos del semestre ───────────────────────────────────
logger.info("Obteniendo configuracion del semestre activo...")
db = SessionLocal()
sem = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
if not sem:
    print("ERROR: No hay semestre activo")
    db.close()
    sys.exit(1)

codigos_activos = [
    r[0] for r in db.query(CourseConfig.codigo_avac).filter(
        CourseConfig.semestre == sem.semestre,
        CourseConfig.activo == True,
        (CourseConfig.bloque == sem.bloque_actual) | (CourseConfig.bloque == "ambos")
    ).all()
]
db.close()
logger.info(f"Semestre: {sem.semestre}, Bloque: {sem.bloque_actual}, Cursos: {len(codigos_activos)}")

# ── 3. Transformar datos ──────────────────────────────────────────────────────
logger.info("Transformando IngresosAVAC...")
df_i = transform_ingresos_avac(DATA_INGRESOS, codigos_activos=codigos_activos)
logger.info(f"  → {len(df_i)} registros de acceso")

logger.info("Transformando Tareas...")
df_t = transform_estado_tareas(DATA_TAREAS, codigos_activos=codigos_activos)
logger.info(f"  → {len(df_t)} registros de tareas")

logger.info("Calculando indicadores...")
df_m = calcular_indicadores_estudiantes(df_i, df_t, pd.DataFrame())
logger.info(f"  → {len(df_m)} estudiantes")

# ── 4. Conexion directa psycopg2 ─────────────────────────────────────────────
conn = psycopg2.connect(DB_URL)
conn.autocommit = False

# ── 5. Marcar run anterior como 'cancelled' si quedó en 'running' ─────────────
with conn.cursor() as cur:
    cur.execute(
        "UPDATE scraping_runs SET status='cancelled', finished_at=NOW() "
        "WHERE status='running'"
    )
    cancelled = cur.rowcount
    conn.commit()
    if cancelled:
        logger.info(f"Marcados {cancelled} runs anteriores como 'cancelled'")

# ── 6. Crear nuevo ScrapingRun ────────────────────────────────────────────────
with conn.cursor() as cur:
    cur.execute(
        "INSERT INTO scraping_runs (tipo, status, triggered_by, started_at) "
        "VALUES ('full', 'running', 'local_bulk', NOW()) RETURNING id"
    )
    run_id = cur.fetchone()[0]
    conn.commit()
logger.info(f"ScrapingRun #{run_id} creado")

total_insertados = 0
logs = []
errores = []

try:
    # ── 7. Upsert estudiantes ─────────────────────────────────────────────────
    logger.info(f"Cargando {len(df_m)} estudiantes...")
    student_records = []
    for _, row in df_m.iterrows():
        correo = str(row.get("correo", "")).strip()
        if not correo or "@" not in correo:
            continue
        nombre = str(row.get("nombre_avac", "")).strip() or None
        dias = nan_to_none(row.get("dias_sin_acceso_max"))
        student_records.append((
            correo,           # correo_institucional
            nombre,           # nombre
            nan_to_none(row.get("indice_compromiso")),
            row.get("nivel_riesgo"),
            int(dias) if dias is not None else None,
            nan_to_none(row.get("porcentaje_tareas")),
        ))

    # Full refresh: truncate cascade removes avac_accesses and task_submissions too
    logger.info("Truncando tablas para full refresh...")
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE students RESTART IDENTITY CASCADE")
        conn.commit()
    logger.info("  Tablas limpiadas (cascade)")

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO students (correo_institucional, nombre, indice_compromiso,
                                  nivel_riesgo, dias_sin_acceso, porcentaje_tareas)
            VALUES %s
            """,
            student_records,
            page_size=500
        )
        conn.commit()
    n_students = len(student_records)
    logger.info(f"  → {n_students} estudiantes upserted")
    logs.append(f"Estudiantes: {n_students}")
    total_insertados += n_students

    # ── 8. Construir mapa correo → student_id ─────────────────────────────────
    logger.info("Cargando mapa correo→ID...")
    with conn.cursor() as cur:
        cur.execute("SELECT id, correo_institucional FROM students WHERE correo_institucional IS NOT NULL")
        correo_to_id = {row[1]: row[0] for row in cur.fetchall()}
    logger.info(f"  → {len(correo_to_id)} estudiantes en mapa")

    # ── 9. Insertar accesos AVAC ─────────────────────────────────────────────
    logger.info(f"Cargando {len(df_i)} accesos AVAC...")

    access_records = []
    for _, row in df_i.iterrows():
        correo = str(row.get("correo", "")).strip()
        sid = correo_to_id.get(correo)
        if not sid:
            continue
        fecha = row.get("fecha_extraccion")
        access_records.append((
            sid,
            str(row.get("codigo_curso", "")).strip(),
            str(row.get("nombre_avac", "")).strip() or None,
            row.get("ultimo_acceso_texto"),
            nan_to_none(row.get("dias_sin_acceso")),
            row.get("estado_avac"),
            fecha if pd.notna(fecha) else None,
        ))

    SQL_ACCESS = """
        INSERT INTO avac_accesses (student_id, codigo_curso, nombre_estudiante_avac,
            ultimo_acceso_texto, dias_sin_acceso, estado_avac, fecha_extraccion)
        VALUES %s
    """
    n_access = batch_insert(conn, SQL_ACCESS, access_records, batch_size=500)
    logger.info(f"  → {n_access} accesos AVAC cargados")
    logs.append(f"Accesos AVAC: {n_access}")
    total_insertados += n_access

    # ── 10. Insertar task submissions ────────────────────────────────────────
    logger.info(f"Cargando {len(df_t)} submissions de tareas...")

    task_records = []
    for _, row in df_t.iterrows():
        correo = str(row.get("correo", "")).strip()
        sid = correo_to_id.get(correo)
        if not sid:
            continue
        fecha = row.get("fecha_extraccion")
        task_records.append((
            sid,
            str(row.get("codigo_curso", "")).strip(),
            str(row.get("unidad", "")).strip(),
            row.get("estado"),
            nan_to_none(row.get("calificacion")),
            nan_to_none(row.get("calificacion_maxima")),
            nan_to_none(row.get("calificacion_final")),
            bool(row.get("entregada", False)),
            bool(row.get("calificada", False)),
            bool(row.get("retrasada", False)),
            row.get("archivos_enviados"),
            row.get("comentarios_retroalimentacion"),
            nan_to_none(row.get("total_curso")),
            fecha if pd.notna(fecha) else None,
        ))

    SQL_TASKS = """
        INSERT INTO task_submissions (student_id, codigo_curso, unidad, estado,
            calificacion, calificacion_maxima, calificacion_final,
            entregada, calificada, retrasada,
            archivos_enviados, comentarios_retroalimentacion,
            total_curso, fecha_extraccion)
        VALUES %s
    """
    n_tasks = batch_insert(conn, SQL_TASKS, task_records, batch_size=500)
    logger.info(f"  → {n_tasks} submissions de tareas cargados")
    logs.append(f"Task submissions: {n_tasks}")
    total_insertados += n_tasks

    # ── 11. Marcar run como success ──────────────────────────────────────────
    with conn.cursor() as cur:
        log_output = "\n".join(logs)
        cur.execute(
            "UPDATE scraping_runs SET status='success', registros_insertados=%s, "
            "log_output=%s, finished_at=NOW() WHERE id=%s",
            (total_insertados, log_output, run_id)
        )
        conn.commit()

    elapsed = time.time() - t_start
    print()
    print("=" * 60)
    print(f"STATUS    : success")
    print(f"REGISTROS : {total_insertados}")
    print(f"TIEMPO    : {elapsed:.1f}s")
    print("=" * 60)
    for l in logs:
        print(f"  {l}")

except Exception as e:
    import traceback
    logger.error(f"ERROR: {e}")
    traceback.print_exc()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE scraping_runs SET status='error', log_output=%s, "
            "finished_at=NOW() WHERE id=%s",
            (str(e), run_id)
        )
        conn.commit()
finally:
    conn.close()
