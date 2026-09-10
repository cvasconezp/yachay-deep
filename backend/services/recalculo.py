"""Recalcular indicadores desde la BD, sin volver a scrapear.

POR QUÉ
-------
El scraping tarda ~2 horas y hoy además está roto por el login. Pero los datos crudos
(avac_accesses, task_submissions, enrollments) ya están en la base: lo único que hacía
falta era volver a aplicarles las reglas correctas.

Esto recorre los mismos pasos que el ETL pero leyendo de la BD en vez de los CSV:
  1. descarta aulas donde el estudiante ya no está matriculado (aulas fantasma),
  2. descarta cursos de un bloque que ya cerró,
  3. acota los días sin acceso a la vida del bloque,
  4. cuenta solo las tareas cuya entrega ya venció,
  5. recalcula días (máximo y mínimo), % de tareas, índice y nivel de riesgo.

LÍMITE: no trae datos nuevos de AVAC. Recalcula sobre la última foto disponible. Si el
último scraping fue hace una semana, los accesos son de hace una semana — lo que cambia es
que las reglas aplicadas ya son las correctas.
"""
from datetime import datetime, timezone
import logging

from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from ..models.student import Student
from ..models.avac_access import AvacAccess
from ..models.task_submission import TaskSubmission
from ..models.enrollment import Enrollment
from ..etl.transformers import calcular_indice_compromiso
from .bloques import (
    semestre_activo, cursos_del_bloque_cerrado, dias_maximos_del_bloque, unidades_vencidas,
)

logger = logging.getLogger(__name__)


def _ultimo_snapshot(db: Session, modelo, periodo=None):
    q = db.query(sqlfunc.max(modelo.snapshot_date))
    if periodo:
        q = q.filter(modelo.periodo.in_([periodo, periodo.lstrip("P")]))
    return q.scalar()


