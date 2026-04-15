"""
Endpoints de administración — ETL manual, estado del sistema, scraping runs.
Solo accesibles para el rol admin.
"""
import asyncio
import io
import os
import shutil
import tempfile
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
    descripcion: Optional[str] = None
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


class PaginatedRuns(BaseModel):
    items: list[ScrapingRunOut]
    total: int
    page: int
    page_size: int
    pages: int


@router.get("/etl/runs", response_model=PaginatedRuns)
def get_etl_runs(
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Historial de ejecuciones del ETL con paginación."""
    from sqlalchemy import func as sqlfunc
    total = db.query(sqlfunc.count(ScrapingRun.id)).scalar()
    pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, pages))
    items = (
        db.query(ScrapingRun)
        .order_by(ScrapingRun.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedRuns(items=items, total=total, page=page, page_size=page_size, pages=pages)


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


@router.post("/etl/upload-historico")
async def upload_historico(
    background_tasks: BackgroundTasks,
    periodo: str = "P67",
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
):
    """
    Sube un ZIP con datos AVAC + reporte para un periodo HISTÓRICO (ej. P67).
    NO toca el semestre activo (P68). Los datos se etiquetan con el periodo dado.

    Estructura esperada del ZIP:
      IngresosAVAC/ingresosAVAC_XXXXX.csv   → accesos AVAC por curso
      Tareas/estado_XXXXX.csv               → entregas por curso
      Reportes/XXXXX_reporte.xlsx           → datos personales + repitencias

    También re-enriquece las calificaciones existentes del periodo con
    NIVEL y NUMERO_REPITENCIAS del reporte.
    """
    # Normalizar periodo: asegurar formato "P67" (no "67")
    periodo = periodo.strip()
    if periodo.isdigit():
        periodo = f"P{periodo}"
    if not periodo.startswith("P") or len(periodo) < 3:
        raise HTTPException(status_code=400, detail=f"Periodo inválido: {periodo}. Use formato P67, P68, etc.")

    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .zip")

    MAX_UPLOAD_SIZE = 500 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail=f"Archivo demasiado grande ({len(content) // (1024*1024)} MB). Máximo: 500 MB")

    # Extraer a directorio temporal separado (no contamina ./data del periodo activo)
    temp_dir = tempfile.mkdtemp(prefix=f"historico_{periodo}_")

    def _auto_route_historico(member_name: str) -> str:
        basename = os.path.basename(member_name)
        parts = member_name.replace("\\", "/").split("/")
        if len(parts) > 1 and parts[0] in ("Reportes", "IngresosAVAC", "Tareas"):
            return member_name
        bl = basename.lower()
        if bl.endswith("_reporte.xlsx"):
            return f"Reportes/{basename}"
        if bl.startswith("ingresosavac") and bl.endswith(".csv"):
            return f"IngresosAVAC/{basename}"
        if bl.startswith("estado_") and bl.endswith(".csv"):
            return f"Tareas/{basename}"
        return member_name

    extracted_files = []
    rerouted = []
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for member in zf.namelist():
                if member.endswith("/") or os.path.basename(member).startswith("."):
                    continue
                routed = _auto_route_historico(member)
                dest_path = os.path.join(temp_dir, routed)
                if not os.path.abspath(dest_path).startswith(os.path.abspath(temp_dir)):
                    continue
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with zf.open(member) as src, open(dest_path, "wb") as dst:
                    dst.write(src.read())
                extracted_files.append(routed)
                if routed != member:
                    rerouted.append(f"{member} → {routed}")
    except zipfile.BadZipFile:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="El archivo no es un ZIP válido")

    # Contar tipos de archivos
    avac_count = sum(1 for f in extracted_files if f.startswith("IngresosAVAC/"))
    tareas_count = sum(1 for f in extracted_files if f.startswith("Tareas/"))
    reporte_count = sum(1 for f in extracted_files if f.startswith("Reportes/"))

    def _run_historico_background():
        from ..database import SessionLocal
        db = SessionLocal()
        try:
            pipeline = ETLPipeline(db)
            pipeline.run_historico(
                periodo=periodo,
                data_dir=temp_dir,
                triggered_by=current_user.email,
            )
        finally:
            db.close()
            shutil.rmtree(temp_dir, ignore_errors=True)

    background_tasks.add_task(_run_historico_background)

    msg = (
        f"ZIP histórico extraído ({len(extracted_files)} archivos). "
        f"AVAC: {avac_count}, Tareas: {tareas_count}, Reportes: {reporte_count}. "
        f"ETL histórico ({periodo}) iniciado en background."
    )
    if rerouted:
        msg += f" {len(rerouted)} archivo(s) reubicados automáticamente."

    return {
        "message": msg,
        "periodo": periodo,
        "archivos_extraidos": len(extracted_files),
        "detalle": {"avac": avac_count, "tareas": tareas_count, "reportes": reporte_count},
        "archivos": extracted_files,
        "reubicados": rerouted,
        "etl": "iniciado",
    }


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
        # Formularios Practica*.xlsx → Practicas/
        if bl.startswith("formularios practica") and bl.endswith(".xlsx"):
            return f"Practicas/{basename}"
        # Escuelas Bilingues SEIBE*.xlsx → Practicas/
        if bl.startswith("escuelas bilingues") and bl.endswith(".xlsx"):
            return f"Practicas/{basename}"
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


@router.post("/etl/upload-practicas")
async def upload_practicas_files(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    current_user: User = Depends(require_admin),
):
    """
    Sube archivos de Prácticas Preprofesionales y ejecuta el ETL.
    Acepta archivos .xlsx directamente (no ZIP):
      - Formularios Practica P*.xlsx — datos del formulario
      - Escuelas Bilingues SEIBE*.xlsx — catálogo de escuelas
    """
    practicas_dir = os.path.abspath("./data/Practicas")
    os.makedirs(practicas_dir, exist_ok=True)

    saved_files = []
    for f in files:
        if not f.filename.lower().endswith(".xlsx"):
            raise HTTPException(
                status_code=400,
                detail=f"Solo se aceptan archivos .xlsx. Archivo rechazado: {f.filename}",
            )
        content = await f.read()
        dest = os.path.join(practicas_dir, f.filename)
        with open(dest, "wb") as dst:
            dst.write(content)
        saved_files.append(f.filename)

    # Ejecutar ETL de prácticas en background con registro en historial
    files_desc = ", ".join(saved_files)

    def _run_practicas_etl():
        from ..database import SessionLocal
        from ..etl.practicas import run_practicas_etl
        from datetime import timezone
        db_session = SessionLocal()
        try:
            run = ScrapingRun(
                tipo="practicas",
                status="running",
                descripcion=f"Prácticas Preprofesionales: {files_desc}",
                triggered_by=current_user.email,
            )
            db_session.add(run)
            db_session.commit()

            stats = run_practicas_etl(db_session, practicas_dir)
            run.status = "success"
            run.registros_insertados = stats.get("practicas_cargadas", 0)
            log_lines = [
                f"Escuelas cargadas: {stats.get('escuelas_cargadas', 0)}",
                f"Prácticas cargadas: {stats.get('practicas_cargadas', 0)}",
                f"Sin estudiante: {stats.get('sin_estudiante', 0)}",
            ]
            if stats.get("errores"):
                run.status = "partial"
                run.errores = stats["errores"]
                log_lines.append(f"Errores: {len(stats['errores'])}")
            run.log_output = "\n".join(log_lines)
        except Exception as e:
            run.status = "error"
            run.errores = [{"error": str(e)}]
            run.log_output = f"ERROR: {e}"
        finally:
            run.finished_at = datetime.now(timezone.utc)
            db_session.commit()
            db_session.close()

    background_tasks.add_task(_run_practicas_etl)

    return {
        "message": f"{len(saved_files)} archivo(s) guardados. ETL de prácticas iniciado.",
        "archivos": saved_files,
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
