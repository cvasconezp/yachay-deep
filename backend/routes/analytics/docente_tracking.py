"""
Módulo: Seguimiento de Calificaciones Docentes.
Fuente: task_submissions + course_config (en vez de tabla DocenteTracking vacía).
Muestra qué docentes tienen actividades pendientes por calificar,
cuántas pendientes tienen y qué estudiantes faltan.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_
from pydantic import BaseModel

from ...database import get_db
from ...models import Student, TaskSubmission
from ...models.course_config import CourseConfig, SemesterConfig
from ...auth.jwt import get_current_user
from ...models.user import User

router = APIRouter(prefix="/analytics", tags=["analytics"])


# ── Response Models ──

class EstudiantePendiente(BaseModel):
    student_id: int
    nombre: str
    tareas_pendientes: int
    tareas_entregadas_sin_calificar: int
    ultima_entrega: Optional[str] = None

class CursoPendiente(BaseModel):
    codigo_curso: str
    asignatura: str
    grupo: Optional[str] = None
    total_tareas: int
    calificadas: int
    pendientes: int
    estudiantes_pendientes: list[EstudiantePendiente] = []

class DocenteTrackingStats(BaseModel):
    docente: str
    correo_docente: Optional[str] = None
    total_cursos: int = 0
    total_tareas: int = 0
    actividades_calificadas: int = 0
    actividades_pendientes: int = 0
    porcentaje_calificacion: float = 0.0
    promedio_dias_retraso: Optional[float] = None
    cursos: list[str] = []
    alerta: str = "ok"

    class Config:
        from_attributes = True


class ResumenDocenteTracking(BaseModel):
    total_docentes: int = 0
    promedio_general_calificacion: float = 0.0
    docentes_en_atencion: int = 0
    docentes_criticos: int = 0
    total_pendientes: int = 0


def _get_periodo_variants(db: Session):
    """Retorna semestre activo y sus variantes de periodo."""
    sem = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    if not sem or not sem.semestre:
        return None, None, ()
    pf = sem.semestre.strip()
    if pf.startswith("P"):
        return sem, pf, (pf, pf[1:])
    return sem, pf, (pf, f"P{pf}")


def _periodo_filter(periodo_variants):
    """Helper to build OR filter for periodo variants."""
    if len(periodo_variants) == 2:
        return or_(
            TaskSubmission.periodo == periodo_variants[0],
            TaskSubmission.periodo == periodo_variants[1],
        )
    return TaskSubmission.periodo == periodo_variants[0]


def _get_bloque_courses(db: Session, semconfig):
    """Retorna CourseConfig del bloque actual con docente asignado."""
    if not semconfig:
        return []
    bloque = semconfig.bloque_actual or "1"
    return db.query(CourseConfig).filter(
        CourseConfig.docente.isnot(None),
        CourseConfig.docente != "",
        or_(
            CourseConfig.bloque == bloque,
            CourseConfig.bloque == "ambos",
            CourseConfig.bloque.is_(None),
        ),
    ).all()


@router.get("/docente-tracking", response_model=list[DocenteTrackingStats])
def get_docente_tracking(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Estadísticas de calificación por docente, basadas en task_submissions."""
    semconfig, pf, periodo_variants = _get_periodo_variants(db)
    if not pf:
        return []

    cursos = _get_bloque_courses(db, semconfig)
    if not cursos:
        return []

    # Map codigo_avac -> course info
    curso_map = {}
    for c in cursos:
        if c.codigo_avac:
            curso_map[c.codigo_avac] = c

    # Group courses by docente
    docente_cursos = {}
    for c in cursos:
        doc = c.docente.strip()
        if doc not in docente_cursos:
            docente_cursos[doc] = {"correo": c.correo_docente, "cursos": []}
        docente_cursos[doc]["cursos"].append(c)

    # Query task_submissions for all relevant courses
    codigos = list(curso_map.keys())
    if not codigos:
        return []

    # Get latest snapshot per course
    latest_snap = db.query(
        TaskSubmission.codigo_curso,
        func.max(TaskSubmission.snapshot_date).label("max_snap"),
    ).filter(
        _periodo_filter(periodo_variants),
        TaskSubmission.codigo_curso.in_(codigos),
    ).group_by(TaskSubmission.codigo_curso).all()

    snap_map = {r.codigo_curso: r.max_snap for r in latest_snap}

    output = []
    for docente_name, info in docente_cursos.items():
        total_tareas = 0
        calificadas = 0
        pendientes = 0
        asignaturas = []

        for curso in info["cursos"]:
            cod = curso.codigo_avac
            snap = snap_map.get(cod)
            if not snap:
                continue

            stats = db.query(
                func.count(TaskSubmission.id).label("total"),
                func.sum(case((TaskSubmission.calificada == True, 1), else_=0)).label("cal"),
                func.sum(case((
                    (TaskSubmission.entregada == True) & (TaskSubmission.calificada == False), 1
                ), else_=0)).label("pend"),
            ).filter(
                TaskSubmission.codigo_curso == cod,
                TaskSubmission.snapshot_date == snap,
                _periodo_filter(periodo_variants),
            ).first()

            if stats and stats.total:
                total_tareas += stats.total
                calificadas += (stats.cal or 0)
                pendientes += (stats.pend or 0)
                label = curso.asignatura or cod
                if curso.grupo:
                    label = f"{label} (G{curso.grupo})"
                asignaturas.append(label)

        if total_tareas == 0:
            continue

        pct = round((calificadas / max(total_tareas, 1)) * 100, 1)

        if pct < 50:
            alerta = "critico"
        elif pct < 80:
            alerta = "atencion"
        else:
            alerta = "ok"

        output.append(DocenteTrackingStats(
            docente=docente_name,
            correo_docente=info["correo"],
            total_cursos=len(info["cursos"]),
            total_tareas=total_tareas,
            actividades_calificadas=calificadas,
            actividades_pendientes=pendientes,
            porcentaje_calificacion=pct,
            cursos=sorted(set(asignaturas)),
            alerta=alerta,
        ))

    output.sort(key=lambda x: (
        0 if x.alerta == "critico" else (1 if x.alerta == "atencion" else 2),
        x.porcentaje_calificacion,
    ))
    return output


