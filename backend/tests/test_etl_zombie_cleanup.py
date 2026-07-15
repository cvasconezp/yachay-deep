"""Limpieza de ETL runs zombi por antigüedad (no depende de reinicio)."""
from datetime import datetime, timezone, timedelta
from backend.models.scraping_run import ScrapingRun
from backend.services.etl_maintenance import cleanup_stale_etl_runs


def _run(db, status, horas_atras):
    r = ScrapingRun(tipo="full", status=status,
                    started_at=datetime.now(timezone.utc) - timedelta(hours=horas_atras))
    db.add(r); db.commit(); db.refresh(r); return r


def test_marca_zombi_viejo_como_failed(db):
    zombi = _run(db, "running", 30)      # 30h en running → zombi
    n = cleanup_stale_etl_runs(db, max_hours=5)
    assert n == 1
    db.refresh(zombi)
    assert zombi.status == "failed"
    assert zombi.finished_at is not None
    assert "[AUTO]" in (zombi.log_output or "")


def test_no_toca_run_en_curso(db):
    activo = _run(db, "running", 1)      # 1h → puede estar corriendo de verdad
    n = cleanup_stale_etl_runs(db, max_hours=5)
    assert n == 0
    db.refresh(activo)
    assert activo.status == "running"


def test_no_toca_runs_terminados(db):
    ok = _run(db, "success", 50)
    err = _run(db, "error", 50)
    n = cleanup_stale_etl_runs(db, max_hours=5)
    assert n == 0
    db.refresh(ok); db.refresh(err)
    assert ok.status == "success" and err.status == "error"
