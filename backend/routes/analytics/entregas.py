"""
Reporte de entregas pendientes por actividad.
Muestra qué estudiantes NO entregaron cada actividad (unidad) de cada asignatura.

[BUG-FIX] Usa solo el snapshot más reciente para evitar duplicados históricos
que generaban falsos positivos (estudiantes que entregaron aparecían como pendientes
porque tenían un registro viejo con entregada=False).
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, case, and_

from ...database import get_db
from ...auth.jwt import get_current_user
from ...models.user import User
from ...models.student import Student
from ...models.task_submission import TaskSubmission
from ...models.course_config import CourseConfig, SemesterConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["entregas"])


def _get_active_periodo_variants(db: Session):
    """Devuelve tupla (periodo_P, periodo_num) del semestre activo."""
    sc = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    if not sc or not sc.semestre:
        return None, None
    p = sc.semestre.strip()
    if p.startswith("P"):
        return p, p[1:]
    return f"P{p}", p


def _build_periodo_filter(periodo_p, periodo_num):
    """Construye filtro SQLAlchemy para periodo activo."""
    if periodo_p:
        return or_(
            TaskSubmission.periodo == periodo_p,
            TaskSubmission.periodo == periodo_num,
            TaskSubmission.periodo.is_(None),
        )
    return TaskSubmission.periodo.is_(None)


def _get_codigos_excluir(db: Session) -> set:
    """Devuelve códigos de cursos del bloque opuesto a excluir."""
    sc = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    if not sc:
        return set()
    otro_bloque = "2" if (sc.bloque_actual or "1") == "1" else "1"
    excl = db.query(CourseConfig.codigo_avac).filter(CourseConfig.bloque == otro_bloque).all()
    return {r[0] for r in excl if r[0]}


def _get_latest_snapshot_date(db: Session, periodo_filter, codigos_excluir: set):
    """Encuentra la fecha del snapshot más reciente."""
    q = db.query(func.max(TaskSubmission.snapshot_date)).filter(periodo_filter)
    if codigos_excluir:
        q = q.filter(~TaskSubmission.codigo_curso.in_(codigos_excluir))
    return q.scalar()


@router.get("/entregas-pendientes")
def entregas_pendientes(
    carrera: str = Query("", description="Filtrar por carrera"),
    asignatura: str = Query("", description="Filtrar por asignatura (nombre parcial)"),
    unidad: str = Query("", description="Filtrar por unidad: 1, 2, 3, 4"),
    codigo_curso: str = Query("", description="Filtrar por código AVAC del curso"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Reporte de entregas pendientes: por cada actividad (curso + unidad),
    lista los estudiantes que NO entregaron.

    Usa SOLO el snapshot más reciente para evitar duplicados históricos.
    """
    periodo_p, periodo_num = _get_active_periodo_variants(db)
    periodo_filter = _build_periodo_filter(periodo_p, periodo_num)
    codigos_excluir = _get_codigos_excluir(db)

    # Encontrar el snapshot más reciente
    latest_date = _get_latest_snapshot_date(db, periodo_filter, codigos_excluir)
    if not latest_date:
        return {"actividades": [], "resumen": {"total_actividades": 0, "total_pendientes": 0}}

    # Filtro base: periodo + snapshot más reciente + excluir bloque opuesto
    base_filters = [
        periodo_filter,
        TaskSubmission.student_id.isnot(None),
        TaskSubmission.snapshot_date == latest_date,
    ]
    if codigos_excluir:
        base_filters.append(~TaskSubmission.codigo_curso.in_(codigos_excluir))

    # Todos los cursos+unidades del snapshot más reciente
    base_q = db.query(
        TaskSubmission.codigo_curso,
        TaskSubmission.unidad,
    ).filter(*base_filters)

    if codigo_curso:
        base_q = base_q.filter(TaskSubmission.codigo_curso == codigo_curso.strip())

    actividades_unicas = base_q.distinct().all()

    # Map de CourseConfig para nombres
    all_codigos = {a[0] for a in actividades_unicas}
    cc_map = {}
    if all_codigos:
        for cc in db.query(CourseConfig).filter(CourseConfig.codigo_avac.in_(all_codigos)).all():
            cc_map[cc.codigo_avac] = cc

    # Filtros de carrera y asignatura
    if carrera:
        carrera_lower = carrera.strip().lower()
        filtered_codigos = {
            cod for cod, cc in cc_map.items()
            if cc.carrera and carrera_lower in cc.carrera.lower()
        }
        actividades_unicas = [(c, u) for c, u in actividades_unicas if c in filtered_codigos]

    if asignatura:
        asig_lower = asignatura.strip().lower()
        filtered_codigos = {
            cod for cod, cc in cc_map.items()
            if cc.asignatura and asig_lower in cc.asignatura.lower()
        }
        actividades_unicas = [(c, u) for c, u in actividades_unicas if c in filtered_codigos]

    if unidad:
        actividades_unicas = [(c, u) for c, u in actividades_unicas if u == unidad.strip()]

    resultado = []
    total_pendientes = 0

    for cod_curso, uni in sorted(actividades_unicas, key=lambda x: (x[0], x[1] or "")):
        cc = cc_map.get(cod_curso)

        # Solo registros del snapshot más reciente
        subs = (
            db.query(
                TaskSubmission.student_id,
                TaskSubmission.entregada,
                TaskSubmission.estado,
            )
            .filter(
                TaskSubmission.codigo_curso == cod_curso,
                TaskSubmission.unidad == uni,
                TaskSubmission.snapshot_date == latest_date,
                periodo_filter,
                TaskSubmission.student_id.isnot(None),
            )
            .all()
        )

        if not subs:
            continue

        # Deduplicar por student_id: si hay varios registros, priorizar entregada=True
        by_student = {}
        for s in subs:
            if s.student_id not in by_student or (s.entregada and not by_student[s.student_id].entregada):
                by_student[s.student_id] = s

        unique_subs = list(by_student.values())
        total = len(unique_subs)
        entregaron = sum(1 for s in unique_subs if s.entregada)
        no_entregaron_ids = [s.student_id for s in unique_subs if not s.entregada]
        estados_por_id = {s.student_id: s.estado for s in unique_subs if not s.entregada}

        pendientes = []
        if no_entregaron_ids:
            students = (
                db.query(Student.id, Student.nombre, Student.correo_institucional, Student.correo)
                .filter(Student.id.in_(no_entregaron_ids))
                .all()
            )
            for st in students:
                pendientes.append({
                    "student_id": st.id,
                    "nombre": st.nombre or "—",
                    "correo": st.correo_institucional or st.correo or "—",
                    "estado": estados_por_id.get(st.id) or "Sin entregar",
                })
            pendientes.sort(key=lambda x: x["nombre"])

        total_pendientes += len(pendientes)

        resultado.append({
            "codigo_curso": cod_curso,
            "asignatura": cc.asignatura if cc else cod_curso,
            "docente": cc.docente if cc else None,
            "carrera": cc.carrera if cc else None,
            "unidad": uni,
            "total_estudiantes": total,
            "entregaron": entregaron,
            "no_entregaron": len(pendientes),
            "pct_entrega": round(entregaron / total * 100, 1) if total > 0 else 0,
            "pendientes": pendientes,
        })

    # Ordenar: primero las actividades con más pendientes
    resultado.sort(key=lambda x: x["no_entregaron"], reverse=True)

    return {
        "actividades": resultado,
        "resumen": {
            "total_actividades": len(resultado),
            "total_pendientes": total_pendientes,
        },
    }