@router.get("/docente-tracking/resumen", response_model=ResumenDocenteTracking)
def get_docente_tracking_resumen(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resumen general de seguimiento docente."""
    all_stats = get_docente_tracking(db=db, current_user=current_user)
    if not all_stats:
        return ResumenDocenteTracking()

    total_pend = sum(d.actividades_pendientes for d in all_stats)
    pcts = [d.porcentaje_calificacion for d in all_stats]
    criticos = sum(1 for d in all_stats if d.alerta == "critico")
    atencion = sum(1 for d in all_stats if d.alerta == "atencion")

    return ResumenDocenteTracking(
        total_docentes=len(all_stats),
        promedio_general_calificacion=round(sum(pcts) / len(pcts), 1) if pcts else 0,
        docentes_en_atencion=atencion,
        docentes_criticos=criticos,
        total_pendientes=total_pend,
    )


@router.get("/docente-tracking/{docente_name}")
def get_docente_tracking_detalle(
    docente_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Detalle por curso: para cada curso del docente, muestra tareas pendientes
    y los estudiantes que aún no han sido calificados.
    Cada codigo_avac es un grupo distinto (misma asignatura, diferente grupo).
    """
    semconfig, pf, periodo_variants = _get_periodo_variants(db)
    if not pf:
        return []

    # Get courses for this docente
    cursos = db.query(CourseConfig).filter(
        CourseConfig.docente == docente_name,
        CourseConfig.codigo_avac.isnot(None),
    ).all()

    if not cursos:
        return []

    result = []
    for curso in cursos:
        cod = curso.codigo_avac

        # Latest snapshot
        snap = db.query(func.max(TaskSubmission.snapshot_date)).filter(
            TaskSubmission.codigo_curso == cod,
            _periodo_filter(periodo_variants),
        ).scalar()

        if not snap:
            continue

        # Get all submissions for this course at latest snapshot
        subs = db.query(TaskSubmission).filter(
            TaskSubmission.codigo_curso == cod,
            TaskSubmission.snapshot_date == snap,
            _periodo_filter(periodo_variants),
        ).all()

        if not subs:
            continue

        total = len(subs)
        cal = sum(1 for s in subs if s.calificada)
        pend_subs = [s for s in subs if s.entregada and not s.calificada]

        # Group pending by student
        student_ids = list(set(s.student_id for s in pend_subs if s.student_id))
        student_names = {}
        if student_ids:
            students = db.query(Student.id, Student.nombre).filter(Student.id.in_(student_ids)).all()
            student_names = {s.id: s.nombre for s in students}

        # Build student pending list
        student_pend_map = {}
        for s in pend_subs:
            if s.student_id not in student_pend_map:
                student_pend_map[s.student_id] = {
                    "count": 0,
                    "last_entrega": None,
                }
            student_pend_map[s.student_id]["count"] += 1
            if s.fecha_entrega:
                curr = student_pend_map[s.student_id]["last_entrega"]
                if curr is None or s.fecha_entrega > curr:
                    student_pend_map[s.student_id]["last_entrega"] = s.fecha_entrega

        estudiantes_pend = []
        for sid, info in sorted(student_pend_map.items(), key=lambda x: -x[1]["count"]):
            estudiantes_pend.append(EstudiantePendiente(
                student_id=sid,
                nombre=student_names.get(sid, f"ID {sid}"),
                tareas_pendientes=info["count"],
                tareas_entregadas_sin_calificar=info["count"],
                ultima_entrega=info["last_entrega"].isoformat() if info["last_entrega"] else None,
            ))

        result.append(CursoPendiente(
            codigo_curso=cod,
            asignatura=curso.asignatura or cod,
            grupo=curso.grupo,
            total_tareas=total,
            calificadas=cal,
            pendientes=len(pend_subs),
            estudiantes_pendientes=estudiantes_pend,
        ))

    # Sort: most pending first
    result.sort(key=lambda x: -x.pendientes)
    return result
