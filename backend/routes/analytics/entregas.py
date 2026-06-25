"""
Reporte de entregas pendientes por actividad.
Muestra qué estudiantes NO entregaron cada actividad (unidad) de cada asignatura.

[BUG-FIX] Usa solo el snapshot más reciente para evitar duplicados históricos
que generaban falsos positivos (estudiantes que entregaron aparecían como pendientes
porque tenían un registro viejo con entregada=False).
"""
import json
import logging
from datetime import date
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
from ...models.enrollment import Enrollment
from ...models.intervention import Intervention

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


def _get_unidad_actual(db: Session) -> Optional[str]:
    """Calcula qué unidad debería estar entregada según el calendario académico.

    Calendario P68:
      Entrega actividades 1: 2026-04-19
      Entrega actividades 2: 2026-05-03
      Entrega actividades 3: 2026-05-17
      Entrega actividades 4: 2026-06-21 (bloque 2)
      Entrega actividades 5: 2026-07-05
      Entrega actividades 6: 2026-07-19

    Retorna la unidad más reciente cuya fecha ya pasó.
    """
    sc = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    if not sc or not sc.calendario_academico:
        return None

    try:
        cal = json.loads(sc.calendario_academico) if isinstance(sc.calendario_academico, str) else sc.calendario_academico
    except (json.JSONDecodeError, TypeError):
        return None

    today = date.today()
    # Buscar entregas cuya fecha ya pasó, extraer el número de actividad
    entregas_pasadas = []
    for item in cal:
        if item.get("tipo") != "entrega":
            continue
        try:
            fecha = date.fromisoformat(item["fecha"])
        except (KeyError, ValueError):
            continue
        if fecha <= today:
            # Extraer número de "Entrega actividades N"
            label = item.get("label", "")
            for word in label.split():
                if word.isdigit():
                    entregas_pasadas.append(word)
                    break

    return entregas_pasadas[-1] if entregas_pasadas else None


def _get_bloque_actual(db: Session) -> str:
    """Retorna el bloque actual del semestre activo."""
    sc = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    return (sc.bloque_actual or "1") if sc else "1"


def _build_periodo_filter(periodo_p, periodo_num):
    """Construye filtro SQLAlchemy para periodo activo."""
    if periodo_p:
        return or_(
            TaskSubmission.periodo == periodo_p,
            TaskSubmission.periodo == periodo_num,
            TaskSubmission.periodo.is_(None),
        )
    return TaskSubmission.periodo.is_(None)


def _get_codigos_incluir_bloque(db: Session, bloque: str) -> set:
    """Devuelve códigos a INCLUIR cuando se filtra por un bloque específico.

    Enfoque WHITELIST: solo incluir cursos confirmados en el bloque seleccionado.
    Usa Enrollment.bloque (dato institucional, confiable) como fuente primaria,
    complementado con CourseConfig.bloque para cobertura.

    Cursos con bloque=NULL en ambas tablas quedan EXCLUIDOS (no se asume nada).
    """
    if bloque not in ("1", "2"):
        return set()

    bloque_int = int(bloque)

    # Fuente principal: Enrollment.bloque (reporte institucional)
    enr_codes = db.query(Enrollment.codigo_grupo).filter(
        Enrollment.bloque == bloque_int
    ).distinct().all()
    codigos = {r[0] for r in enr_codes if r[0]}

    # Fuente secundaria: CourseConfig.bloque
    cc_codes = db.query(CourseConfig.codigo_avac).filter(
        CourseConfig.bloque == bloque
    ).all()
    codigos.update(r[0] for r in cc_codes if r[0])

    return codigos


def _get_codigos_incluir_bloque_default(db: Session) -> set:
    """Devuelve códigos del bloque actual (para cuando no se especifica filtro)."""
    sc = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    if not sc:
        return set()
    bloque_actual = sc.bloque_actual or "1"
    return _get_codigos_incluir_bloque(db, bloque_actual)


def _get_latest_snapshot_date(db: Session, periodo_filter, codigos_incluir: set):
    """Encuentra la fecha del snapshot más reciente (global)."""
    q = db.query(func.max(TaskSubmission.snapshot_date)).filter(periodo_filter)
    if codigos_incluir:
        q = q.filter(TaskSubmission.codigo_curso.in_(codigos_incluir))
    return q.scalar()


