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
      TercerasMatriculas/XXXXX_Reporte.xlsx         → terceras matrículas (oyentes condicionados)
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
            "TercerasMatriculas",
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


@router.get("/system/network-check")
async def network_check(
    current_user: User = Depends(require_admin),
):
    """Diagnóstico de red: verifica si Railway puede acceder a AVAC."""
    import socket
    import httpx
    from ..config import settings

    results = {"avac_base_url": settings.AVAC_BASE_URL}

    # Test 1: DNS resolution
    domain = "avac.ups.edu.ec"
    try:
        ip = socket.gethostbyname(domain)
        results["dns_resolved"] = True
        results["dns_ip"] = ip
    except socket.gaierror as e:
        results["dns_resolved"] = False
        results["dns_error"] = str(e)

    # Test 2: HTTP connectivity
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.head(
                f"{settings.AVAC_BASE_URL}/login/index.php",
                follow_redirects=True,
            )
            results["http_status"] = resp.status_code
            results["http_ok"] = resp.status_code < 400
            results["http_final_url"] = str(resp.url)
    except Exception as e:
        results["http_ok"] = False
        results["http_error"] = str(e)

    # Test 3: Microsoft SSO reachable
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.head(
                "https://login.microsoftonline.com",
                follow_redirects=True,
            )
            results["microsoft_sso_ok"] = resp.status_code < 400
    except Exception as e:
        results["microsoft_sso_ok"] = False
        results["microsoft_sso_error"] = str(e)

    results["all_ok"] = results.get("dns_resolved", False) and results.get("http_ok", False) and results.get("microsoft_sso_ok", False)
    return results


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


