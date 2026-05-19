"""
Módulo: Seguimiento de Calificaciones Docentes.
Fuente: task_submissions + course_config (en vez de tabla DocenteTracking vacía).
Muestra qué docentes tienen actividades pendientes por calificar,
cuántas pendientes tienen y qué estudiantes faltan — desglosado por actividad.
"""
from typing import Optional
from collections import defaultdict
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

class ActividadPendiente(BaseModel):
    """Desglose de una actividad (unidad) dentro de un curso."""
    actividad: str                # "Actividad 1", "Actividad 2", etc.
    unidad: str                   # "1", "2", "3", "4"
    total: int                    # total entregas en esta actividad
    calificadas: int
    pendientes: int
    estudiantes_pendientes: list[EstudiantePendiente] = []

class CursoPendiente(BaseModel):
    codigo_curso: str
    asignatura: str
    grupo: Optional[str] = None
    total_tareas: int
    calificadas: int
    pendientes: int
    actividades: list[ActividadPendiente] = []
    # Keep flat student list for backwards compat
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
    carreras: list[str] = []
    alerta: str = "ok"

    class Config:
        from_attributes = True


class ResumenDocenteTracking(BaseModel):
    total_docentes: int = 0
    promedio_general_calificacion: float = 0.0
    docentes_en_atencion: int = 0
    docentes_criticos: int = 0
    total_pendientes: int = 0
    snapshot_date: Optional[str] = None
    dias_desde_snapshot: Optional[int] = None


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