def _get_latest_snapshot_per_course(db: Session, periodo_filter, codigos_incluir: set) -> dict:
    """Retorna {codigo_curso: max_snapshot_date} para cada curso.

    Corrige el bug donde se usaba una fecha global: si un curso se scrapeó
    el lunes y otro el miércoles, la consulta global (miércoles) haría
    desaparecer los datos del lunes. Ahora cada curso usa su propio snapshot.
    """
    q = db.query(
        TaskSubmission.codigo_curso,
        func.max(TaskSubmission.snapshot_date).label("latest"),
    ).filter(periodo_filter, TaskSubmission.student_id.isnot(None))
    if codigos_incluir:
        q = q.filter(TaskSubmission.codigo_curso.in_(codigos_incluir))
    rows = q.group_by(TaskSubmission.codigo_curso).all()
    return {r[0]: r[1] for r in rows if r[0] and r[1]}


@router.get("/entregas-pendientes")
def entregas_pendientes(
    carrera: str = Query("", description="Filtrar por carrera"),
    asignatura: str = Query("", description="Filtrar por asignatura (nombre parcial)"),
    unidad: str = Query("", description="Filtrar por unidad: 1, 2, 3, 4"),
    bloque: str = Query("", description="Filtrar por bloque: 1, 2, o vacío para todos"),
    codigo_curso: str = Query("", description="Filtrar por código AVAC del curso"),
    grupos_excluir: str = Query("", description="Grupos a excluir (comma-sep): 6 excluye Wasakentsa"),
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

    # Filtro de bloque: WHITELIST — solo incluir cursos confirmados del bloque
    if bloque:
        codigos_incluir = _get_codigos_incluir_bloque(db, bloque.strip())
    else:
        codigos_incluir = _get_codigos_incluir_bloque_default(db)

    # Filtro de grupo: remover cursos de grupos excluidos (ej: grupo 6 Wasakentsa)
    if grupos_excluir:
        grupos_list = [g.strip() for g in grupos_excluir.split(",") if g.strip()]
        if grupos_list:
            excl_by_grupo = db.query(CourseConfig.codigo_avac).filter(
                CourseConfig.grupo.in_(grupos_list)
            ).all()
            codigos_incluir = codigos_incluir - {r[0] for r in excl_by_grupo if r[0]}

    # Snapshot más reciente POR CURSO (no global)
    snapshot_per_course = _get_latest_snapshot_per_course(db, periodo_filter, codigos_incluir)
    if not snapshot_per_course:
        return {"actividades": [], "resumen": {"total_actividades": 0, "total_pendientes": 0}}

    # Para la consulta de cursos+unidades usamos el rango de fechas de snapshots
    all_snapshot_dates = set(snapshot_per_course.values())

    # Filtro base: periodo + solo cursos del bloque + snapshot dates relevantes
    base_filters = [
        periodo_filter,
        TaskSubmission.student_id.isnot(None),
        TaskSubmission.snapshot_date.in_(all_snapshot_dates),
    ]
    if codigos_incluir:
        base_filters.append(TaskSubmission.codigo_curso.in_(codigos_incluir))

    # Todos los cursos+unidades de los snapshots más recientes
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

        # Snapshot más reciente PARA ESTE CURSO (no global)
        course_snapshot = snapshot_per_course.get(cod_curso)
        if not course_snapshot:
            continue

        subs = (
            db.query(
                TaskSubmission.student_id,
                TaskSubmission.entregada,
                TaskSubmission.estado,
            )
            .filter(
                TaskSubmission.codigo_curso == cod_curso,
                TaskSubmission.unidad == uni,
                TaskSubmission.snapshot_date == course_snapshot,
                periodo_filter,
                TaskSubmission.student_id.isnot(None),
            )
            .all()
        )

        if not subs:
            continue

        # Deduplicar por student_id: priorizar entregada=True
        # (puede haber duplicados si un curso tiene registros de distintos snapshots)
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

    # Marcar estudiantes que ya tienen intervención reciente (motivo "Tareas no entregadas")
    all_pending_ids = set()
    for act in resultado:
        for p in act["pendientes"]:
            all_pending_ids.add(p["student_id"])

    intervenidos = set()
    if all_pending_ids:
        from datetime import timedelta, datetime, timezone
        umbral = datetime.now(timezone.utc) - timedelta(days=30)
        rows = (
            db.query(Intervention.student_id)
            .filter(
                Intervention.student_id.in_(all_pending_ids),
                Intervention.created_at >= umbral,
            )
            .distinct()
            .all()
        )
        intervenidos = {r[0] for r in rows}

    for act in resultado:
        for p in act["pendientes"]:
            p["intervenido"] = p["student_id"] in intervenidos

    # Grupos disponibles para la carrera seleccionada (para filtro en frontend)
    grupos_disponibles = []
    if carrera:
        carrera_lower = carrera.strip().lower()
        grupos_q = (
            db.query(CourseConfig.grupo)
            .filter(
                CourseConfig.carrera.ilike(f"%{carrera_lower}%"),
                CourseConfig.grupo.isnot(None),
            )
            .distinct()
            .all()
        )
        grupos_disponibles = sorted({r[0] for r in grupos_q if r[0]}, key=lambda x: int(x) if x.isdigit() else x)

    return {
        "actividades": resultado,
        "resumen": {
            "total_actividades": len(resultado),
            "total_pendientes": total_pendientes,
        },
        "defaults": {
            "bloque_actual": _get_bloque_actual(db),
            "unidad_actual": _get_unidad_actual(db),
        },
        "grupos_disponibles": grupos_disponibles,
    }


@router.get("/entregas-resumen")
def entregas_resumen(
    carrera: str = Query("", description="Filtrar por carrera"),
    bloque: str = Query("", description="Filtrar por bloque: 1, 2, o vacío para todos"),
    grupos_excluir: str = Query("", description="Grupos a excluir (comma-sep): 6 excluye Wasakentsa"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Resumen compacto de entregas: por cada curso, % de entrega por unidad.
    Usa SOLO el snapshot más reciente.
    """
    periodo_p, periodo_num = _get_active_periodo_variants(db)
    periodo_filter = _build_periodo_filter(periodo_p, periodo_num)

    # WHITELIST: solo cursos confirmados del bloque
    if bloque:
        codigos_incluir = _get_codigos_incluir_bloque(db, bloque.strip())
    else:
        codigos_incluir = _get_codigos_incluir_bloque_default(db)

    # Filtro de grupo
    if grupos_excluir:
        grupos_list = [g.strip() for g in grupos_excluir.split(",") if g.strip()]
        if grupos_list:
            excl_by_grupo = db.query(CourseConfig.codigo_avac).filter(
                CourseConfig.grupo.in_(grupos_list)
            ).all()
            codigos_incluir = codigos_incluir - {r[0] for r in excl_by_grupo if r[0]}

    # Snapshot más reciente POR CURSO
    snapshot_per_course = _get_latest_snapshot_per_course(db, periodo_filter, codigos_incluir)
    if not snapshot_per_course:
        return {"cursos": []}

    # Construir filtro OR: (curso=A AND snapshot=dateA) OR (curso=B AND snapshot=dateB) ...
    # Para eficiencia, agrupar cursos por snapshot_date
    from collections import defaultdict
    courses_by_date = defaultdict(set)
    for cod, dt in snapshot_per_course.items():
        courses_by_date[dt].add(cod)

    date_filters = []
    for dt, codes in courses_by_date.items():
        date_filters.append(and_(
            TaskSubmission.snapshot_date == dt,
            TaskSubmission.codigo_curso.in_(codes),
        ))

    q = db.query(
        TaskSubmission.codigo_curso,
        TaskSubmission.unidad,
        func.count(TaskSubmission.id).label("total"),
        func.sum(case((TaskSubmission.entregada == True, 1), else_=0)).label("entregadas"),
    ).filter(
        periodo_filter,
        TaskSubmission.student_id.isnot(None),
        or_(*date_filters),
    )

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
