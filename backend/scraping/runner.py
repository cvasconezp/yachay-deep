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

    results = {}

    if mode in ("ingresos", "full"):
        logger.info("=" * 50)
        logger.info("SCRAPING: IngresosAVAC")
        logger.info("=" * 50)
        results["ingresos"] = scrape_ingresos(output_dir=settings.DATA_PATH_INGRESOS)

    if mode in ("tareas", "full"):
        logger.info("=" * 50)
        logger.info("SCRAPING: Estado Tareas")
        logger.info("=" * 50)
        results["tareas"] = scrape_tareas(output_dir=settings.DATA_PATH_TAREAS)

    return results


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
    args = parser.parse_args()

    logger.info(f"Iniciando scraping en modo: {args.mode}")
    scraping_results = run_scraping(mode=args.mode)

    if not args.skip_etl:
        etl_run = run_etl_after_scraping()
        if etl_run.status != "success":
            sys.exit(1)

    logger.info("Pipeline completo")