@router.get("/entregas-resumen")
def entregas_resumen(
    carrera: str = Query("", description="Filtrar por carrera"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Resumen compacto de entregas: por cada curso, % de entrega por unidad.
    Usa SOLO el snapshot más reciente.
    """
    periodo_p, periodo_num = _get_active_periodo_variants(db)
    periodo_filter = _build_periodo_filter(periodo_p, periodo_num)
    codigos_excluir = _get_codigos_excluir(db)

    latest_date = _get_latest_snapshot_date(db, periodo_filter, codigos_excluir)
    if not latest_date:
        return {"cursos": []}

    q = db.query(
        TaskSubmission.codigo_curso,
        TaskSubmission.unidad,
        func.count(TaskSubmission.id).label("total"),
        func.sum(case((TaskSubmission.entregada == True, 1), else_=0)).label("entregadas"),
    ).filter(
        periodo_filter,
        TaskSubmission.student_id.isnot(None),
        TaskSubmission.snapshot_date == latest_date,
    )

    if codigos_excluir:
        q = q.filter(~TaskSubmission.codigo_curso.in_(codigos_excluir))

    rows = q.group_by(TaskSubmission.codigo_curso, TaskSubmission.unidad).all()

    # Map de CourseConfig
    all_codigos = {r[0] for r in rows}
    cc_map = {}
    if all_codigos:
        for cc in db.query(CourseConfig).filter(CourseConfig.codigo_avac.in_(all_codigos)).all():
            cc_map[cc.codigo_avac] = cc

    if carrera:
        carrera_lower = carrera.strip().lower()
        rows = [r for r in rows if cc_map.get(r[0]) and carrera_lower in (cc_map[r[0]].carrera or "").lower()]

    # Agrupar por curso
    cursos = {}
    for cod, uni, total, entregadas in rows:
        if cod not in cursos:
            cc = cc_map.get(cod)
            cursos[cod] = {
                "codigo_curso": cod,
                "asignatura": cc.asignatura if cc else cod,
                "docente": cc.docente if cc else None,
                "carrera": cc.carrera if cc else None,
                "unidades": {},
            }
        cursos[cod]["unidades"][uni] = {
            "total": total,
            "entregadas": entregadas,
            "pct": round(entregadas / total * 100, 1) if total > 0 else 0,
        }

    return {"cursos": list(cursos.values())}
