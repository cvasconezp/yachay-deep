"""
Reporte de entregas pendientes por actividad.
Muestra qué estudiantes NO entregaron cada actividad (unidad) de cada asignatura.
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

    Retorna:
    {
        "actividades": [
            {
                "codigo_curso": "395484",
                "asignatura": "Didáctica General",
                "docente": "PÉREZ JUAN",
                "carrera": "EIB",
                "unidad": "1",
                "total_estudiantes": 30,
                "entregaron": 25,
                "no_entregaron": 5,
                "pct_entrega": 83.3,
                "pendientes": [
                    {"student_id": 1, "nombre": "GARCÍA ANA", "correo": "agarcia@...", "estado": "Sin entregar"}
                ]
            }
        ],
        "resumen": {"total_actividades": 12, "total_pendientes": 45}
    }
    """
    periodo_p, periodo_num = _get_active_periodo_variants(db)

    # Filtro de periodo
    if periodo_p:
        periodo_filter = or_(
            TaskSubmission.periodo == periodo_p,
            TaskSubmission.periodo == periodo_num,
            TaskSubmission.periodo.is_(None),
        )
    else:
        periodo_filter = TaskSubmission.periodo.is_(None)

    # Filtro de bloque activo: excluir cursos del bloque opuesto
    sc = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    codigos_excluir = set()
    if sc:
        otro_bloque = "2" if (sc.bloque_actual or "1") == "1" else "1"
        excl = db.query(CourseConfig.codigo_avac).filter(CourseConfig.bloque == otro_bloque).all()
        codigos_excluir = {r[0] for r in excl if r[0]}

    # Obtener todas las task_submissions del periodo agrupadas por (codigo_curso, unidad)
    # Primero: todos los cursos+unidades que existen
    base_q = db.query(
        TaskSubmission.codigo_curso,
        TaskSubmission.unidad,
    ).filter(periodo_filter)

    if codigos_excluir:
        base_q = base_q.filter(~TaskSubmission.codigo_curso.in_(codigos_excluir))

    if codigo_curso:
        base_q = base_q.filter(TaskSubmission.codigo_curso == codigo_curso.strip())

    actividades_unicas = base_q.distinct().all()

    # Map de CourseConfig para nombres
    all_codigos = {a[0] for a in actividades_unicas}
    cc_map = {}
    if all_codigos:
        for cc in db.query(CourseConfig).filter(CourseConfig.codigo_avac.in_(all_codigos)).all():
            cc_map[cc.codigo_avac] = cc

    # Filtros de carrera y asignatura (aplicados sobre CourseConfig)
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

        # Todos los registros de esta actividad
        subs = (
            db.query(
                TaskSubmission.student_id,
                TaskSubmission.entregada,
                TaskSubmission.estado,
            )
            .filter(
                TaskSubmission.codigo_curso == cod_curso,
                TaskSubmission.unidad == uni,
                periodo_filter,
                TaskSubmission.student_id.isnot(None),
            )
            .all()
        )

        if not subs:
            continue

        total = len(subs)
        entregaron = sum(1 for s in subs if s.entregada)
        no_entregaron_ids = [s.student_id for s in subs if not s.entregada]
        estados_por_id = {s.student_id: s.estado for s in subs if not s.entregada}

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
    Útil para vista de dashboard rápida.
    """
    periodo_p, periodo_num = _get_active_periodo_variants(db)

    if periodo_p:
        periodo_filter = or_(
            TaskSubmission.periodo == periodo_p,
            TaskSubmission.periodo == periodo_num,
            TaskSubmission.periodo.is_(None),
        )
    else:
        periodo_filter = TaskSubmission.periodo.is_(None)

    # Excluir cursos del bloque opuesto
    sc = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    codigos_excluir = set()
    if sc:
        otro_bloque = "2" if (sc.bloque_actual or "1") == "1" else "1"
        excl = db.query(CourseConfig.codigo_avac).filter(CourseConfig.bloque == otro_bloque).all()
        codigos_excluir = {r[0] for r in excl if r[0]}

    q = db.query(
        TaskSubmission.codigo_curso,
        TaskSubmission.unidad,
        func.count(TaskSubmission.id).label("total"),
        func.sum(case((TaskSubmission.entregada == True, 1), else_=0)).label("entregadas"),
    ).filter(
        periodo_filter,
        TaskSubmission.student_id.isnot(None),
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
