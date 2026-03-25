"""
Endpoints de administración — ETL manual, estado del sistema, scraping runs.
Solo accesibles para el rol admin.
"""
import asyncio
import io
import os
import zipfile
from fastapi import APIRouter, Depends, BackgroundTasks, File, UploadFile, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from ..database import get_db
from ..models.scraping_run import ScrapingRun
from ..auth.jwt import require_admin, get_current_user
from ..models.user import User
from ..etl.pipeline import ETLPipeline

router = APIRouter(prefix="/admin", tags=["admin"])


class ScrapingRunOut(BaseModel):
    id: int
    tipo: str
    status: str
    cursos_procesados: Optional[int]
    registros_insertados: Optional[int]
    cursos_error: Optional[int]
    triggered_by: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]

    class Config:
        from_attributes = True


def _run_etl_background(triggered_by: str):
    """Función para correr ETL en background thread."""
    from ..database import SessionLocal
    db = SessionLocal()
    try:
        pipeline = ETLPipeline(db)
        pipeline.run_full(triggered_by=triggered_by)
    finally:
        db.close()


@router.post("/etl/run")
def trigger_etl(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Dispara el pipeline ETL completo en background.
    Equivalente a hacer "Actualizar Todo" en Power Query + ejecutar macros.
    """
    background_tasks.add_task(_run_etl_background, triggered_by=current_user.email)
    return {"message": "ETL iniciado en background. Consulta /admin/etl/runs para ver el progreso."}


@router.get("/etl/runs", response_model=list[ScrapingRunOut])
def get_etl_runs(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Historial de ejecuciones del ETL."""
    return (
        db.query(ScrapingRun)
        .order_by(ScrapingRun.started_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/etl/runs/{run_id}/log")
def get_etl_log(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Log detallado de una ejecución ETL."""
    run = db.query(ScrapingRun).filter(ScrapingRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run no encontrado")
    return {"log": run.log_output, "errores": run.errores}


@router.post("/etl/upload-and-run")
async def upload_data_and_run_etl(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
):
    """
    Sube un ZIP con los archivos de datos y dispara el ETL.
    Estructura esperada del ZIP:
      IngresosAVAC/ingresosAVAC_XXXXX.csv          → accesos AVAC por curso
      Tareas/estado_XXXXX.csv                       → entregas por curso
      Reportes/XXXXX_reporte.xlsx                   → datos personales (cédula, teléfono, residencia)
      DatosEspecificos/DatosEspecificos EIB*.xlsx   → formulario EIB (nivel, sede, whatsapp, residencia)
      (opcional) calificaciones.csv                 → se copia a ./data/calificaciones.csv
    """
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .zip")

    MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500 MB
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Archivo demasiado grande ({len(content) // (1024*1024)} MB). Máximo: 500 MB",
        )
    data_root = os.path.abspath("./data")

    # Auto-routing rules: if a file at the ZIP root matches a known pattern,
    # move it into the correct subdirectory automatically.
    # This prevents the common mistake of zipping files without subdirectories.
    def _auto_route(member_name: str) -> str:
        """Return corrected path if file is at root but belongs in a subdirectory."""
        basename = os.path.basename(member_name)
        # Already in a known subdirectory? keep as-is
        parts = member_name.replace("\\", "/").split("/")
        if len(parts) > 1 and parts[0] in (
            "Reportes", "IngresosAVAC", "Tareas",
            "DatosEspecificos", "TableauHistorico",
        ):
            return member_name

        bl = basename.lower()
        # *_reporte.xlsx → Reportes/
        if bl.endswith("_reporte.xlsx"):
            return f"Reportes/{basename}"
        # ingresosAVAC_*.csv → IngresosAVAC/
        if bl.startswith("ingresosavac") and bl.endswith(".csv"):
            return f"IngresosAVAC/{basename}"
        # estado_*.csv → Tareas/
        if bl.startswith("estado_") and bl.endswith(".csv"):
            return f"Tareas/{basename}"
        # DatosEspecificos*.xlsx → DatosEspecificos/
        if bl.startswith("datosespecificos") and bl.endswith(".xlsx"):
            return f"DatosEspecificos/{basename}"
        # Detalle de Calificaciones*.csv → TableauHistorico/
        if bl.startswith("detalle de calificaciones") and bl.endswith(".csv"):
            return f"TableauHistorico/{basename}"
        # Resumen_General*.csv → Reportes/ (docente grading data)
        if bl.startswith("resumen_general") and bl.endswith(".csv"):
            return f"Reportes/{basename}"
        # calificaciones.csv → root data dir
        if bl == "calificaciones.csv":
            return basename
        # Unknown file: keep original path
        return member_name

    extracted_files: list[str] = []
    rerouted: list[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for member in zf.namelist():
                # Ignorar directorios vacíos y archivos ocultos/sistema
                if member.endswith("/") or os.path.basename(member).startswith("."):
                    continue
                routed = _auto_route(member)
                dest_path = os.path.join(data_root, routed)
                # Sanitize: no salir del data_root (path traversal protection)
                if not os.path.abspath(dest_path).startswith(data_root):
                    continue
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with zf.open(member) as src, open(dest_path, "wb") as dst:
                    dst.write(src.read())
                extracted_files.append(routed)
                if routed != member:
                    rerouted.append(f"{member} → {routed}")
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="El archivo no es un ZIP válido")

    background_tasks.add_task(_run_etl_background, triggered_by=current_user.email)
    msg = f"ZIP extraído ({len(extracted_files)} archivos). ETL iniciado en background."
    if rerouted:
        msg += f" {len(rerouted)} archivo(s) reubicados automáticamente."
    return {
        "message": msg,
        "archivos_extraidos": len(extracted_files),
        "archivos": extracted_files,
        "reubicados": rerouted,
        "etl": "iniciado",
    }


@router.get("/system/status")
def system_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Estado general del sistema: última actualización, total estudiantes, etc."""
    from ..models import Student
    from sqlalchemy import func

    last_run = db.query(ScrapingRun).filter(ScrapingRun.status == "success").order_by(ScrapingRun.finished_at.desc()).first()
    total_students = db.query(func.count(Student.id)).scalar()

    return {
        "total_estudiantes": total_students,
        "ultima_actualizacion": last_run.finished_at.isoformat() if last_run else None,
        "estado_pipeline": last_run.status if last_run else "nunca_ejecutado",
    }


@router.post("/students/deduplicate")
def deduplicate_students(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Ejecuta la deduplicación de estudiantes AHORA.
    Detecta y fusiona registros duplicados por:
    - Mismo nombre pero con/sin correo institucional
    - Mismo nombre pero con variación de tildes (ACHIÑA vs ACHINA)
    Mueve calificaciones, accesos, tareas, intervenciones y alertas al registro principal.
    """
    pipeline = ETLPipeline(db)
    merged = pipeline._merge_duplicate_students()
    return {
        "message": f"Deduplicación completada. {merged} estudiantes fusionados.",
        "fusionados": merged,
    }
