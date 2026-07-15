"""Limpieza de ETL runs 'zombi'.

Un run queda en 'running' para siempre si el proceso muere sin poder cerrarlo
(p. ej. GitHub Actions cancela el job por timeout: el proceso se mata de golpe).
Antes esto solo se corregía al reiniciar el backend; ahora también se limpia por
antigüedad, sin depender de un reinicio.
"""
from datetime import datetime, timezone, timedelta
import logging

from sqlalchemy.orm import Session

from ..models.scraping_run import ScrapingRun

logger = logging.getLogger(__name__)

# Un scraping completo tarda ~2-3h; el timeout del workflow es 4h.
# Más de 5h en 'running' = el proceso murió sin cerrar la fila.
STALE_HOURS = 5


def cleanup_stale_etl_runs(db: Session, max_hours: int = STALE_HOURS) -> int:
    """Marca como 'failed' los runs en 'running' iniciados hace más de max_hours.
    Devuelve cuántos se limpiaron. Seguro: no toca runs realmente en curso."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_hours)
        stale = []
        for run in db.query(ScrapingRun).filter(ScrapingRun.status == "running").all():
            started = run.started_at
            if started is None:
                continue
            if started.tzinfo is None:            # SQLite/Postgres pueden devolver naive
                started = started.replace(tzinfo=timezone.utc)
            if started < cutoff:
                stale.append(run)

        for run in stale:
            run.status = "failed"
            run.finished_at = datetime.now(timezone.utc)
            run.log_output = (run.log_output or "") + (
                f"\n[AUTO] Marcado como failed: quedó en 'running' más de {max_hours}h "
                "(el proceso fue cancelado o murió sin cerrar la ejecución)."
            )
        if stale:
            db.commit()
            logger.warning("🧹 %d ETL run(s) zombi marcados como failed (>%sh en running)", len(stale), max_hours)
        return len(stale)
    except Exception as e:
        logger.error("Error limpiando ETL runs zombi: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return 0
