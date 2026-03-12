"""
run_etl_local.py — Ejecuta el pipeline ETL localmente contra Railway PostgreSQL.

Uso:
    cd yachay-deep-webapp
    python run_etl_local.py

Lee los CSVs locales y carga los datos directamente en la BD de Railway.
"""
import os
import sys

# ── 1. Configurar variables de entorno ANTES de importar el backend ───────────
os.environ["DATABASE_URL"] = (
    "postgresql://postgres:YUWSEEhtRKAhiTmnoDOulELqGNbItcPu"
    "@maglev.proxy.rlwy.net:30786/railway"
)

# Rutas locales a los CSV (ajusta si es necesario)
BASE = os.path.dirname(os.path.abspath(__file__))
AUTO = os.path.join(
    os.path.dirname(BASE),
    "Automatizacion",
)

DATA_INGRESOS = os.path.join(AUTO, "IngresosAVAC")
DATA_TAREAS = os.path.join(AUTO, "Tareas")
DATA_CALS = os.path.join(AUTO, "Calificaciones", "65187_reporte.xlsx")

os.environ["DATA_PATH_INGRESOS"] = DATA_INGRESOS
os.environ["DATA_PATH_TAREAS"] = DATA_TAREAS
os.environ["DATA_PATH_CALIFICACIONES"] = DATA_CALS

# ── 2. Configurar salida UTF-8 para Windows ───────────────────────────────────
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# ── 3. Verificar rutas ────────────────────────────────────────────────────────
print(f"[INFO] DATA_PATH_INGRESOS : {DATA_INGRESOS}")
print(f"[INFO] DATA_PATH_TAREAS   : {DATA_TAREAS}")
print(f"[INFO] DATA_PATH_CALS     : {DATA_CALS}")
print(f"[INFO] IngresosAVAC files : {len(os.listdir(DATA_INGRESOS)) if os.path.isdir(DATA_INGRESOS) else 'NOT FOUND'}")
print(f"[INFO] Tareas files       : {len(os.listdir(DATA_TAREAS)) if os.path.isdir(DATA_TAREAS) else 'NOT FOUND'}")
print(f"[INFO] Calificaciones     : {'OK' if os.path.isfile(DATA_CALS) else 'NOT FOUND'}")
print()

# ── 4. Importar y ejecutar el pipeline ───────────────────────────────────────
sys.path.insert(0, BASE)

from backend.database import SessionLocal, create_tables
from backend.etl.pipeline import ETLPipeline

print("[INFO] Conectando a Railway PostgreSQL...")
create_tables()
print("[INFO] Tablas verificadas/creadas OK")
print()

db = SessionLocal()
try:
    print("[INFO] Iniciando ETL pipeline...")
    pipeline = ETLPipeline(db)
    run = pipeline.run_full(triggered_by="local_run")

    print()
    print("=" * 60)
    print(f"STATUS    : {run.status}")
    print(f"REGISTROS : {run.registros_insertados}")
    print(f"STARTED   : {run.started_at}")
    print(f"FINISHED  : {run.finished_at}")
    print("=" * 60)
    print()
    print("--- LOG ---")
    if run.log_output:
        print(run.log_output)
    if run.errores:
        print()
        print("--- ERRORES ---")
        for e in run.errores:
            print(e)
finally:
    db.close()
