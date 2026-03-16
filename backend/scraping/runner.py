"""
Runner de scraping — punto de entrada para GitHub Actions.
Ejecuta ingresos + tareas en secuencia y luego dispara el ETL.
"""
import sys
import os
import logging
import argparse
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def run_scraping(mode: str = "full"):
    """
    mode: 'ingresos' | 'tareas' | 'full'
    """
    from .ingresos_avac import scrape_ingresos
    from .estado_tareas import scrape_tareas
    from ..config import settings
    from ..database import SessionLocal

    results = {}
    db = SessionLocal()

    try:
        if mode in ("ingresos", "full"):
            logger.info("=" * 50)
            logger.info("SCRAPING: IngresosAVAC")
            logger.info("=" * 50)
            results["ingresos"] = scrape_ingresos(output_dir=settings.DATA_PATH_INGRESOS, db=db)

        if mode in ("tareas", "full"):
            logger.info("=" * 50)
            logger.info("SCRAPING: Estado Tareas")
            logger.info("=" * 50)
            results["tareas"] = scrape_tareas(output_dir=settings.DATA_PATH_TAREAS, db=db)
    finally:
        db.close()

    return results


def _semester_ended() -> bool:
    """Verifica si el semestre activo ya finalizó según sus fechas de bloque."""
    from ..database import SessionLocal
    from ..models.course_config import SemesterConfig
    db = SessionLocal()
    try:
        sem = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
        if sem is None:
            logger.warning("No hay semestre activo configurado — omitiendo scraping.")
            return True  # sin semestre activo, no ejecutar scraping
        if sem.fecha_fin_actual is None:
            logger.warning(
                f"⚠️ Semestre {sem.semestre} no tiene fechas de bloque configuradas. "
                "Configure bloque1_fin/bloque2_fin en Admin → Configuración de Semestre "
                "para activar la protección post-semestre. Continuando scraping..."
            )
            return False
        if sem.semestre_finalizado:
            logger.warning(
                f"Semestre {sem.semestre} finalizó el {sem.fecha_fin_actual}. "
                "Omitiendo scraping para evitar alertas falsas post-semestre."
            )
            return True
        logger.info(f"Semestre {sem.semestre} vigente (fin bloque: {sem.fecha_fin_actual})")
        return False
    finally:
        db.close()


def run_etl_after_scraping():
    """Dispara el ETL después del scraping para actualizar la BD."""
    from ..database import SessionLocal, create_tables
    from ..etl.pipeline import ETLPipeline

    logger.info("=" * 50)
    logger.info("ETL: Procesando datos scrapeados")
    logger.info("=" * 50)

    create_tables()
    db = SessionLocal()
    try:
        pipeline = ETLPipeline(db)
        run = pipeline.run_full(triggered_by="github_actions")
        logger.info(f"ETL completado: status={run.status}, registros={run.registros_insertados}")
        return run
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Yachay Deep Scraping Runner")
    parser.add_argument(
        "--mode", default="full",
        choices=["ingresos", "tareas", "full"],
        help="Qué scraping ejecutar",
    )
    parser.add_argument("--skip-etl", action="store_true", help="No ejecutar ETL después del scraping")
    parser.add_argument("--force", action="store_true", help="Forzar ejecución aunque el semestre haya terminado")
    args = parser.parse_args()

    # Verificar si el semestre está vigente antes de scrapear
    if not args.force and _semester_ended():
        logger.info("Scraping omitido: el semestre activo ya finalizó. Use --force para ejecutar de todas formas.")
        sys.exit(0)

    logger.info(f"Iniciando scraping en modo: {args.mode}")
    scraping_results = run_scraping(mode=args.mode)

    if not args.skip_etl:
        etl_run = run_etl_after_scraping()
        if etl_run.status != "success":
            sys.exit(1)

    logger.info("Pipeline completo")