def _get_unidades_vencidas(semconfig) -> set:
    """Retorna set de unidades cuya fecha de entrega ya pasó según calendario."""
    import json
    from ...services.alert_generator import _unidades_vencidas
    calendario = []
    if semconfig and semconfig.calendario_academico:
        try:
            calendario = json.loads(semconfig.calendario_academico)
        except Exception:
            pass
    return _unidades_vencidas(calendario)


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

    unidades_vencidas = _get_unidades_vencidas(semconfig)

    curso_map = {}
    for c in cursos:
        if c.codigo_avac:
            curso_map[c.codigo_avac] = c

    docente_cursos = {}
    for c in cursos:
        doc = c.docente.strip()
        if doc not in docente_cursos:
            docente_cursos[doc] = {"correo": c.correo_docente, "cursos": []}
        docente_cursos[doc]["cursos"].append(c)

    codigos = list(curso_map.keys())
    if not codigos:
        return []

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

            stats_q = db.query(
                func.count(TaskSubmission.id).label("total"),
                func.sum(case((TaskSubmission.calificada == True, 1), else_=0)).label("cal"),
                func.sum(case((
                    (TaskSubmission.entregada == True) & (TaskSubmission.calificada == False), 1
                ), else_=0)).label("pend"),
            ).filter(
                TaskSubmission.codigo_curso == cod,
                TaskSubmission.snapshot_date == snap,
                _periodo_filter(periodo_variants),
            )
            # Solo contar actividades cuya fecha de entrega ya pasó
            if unidades_vencidas and unidades_vencidas != {"1", "2", "3", "4"}:
                stats_q = stats_q.filter(TaskSubmission.unidad.in_(unidades_vencidas))
            stats = stats_q.first()

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
        alerta = "critico" if pct < 50 else ("atencion" if pct < 80 else "ok")

        # Collect unique carreras from this docente's courses
        docente_carreras = sorted(set(
            c.carrera for c in info["cursos"] if c.carrera
        ))

        output.append(DocenteTrackingStats(
            docente=docente_name,
            correo_docente=info["correo"],
            total_cursos=len(info["cursos"]),
            total_tareas=total_tareas,
            actividades_calificadas=calificadas,
            actividades_pendientes=pendientes,
            porcentaje_calificacion=pct,
            cursos=sorted(set(asignaturas)),
            carreras=docente_carreras,
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

    # Obtener fecha del snapshot más reciente de task_submissions
    from datetime import date as date_type
    latest_snap = db.query(func.max(TaskSubmission.snapshot_date)).scalar()
    snap_str = str(latest_snap) if latest_snap else None
    dias_stale = (date_type.today() - latest_snap).days if latest_snap else None

    if not all_stats:
        return ResumenDocenteTracking(
            snapshot_date=snap_str,
            dias_desde_snapshot=dias_stale,
        )

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
        snapshot_date=snap_str,
        dias_desde_snapshot=dias_stale,
    )


@router.get("/docente-tracking/{docente_name}")
def get_docente_tracking_detalle(
    docente_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Detalle por curso: para cada curso del docente, muestra tareas pendientes
    desglosadas por actividad (unidad 1-4) y estudiantes sin calificar.
    """
    semconfig, pf, periodo_variants = _get_periodo_variants(db)
    if not pf:
        return []

    unidades_vencidas = _get_unidades_vencidas(semconfig)

    cursos = db.query(CourseConfig).filter(
        CourseConfig.docente == docente_name,
        CourseConfig.codigo_avac.isnot(None),
    ).all()

    if not cursos:
        return []

    result = []
    for curso in cursos:
        cod = curso.codigo_avac

        snap = db.query(func.max(TaskSubmission.snapshot_date)).filter(
            TaskSubmission.codigo_curso == cod,
            _periodo_filter(periodo_variants),
        ).scalar()

        if not snap:
            continue

        subs = db.query(TaskSubmission).filter(
            TaskSubmission.codigo_curso == cod,
            TaskSubmission.snapshot_date == snap,
            _periodo_filter(periodo_variants),
        ).all()

        if not subs:
            continue

        # Filtrar solo actividades cuya fecha de entrega ya pasó
        if unidades_vencidas and unidades_vencidas != {"1", "2", "3", "4"}:
            subs = [s for s in subs if s.unidad in unidades_vencidas]
            if not subs:
                continue

        # Collect all student IDs for name lookup
        all_student_ids = list(set(s.student_id for s in subs if s.student_id))
        student_names = {}
        if all_student_ids:
            students = db.query(Student.id, Student.nombre).filter(
                Student.id.in_(all_student_ids)
            ).all()
            student_names = {s.id: s.nombre for s in students}

        total = len(subs)
        cal = sum(1 for s in subs if s.calificada)
        pend_subs = [s for s in subs if s.entregada and not s.calificada]

        # ── Group by unidad (actividad) ──
        by_unidad = defaultdict(list)
        all_by_unidad = defaultdict(list)
        for s in subs:
            u = s.unidad or "?"
            all_by_unidad[u].append(s)
            if s.entregada and not s.calificada:
                by_unidad[u].append(s)

        actividades = []
        for u in sorted(all_by_unidad.keys(), key=lambda x: (x if x != "?" else "z")):
            u_subs = all_by_unidad[u]
            u_pend = by_unidad.get(u, [])
            u_total = len(u_subs)
            u_cal = sum(1 for s in u_subs if s.calificada)

            # Build student list for this activity
            student_pend_map = {}
            for s in u_pend:
                sid = s.student_id
                if sid not in student_pend_map:
                    student_pend_map[sid] = {"count": 0, "last_entrega": None}
                student_pend_map[sid]["count"] += 1
                if s.fecha_entrega:
                    curr = student_pend_map[sid]["last_entrega"]
                    if curr is None or s.fecha_entrega > curr:
                        student_pend_map[sid]["last_entrega"] = s.fecha_entrega

            est_list = []
            for sid, info in sorted(student_pend_map.items(), key=lambda x: -x[1]["count"]):
                est_list.append(EstudiantePendiente(
                    student_id=sid,
                    nombre=student_names.get(sid, f"ID {sid}"),
                    tareas_pendientes=info["count"],
                    tareas_entregadas_sin_calificar=info["count"],
                    ultima_entrega=info["last_entrega"].isoformat() if info["last_entrega"] else None,
                ))

            actividades.append(ActividadPendiente(
                actividad=f"Actividad {u}" if u != "?" else "Sin clasificar",
                unidad=u,
                total=u_total,
                calificadas=u_cal,
                pendientes=len(u_pend),
                estudiantes_pendientes=est_list,
            ))

        # Flat student list (all activities combined) for backwards compat
        all_pend_map = {}
        for s in pend_subs:
            sid = s.student_id
            if sid not in all_pend_map:
                all_pend_map[sid] = {"count": 0, "last_entrega": None}
            all_pend_map[sid]["count"] += 1
            if s.fecha_entrega:
                curr = all_pend_map[sid]["last_entrega"]
                if curr is None or s.fecha_entrega > curr:
                    all_pend_map[sid]["last_entrega"] = s.fecha_entrega

        flat_students = []
        for sid, info in sorted(all_pend_map.items(), key=lambda x: -x[1]["count"]):
            flat_students.append(EstudiantePendiente(
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
            actividades=actividades,
            estudiantes_pendientes=flat_students,
        ))

    result.sort(key=lambda x: -x.pendientes)
    return result