def recalcular_indicadores(db: Session, periodo: str = None) -> dict:
    """Recomputa los indicadores de riesgo de todos los estudiantes desde la BD."""
    semconfig = semestre_activo(db)
    periodo = periodo or (semconfig.semestre if semconfig else None)
    if not periodo:
        return {"ok": False, "motivo": "No hay semestre activo configurado."}

    variantes = [periodo, periodo.lstrip("P")]
    ahora = datetime.now(timezone.utc)

    cerrados = cursos_del_bloque_cerrado(db, semconfig)
    tope_dias = dias_maximos_del_bloque(db and semconfig, ahora)
    vencidas = unidades_vencidas(semconfig, ahora)
    try:
        bloque_num = int(semconfig.bloque_actual) if semconfig and semconfig.bloque_actual else 1
    except (TypeError, ValueError):
        bloque_num = 1

    # ── Matrículas por estudiante (para descartar aulas fantasma) ──
    matriculas = {}
    for sid, cod in db.query(Enrollment.student_id, Enrollment.codigo_grupo).filter(
        Enrollment.codigo_grupo.isnot(None)
    ).distinct().all():
        if sid:
            matriculas.setdefault(sid, set()).add(str(cod).strip())

    # ── Accesos AVAC del último snapshot ──
    snap_avac = _ultimo_snapshot(db, AvacAccess, periodo)
    accesos = {}
    q = db.query(AvacAccess.student_id, AvacAccess.codigo_curso, AvacAccess.dias_sin_acceso).filter(
        AvacAccess.periodo.in_(variantes), AvacAccess.dias_sin_acceso.isnot(None),
    )
    if snap_avac:
        q = q.filter(AvacAccess.snapshot_date == snap_avac)

    descartados_fantasma = descartados_bloque = 0
    for sid, cod, dias in q.all():
        if sid is None:
            continue
        cod = str(cod).strip()
        # Aula fantasma: el estudiante ya no está matriculado ahí
        if sid in matriculas and cod not in matriculas[sid]:
            descartados_fantasma += 1
            continue
        # Curso de un bloque que ya cerró: no entra porque la materia terminó
        if cod in cerrados:
            descartados_bloque += 1
            continue
        d = float(dias)
        if tope_dias is not None:
            d = min(d, tope_dias)
        accesos.setdefault(sid, []).append(d)

    # ── Tareas del último snapshot, solo unidades vencidas ──
    snap_tar = _ultimo_snapshot(db, TaskSubmission, periodo)
    tq = db.query(
        TaskSubmission.student_id, TaskSubmission.unidad, TaskSubmission.entregada,
        TaskSubmission.codigo_curso,
    ).filter(TaskSubmission.periodo.in_(variantes))
    if snap_tar:
        tq = tq.filter(TaskSubmission.snapshot_date == snap_tar)

    tareas = {}
    descartadas_futuras = descartadas_tareas_bloque = 0
    filas_tareas = tq.all()
    # Si aún no venció ninguna unidad, no se filtra: dejar a todos a cero sería peor
    aplicar_vencidas = bool(vencidas)
    for sid, unidad, entregada, cod_tarea in filas_tareas:
        if sid is None:
            continue
        # Las tareas del bloque cerrado tampoco cuentan: se estaban sumando como "no
        # entregadas" y hundían el % (bajó de 31% a 20% en el primer recálculo).
        if str(cod_tarea).strip() in cerrados:
            descartadas_tareas_bloque += 1
            continue
        if aplicar_vencidas and str(unidad) not in vencidas:
            descartadas_futuras += 1
            continue
        tareas.setdefault(sid, []).append(bool(entregada))

    # ── Promedio del parcial de AVAC (total_curso) por estudiante [H1] ──
    # Respaldo académico cuando aún no hay nota final. Un valor por curso
    # (deduplicado), excluyendo cursos de bloque cerrado, promediado por estudiante.
    avac_tc: dict = {}
    aq = db.query(
        TaskSubmission.student_id, TaskSubmission.codigo_curso, TaskSubmission.total_curso,
    ).filter(TaskSubmission.periodo.in_(variantes), TaskSubmission.total_curso.isnot(None))
    if snap_tar:
        aq = aq.filter(TaskSubmission.snapshot_date == snap_tar)
    for sid, cod, tc in aq.all():
        if sid is None or cod is None:
            continue
        cod = str(cod).strip()
        if cod in cerrados:
            continue
        avac_tc.setdefault(sid, {})[cod] = tc
    avac_prom = {sid: (sum(v.values()) / len(v)) for sid, v in avac_tc.items() if v}

    # ── Recalcular por estudiante ──
    actualizados = 0
    cambios_nivel = 0
    for student in db.query(Student).filter(
        (Student.retirado == False) | (Student.retirado.is_(None))  # noqa: E712
    ).all():
        dias_lista = accesos.get(student.id)
        t_lista = tareas.get(student.id)
        if not dias_lista and not t_lista:
            continue

        nivel_previo = student.nivel_riesgo

        if dias_lista:
            student.dias_sin_acceso = int(max(dias_lista))          # asignatura más descuidada
            student.dias_desde_ultimo_acceso = int(min(dias_lista))  # último acceso real
        if t_lista:
            student.porcentaje_tareas = round(sum(t_lista) / len(t_lista) * 100, 2)

        ind = calcular_indice_compromiso(
            dias_sin_acceso=student.dias_sin_acceso,
            tareas_entregadas=int(sum(t_lista)) if t_lista else 0,
            tareas_totales=len(t_lista) if t_lista else 0,
            notas=[],
            bloque_actual=bloque_num,
            promedio_calificaciones=student.promedio_calificaciones,
            promedio_total_curso=avac_prom.get(student.id),   # [H1] respaldo AVAC
            estado_matricula=student.estado_matricula,
            dias_desde_ultimo_acceso=student.dias_desde_ultimo_acceso,
        )
        student.indice_compromiso = ind.get("indice_compromiso")
        student.nivel_riesgo = ind.get("nivel_riesgo")
        if nivel_previo != student.nivel_riesgo:
            cambios_nivel += 1
        actualizados += 1

    db.commit()

    # Cuántos tienen realmente datos de tareas. Sin este número no se puede saber si un
    # 12% de promedio significa "no entregan" o "no tenemos el dato".
    #
    # Importa porque el componente de tareas vale 0.30 y su valor por defecto cuando falta
    # es 0.05: con eso, el TECHO del índice es 0.30+0.05+0.23+0.15 = 0.729 — por debajo del
    # 0.80 de "Sin riesgo". Un estudiante perfecto en todo lo demás queda excluido del nivel
    # solo por no tener datos de tareas.
    con_tareas = len(tareas)
    total_alumnos = actualizados or 1

    resumen = {
        "ok": True,
        "periodo": periodo,
        "bloque": bloque_num,
        "estudiantes_actualizados": actualizados,
        "tareas": {
            "estudiantes_con_datos": con_tareas,
            "estudiantes_sin_datos": max(actualizados - con_tareas, 0),
            "pct_con_datos": round(con_tareas / total_alumnos * 100, 1),
            "tareas_contadas": sum(len(v) for v in tareas.values()),
            "por_que_importa": (
                "El componente de tareas vale 0.30 del índice y sin datos se le asigna 0.05. "
                "Con ese valor el techo del índice es 0.729, así que quien no tenga datos de "
                "tareas NUNCA puede llegar a 'Sin riesgo' (>= 0.80), por bien que vaya en todo "
                "lo demás."
            ) if con_tareas < actualizados * 0.5 else None,
        },
        "cambiaron_de_nivel": cambios_nivel,
        "registros_descartados": {
            "aulas_fantasma": descartados_fantasma,
            "cursos_de_bloque_cerrado": descartados_bloque,
            "tareas_aun_no_vencidas": descartadas_futuras,
            "tareas_de_bloque_cerrado": descartadas_tareas_bloque,
        },
        "tope_dias_bloque": tope_dias,
        "unidades_vencidas": sorted(vencidas) if vencidas else None,
        "snapshot_avac": str(snap_avac) if snap_avac else None,
        "nota": (
            "Recalculado sobre la última foto de AVAC disponible; no trae datos nuevos. "
            "Lo que cambia es que ya se aplican las reglas correctas."
        ),
    }
    logger.info("♻️ Recálculo de indicadores: %s", resumen)
    return resumen