# ─────────────────────────────────────────────────────────────────────────────
# TRIGGER SCRAPING VIA GITHUB ACTIONS
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/etl/trigger-scraping")
async def trigger_scraping(
    mode: str = "full",
    current_user: User = Depends(require_admin),
):
    """
    Dispara el workflow de scraping en GitHub Actions.
    Requiere GITHUB_TOKEN configurado en las variables de entorno de Railway.
    mode: 'full' | 'ingresos' | 'tareas'
    """
    import httpx
    from ..config import settings

    if not settings.GITHUB_TOKEN:
        raise HTTPException(
            status_code=400,
            detail="GITHUB_TOKEN no configurado. Agrega un Personal Access Token "
                   "de GitHub (scope: repo o actions) como variable de entorno en Railway.",
        )

    if mode not in ("full", "ingresos", "tareas"):
        raise HTTPException(status_code=400, detail=f"Modo invalido: {mode}. Use full, ingresos o tareas.")

    url = f"https://api.github.com/repos/{settings.GITHUB_REPO}/actions/workflows/{settings.GITHUB_WORKFLOW}/dispatches"
    headers = {
        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {
        "ref": "main",
        "inputs": {"mode": mode},
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload, headers=headers)

    if resp.status_code == 204:
        return {
            "message": f"Scraping '{mode}' disparado en GitHub Actions. "
                       "Revisa el progreso en https://github.com/"
                       f"{settings.GITHUB_REPO}/actions",
            "mode": mode,
            "github_status": resp.status_code,
        }
    elif resp.status_code == 404:
        raise HTTPException(
            status_code=400,
            detail=f"Workflow '{settings.GITHUB_WORKFLOW}' no encontrado en "
                   f"{settings.GITHUB_REPO}. Verifica GITHUB_REPO y GITHUB_WORKFLOW.",
        )
    elif resp.status_code == 422:
        raise HTTPException(
            status_code=400,
            detail="Error 422: El workflow no acepta los inputs enviados. "
                   f"Respuesta de GitHub: {resp.text[:300]}",
        )
    else:
        raise HTTPException(
            status_code=500,
            detail=f"GitHub API respondio {resp.status_code}: {resp.text[:300]}",
        )




@router.get("/etl/scraping-progress")
async def get_scraping_progress(
    current_user: User = Depends(require_admin),
):
    """
    Consulta el estado del workflow de scraping más reciente en GitHub Actions.
    Calcula progreso basado en tiempo promedio de runs históricos.
    """
    import httpx
    from ..config import settings

    if not settings.GITHUB_TOKEN:
        return {"running": False, "error": "GITHUB_TOKEN no configurado"}

    headers = {
        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Get recent workflow runs (last 5 for avg calculation)
            resp = await client.get(
                f"https://api.github.com/repos/{settings.GITHUB_REPO}/actions/workflows/{settings.GITHUB_WORKFLOW}/runs?per_page=5",
                headers=headers,
            )
            if resp.status_code != 200:
                return {"running": False, "error": f"GitHub API: {resp.status_code}"}

            data = resp.json()
            runs = data.get("workflow_runs", [])
            if not runs:
                return {"running": False, "message": "No hay ejecuciones recientes"}

            run = runs[0]
            run_status = run.get("status")  # queued, in_progress, completed
            run_conclusion = run.get("conclusion")  # success, failure, cancelled, null
            run_started = run.get("run_started_at")
            run_updated = run.get("updated_at")

            # Calculate average duration from recent successful runs
            avg_duration_secs = None
            completed_durations = []
            for r in runs[1:]:  # Skip current, use previous runs
                if r.get("conclusion") == "success" and r.get("run_started_at") and r.get("updated_at"):
                    try:
                        from datetime import datetime as _dt
                        started = _dt.fromisoformat(r["run_started_at"].replace("Z", "+00:00"))
                        updated = _dt.fromisoformat(r["updated_at"].replace("Z", "+00:00"))
                        dur = (updated - started).total_seconds()
                        if dur > 60:  # At least 1 minute
                            completed_durations.append(dur)
                    except Exception:
                        pass
            if completed_durations:
                avg_duration_secs = sum(completed_durations) / len(completed_durations)
            else:
                # Fallback: estimate 40 min if no historical successful runs
                avg_duration_secs = 40 * 60

            # Calculate time-based progress
            elapsed_secs = 0
            if run_started:
                from datetime import datetime as _dt, timezone as _tz
                started_dt = _dt.fromisoformat(run_started.replace("Z", "+00:00"))
                elapsed_secs = (_dt.now(_tz.utc) - started_dt).total_seconds()

            time_progress = None
            if avg_duration_secs and elapsed_secs > 0 and run_status == "in_progress":
                pct = min(round(elapsed_secs / avg_duration_secs * 100), 99)
                remaining_secs = max(avg_duration_secs - elapsed_secs, 0)
                remaining_min = round(remaining_secs / 60)
                time_progress = {
                    "percent": pct,
                    "elapsed_min": round(elapsed_secs / 60),
                    "estimated_total_min": round(avg_duration_secs / 60),
                    "remaining_min": remaining_min,
                    "based_on_runs": len(completed_durations),
                    "is_estimate": len(completed_durations) == 0,
                }

            result = {
                "running": run_status in ("queued", "in_progress"),
                "status": run_status,
                "conclusion": run_conclusion,
                "started_at": run_started,
                "updated_at": run_updated,
                "html_url": run.get("html_url"),
                "run_id": run.get("id"),
                "time_progress": time_progress,
            }

            # Also include step-level info if running
            if run_status in ("queued", "in_progress"):
                jobs_resp = await client.get(
                    f"https://api.github.com/repos/{settings.GITHUB_REPO}/actions/runs/{run['id']}/jobs",
                    headers=headers,
                )
                if jobs_resp.status_code == 200:
                    jobs_data = jobs_resp.json()
                    jobs = jobs_data.get("jobs", [])
                    if jobs:
                        job = jobs[0]
                        steps = job.get("steps", [])
                        current_step = None
                        completed_steps = 0
                        total_steps = len(steps)
                        for s in steps:
                            if s.get("status") == "completed":
                                completed_steps += 1
                            elif s.get("status") == "in_progress":
                                current_step = s.get("name")
                        result["current_step"] = current_step
                        result["steps_completed"] = completed_steps
                        result["steps_total"] = total_steps
                        # Step-based progress as fallback/complement
                        if total_steps > 0:
                            result["step_progress_pct"] = min(round(completed_steps / total_steps * 100), 99)

            return result

    except Exception as e:
        return {"running": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# AVAC SESSION COOKIE MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

class CookieUpdate(BaseModel):
    cookie: str

@router.put("/system/avac-cookie")
async def update_avac_cookie(
    body: CookieUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Actualiza la cookie MoodleSession para el scraping sin Selenium.

    Flujo: el admin inicia sesión en AVAC desde su navegador,
    copia la cookie MoodleSession, y la pega aquí.
    Se guarda en la base de datos (persiste entre redeployments)
    y en memoria para uso inmediato.
    """
    import httpx
    from ..config import settings
    from ..models.system_setting import SystemSetting

    cookie_val = body.cookie.strip()
    if not cookie_val:
        raise HTTPException(status_code=400, detail="Cookie vacía")

    # Validate the cookie works using httpx (available in requirements.txt)
    cookies = {"MoodleSession": cookie_val}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.0.0"}

    try:
        async with httpx.AsyncClient(cookies=cookies, headers=headers, follow_redirects=True, timeout=15) as client:
            resp = await client.get(f"{settings.AVAC_BASE_URL}/my/")
            if "login/index.php" in str(resp.url):
                raise HTTPException(
                    status_code=400,
                    detail="Cookie inválida o expirada — redirige a login. Inicia sesión en AVAC y copia una cookie nueva."
                )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Error conectando a AVAC: {e}")

    # Persist in database (survives redeployments)
    SystemSetting.set(db, "avac_session_cookie", cookie_val)

    # Also keep in memory for immediate use
    os.environ["AVAC_SESSION_COOKIE"] = cookie_val
    settings.AVAC_SESSION_COOKIE = cookie_val

    return {
        "message": "Cookie MoodleSession actualizada, validada y guardada en BD",
        "avac_url": str(resp.url),
        "status": "valid",
    }


@router.get("/system/avac-cookie")
async def check_avac_cookie(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Verifica si hay una cookie MoodleSession configurada y si aún es válida."""
    import httpx
    from ..config import settings
    from ..models.system_setting import SystemSetting

    # Read from DB first (persistent), fall back to env/settings (legacy)
    cookie_val = SystemSetting.get(db, "avac_session_cookie") or settings.AVAC_SESSION_COOKIE
    if not cookie_val:
        return {"configured": False, "message": "No hay cookie configurada. Usa PUT para establecerla."}

    # Sync to memory if loaded from DB
    if cookie_val != settings.AVAC_SESSION_COOKIE:
        os.environ["AVAC_SESSION_COOKIE"] = cookie_val
        settings.AVAC_SESSION_COOKIE = cookie_val

    cookies = {"MoodleSession": cookie_val}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.0.0"}

    try:
        async with httpx.AsyncClient(cookies=cookies, headers=headers, follow_redirects=True, timeout=15) as client:
            resp = await client.get(f"{settings.AVAC_BASE_URL}/my/")
            is_valid = "login/index.php" not in str(resp.url)
        return {
            "configured": True,
            "valid": is_valid,
            "message": "Cookie válida — sesión activa" if is_valid else "Cookie expirada — necesita actualización",
            "cookie_preview": f"{cookie_val[:6]}...{cookie_val[-4:]}" if len(cookie_val) > 10 else "***",
        }
    except Exception as e:
        return {"configured": True, "valid": False, "message": f"Error verificando: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# Debug: diagnóstico AVAC por estudiante
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/debug/student-avac/{student_id}")
def debug_student_avac(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Diagnóstico de datos AVAC para un estudiante específico.
    
    Retorna: correo, task_submissions, accesos AVAC, calificaciones,
    y posibles problemas de matching.
    """
    from ..models import Student, AvacAccess, TaskSubmission, Grade, Enrollment
    from ..models.course_config import SemesterConfig

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return {"error": f"Estudiante {student_id} no encontrado"}

    # Periodo activo
    sem = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    active_p = sem.semestre if sem else None

    # Contar task_submissions
    ts_total = db.query(sqlfunc.count(TaskSubmission.id)).filter(
        TaskSubmission.student_id == student_id
    ).scalar()
    
    ts_by_periodo = db.query(
        TaskSubmission.periodo,
        TaskSubmission.snapshot_date,
        sqlfunc.count(TaskSubmission.id)
    ).filter(
        TaskSubmission.student_id == student_id
    ).group_by(TaskSubmission.periodo, TaskSubmission.snapshot_date).all()

    # Contar accesos AVAC
    avac_total = db.query(sqlfunc.count(AvacAccess.id)).filter(
        AvacAccess.student_id == student_id
    ).scalar()

    # Contar calificaciones
    grades_total = db.query(sqlfunc.count(Grade.id)).filter(
        Grade.student_id == student_id
    ).scalar()
    
    grades_by_periodo = db.query(
        Grade.periodo, sqlfunc.count(Grade.id)
    ).filter(
        Grade.student_id == student_id
    ).group_by(Grade.periodo).all()

    # Enrollments
    enrollments = db.query(sqlfunc.count(Enrollment.id)).filter(
        Enrollment.student_id == student_id
    ).scalar()

    # Buscar si existe otro estudiante con correo similar
    posibles_duplicados = []
    if student.correo_institucional:
        base = student.correo_institucional.split("@")[0]
        dupes = db.query(Student).filter(
            Student.id != student_id,
            Student.correo_institucional.ilike(f"%{base}%")
        ).limit(5).all()
        posibles_duplicados = [
            {"id": d.id, "nombre": d.nombre, "correo_inst": d.correo_institucional}
            for d in dupes
        ]

    return {
        "estudiante": {
            "id": student.id,
            "nombre": student.nombre,
            "correo_institucional": student.correo_institucional,
            "correo_personal": student.correo,
            "cedula": student.cedula,
            "carrera": student.carrera,
        },
        "periodo_activo": active_p,
        "task_submissions": {
            "total": ts_total,
            "por_periodo_snapshot": [
                {"periodo": p, "snapshot": str(s) if s else None, "count": c}
                for p, s, c in ts_by_periodo
            ],
        },
        "accesos_avac": {"total": avac_total},
        "calificaciones": {
            "total": grades_total,
            "por_periodo": [
                {"periodo": p, "count": c} for p, c in grades_by_periodo
            ],
        },
        "enrollments": enrollments,
        "posibles_duplicados": posibles_duplicados,
        "diagnostico": (
            "✅ Tiene datos AVAC" if ts_total > 0
            else "⚠️ SIN task_submissions — posible problema de matching correo o scraping no procesó sus cursos"
        ),
    }


@router.get("/debug/student-search")
def debug_student_search(
    q: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Busca estudiante por nombre/correo para diagnóstico."""
    from ..models import Student
    
    if len(q) < 2:
        return {"results": []}
    
    students = db.query(Student).filter(
        sqlfunc.lower(Student.nombre).contains(q.lower())
        | sqlfunc.lower(Student.correo_institucional).contains(q.lower())
        | sqlfunc.lower(Student.cedula).contains(q.lower())
    ).limit(10).all()
    
    return {"results": [
        {"id": s.id, "nombre": s.nombre, "correo_inst": s.correo_institucional, "cedula": s.cedula}
        for s in students
    ]}


@router.get("/debug/bloque-filter/{student_id}")
def debug_bloque_filter(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Diagnóstico del filtro de bloque para un estudiante específico."""
    from ..models import Student, AvacAccess
    from ..models.course_config import CourseConfig, SemesterConfig
    from ..models.enrollment import Enrollment
    from sqlalchemy import func as sqf, or_

    student = db.query(Student).get(student_id)
    if not student:
        return {"error": "Student not found"}

    semconfig = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    bloque_actual = semconfig.bloque_actual if semconfig else None

    # All CourseConfig entries
    all_cc = db.query(CourseConfig.codigo_avac, CourseConfig.bloque, CourseConfig.asignatura).filter(
        CourseConfig.codigo_avac.isnot(None),
    ).all()
    all_courses = {r[0]: {"bloque": r[1], "asignatura": r[2]} for r in all_cc}

    # Exclusion logic
    excluded_codes = set()
    if bloque_actual:
        other_bloque = "2" if bloque_actual == "1" else "1"
        excluded_cc = db.query(CourseConfig.codigo_avac).filter(
            CourseConfig.bloque == other_bloque,
        ).all()
        excluded_codes = {r[0] for r in excluded_cc if r[0]}
        other_bloque_int = int(other_bloque)
        excluded_enroll = db.query(Enrollment.codigo_grupo).filter(
            Enrollment.codigo_grupo.isnot(None),
            Enrollment.bloque == other_bloque_int,
        ).distinct().all()
        excluded_codes |= {r[0] for r in excluded_enroll if r[0]}

    # Build enrollment bloque map
    enroll_bloque_map = {}
    for eg, eb in db.query(Enrollment.codigo_grupo, Enrollment.bloque).filter(
        Enrollment.codigo_grupo.isnot(None), Enrollment.bloque.isnot(None)
    ).distinct().all():
        enroll_bloque_map[eg] = eb

    included_codes = {r[0] for r in all_cc if r[0]} - excluded_codes

    # Student's AvacAccess records
    avac_records = db.query(
        AvacAccess.codigo_curso, AvacAccess.dias_sin_acceso, AvacAccess.snapshot_date,
    ).filter(
        AvacAccess.student_id == student_id,
        AvacAccess.dias_sin_acceso.isnot(None),
    ).order_by(AvacAccess.snapshot_date.desc()).limit(20).all()

    avac_list = []
    for r in avac_records:
        cc_info = all_courses.get(r[0], {})
        avac_list.append({
            "codigo_curso": r[0],
            "dias_sin_acceso": r[1],
            "snapshot_date": str(r[2]) if r[2] else None,
            "bloque": cc_info.get("bloque"),
            "asignatura": cc_info.get("asignatura"),
            "included": r[0] in included_codes,
            "in_courseconfig": r[0] in all_courses,
            "enrollment_bloque": enroll_bloque_map.get(r[0]),
        })

    # What the alerts endpoint would calculate
    bloque_course_codes = included_codes
    dias_calculated = None
    if bloque_course_codes:
        latest_snap = db.query(sqf.max(AvacAccess.snapshot_date)).filter(
            AvacAccess.student_id == student_id,
            AvacAccess.dias_sin_acceso.isnot(None),
            AvacAccess.codigo_curso.in_(bloque_course_codes),
        ).scalar()
        if latest_snap:
            max_dias = db.query(sqf.max(AvacAccess.dias_sin_acceso)).filter(
                AvacAccess.student_id == student_id,
                AvacAccess.dias_sin_acceso.isnot(None),
                AvacAccess.codigo_curso.in_(bloque_course_codes),
                AvacAccess.snapshot_date == latest_snap,
            ).scalar()
            dias_calculated = int(max_dias) if max_dias is not None else None

    return {
        "student": {"id": student.id, "nombre": student.nombre, "dias_sin_acceso_stored": student.dias_sin_acceso},
        "bloque_actual": bloque_actual,
        "total_courses_in_config": len(all_courses),
        "excluded_codes_count": len(excluded_codes),
        "included_codes_count": len(included_codes),
        "dias_calculated_for_alerts": dias_calculated,
        "avac_records": avac_list,
    }


@router.get("/debug/task-submissions/{codigo_curso}")
def debug_task_submissions(
    codigo_curso: str,
    unidad: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Diagnóstico: muestra task_submissions para un curso dado.
    Útil para investigar discrepancias entre AVAC y Yachay.
    """
    from ..models import TaskSubmission, Student
    from ..models.course_config import SemesterConfig
    from sqlalchemy import func as sqf, or_

    sem = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    if not sem:
        return {"error": "No hay semestre activo"}

    pf = sem.semestre.strip()
    periodo_variants = (pf, pf[1:]) if pf.startswith("P") else (pf, f"P{pf}")

    # Latest snapshot
    snap = db.query(sqf.max(TaskSubmission.snapshot_date)).filter(
        TaskSubmission.codigo_curso == codigo_curso,
        or_(TaskSubmission.periodo == periodo_variants[0], TaskSubmission.periodo == periodo_variants[1]),
    ).scalar()

    if not snap:
        return {"error": f"No hay snapshots para curso {codigo_curso}", "periodo_variants": periodo_variants}

    q = db.query(TaskSubmission).filter(
        TaskSubmission.codigo_curso == codigo_curso,
        TaskSubmission.snapshot_date == snap,
        or_(TaskSubmission.periodo == periodo_variants[0], TaskSubmission.periodo == periodo_variants[1]),
    )
    if unidad:
        q = q.filter(TaskSubmission.unidad == unidad)

    subs = q.all()

    # Get student names
    student_ids = list(set(s.student_id for s in subs if s.student_id))
    names = {}
    if student_ids:
        rows = db.query(Student.id, Student.nombre).filter(Student.id.in_(student_ids)).all()
        names = {r.id: r.nombre for r in rows}

    records = []
    for s in subs:
        records.append({
            "id": s.id,
            "student": names.get(s.student_id, f"ID {s.student_id}"),
            "unidad": s.unidad,
            "estado": s.estado,
            "entregada": s.entregada,
            "calificada": s.calificada,
            "calificacion": s.calificacion,
            "calificacion_maxima": s.calificacion_maxima,
            "calificacion_final": s.calificacion_final,
            "calificacion_texto": s.calificacion_texto,
            "fecha_entrega": s.fecha_entrega.isoformat() if s.fecha_entrega else None,
            "fecha_calificacion": s.fecha_calificacion.isoformat() if s.fecha_calificacion else None,
            "snapshot_date": str(s.snapshot_date),
        })

    # Summary
    by_unidad = {}
    for r in records:
        u = r["unidad"] or "?"
        if u not in by_unidad:
            by_unidad[u] = {"total": 0, "entregada": 0, "calificada": 0, "not_calificada_but_entregada": 0}
        by_unidad[u]["total"] += 1
        if r["entregada"]:
            by_unidad[u]["entregada"] += 1
        if r["calificada"]:
            by_unidad[u]["calificada"] += 1
        if r["entregada"] and not r["calificada"]:
            by_unidad[u]["not_calificada_but_entregada"] += 1

    return {
        "codigo_curso": codigo_curso,
        "snapshot_date": str(snap),
        "periodo_variants": periodo_variants,
        "total_records": len(records),
        "summary_by_unidad": by_unidad,
        "records": records,
    }
