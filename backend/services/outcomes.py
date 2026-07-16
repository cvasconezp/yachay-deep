"""Desenlace REAL del estudiante: aprobó, reprobó, siguió o se fue.

POR QUÉ EXISTE
--------------
Toda la medición de impacto se apoyaba en `prob_desercion` y `prob_reprobacion`, que son
PREDICCIONES del modelo, no hechos. Decir "bajamos la probabilidad de deserción" no
responde a "¿cuántos desertaron?". Este módulo mira lo que de verdad pasó:

  - Reprobación: `Grade.nota_final < 70` en el período (umbral usado ya en export.py).
  - Deserción:   no hay matrícula ni notas en el período siguiente. Es un proxy, no un
                 acta de retiro, y se llama "no continuó" para no afirmar de más.

LÍMITE INSALVABLE
-----------------
Estos datos solo existen AL CIERRE del período. Antes de que se carguen las notas finales
no hay nada que medir, y ninguna ingeniería lo arregla: la información todavía no existe
en el mundo. Cuando falta, se dice, en vez de rellenar con predicciones.
"""
import logging

from sqlalchemy import func as sqlfunc, case
from sqlalchemy.orm import Session

from ..models.student import Student
from ..models.grade import Grade
from ..models.enrollment import Enrollment
from ..models.intervention import Intervention

logger = logging.getLogger(__name__)

NOTA_APROBACION = 70.0     # mismo umbral que usa el export institucional


def _sufijo_periodo(periodo: str) -> str | None:
    """'P68' -> 'P69'. Los períodos son correlativos."""
    if not periodo:
        return None
    p = periodo.strip().upper()
    if p.startswith("P") and p[1:].isdigit():
        return f"P{int(p[1:]) + 1}"
    return None


def resultados_academicos(db: Session, periodo: str, student_ids=None) -> dict:
    """{student_id: {"asignaturas", "reprobadas", "reprobo", "promedio"}} en el período."""
    q = db.query(
        Grade.student_id,
        sqlfunc.count(Grade.id),
        sqlfunc.sum(case((Grade.nota_final < NOTA_APROBACION, 1), else_=0)),
        sqlfunc.avg(Grade.nota_final),
    ).filter(Grade.periodo == periodo, Grade.nota_final.isnot(None))
    if student_ids:
        q = q.filter(Grade.student_id.in_(student_ids))

    out = {}
    for sid, total, reprobadas, promedio in q.group_by(Grade.student_id).all():
        if sid is None:
            continue
        reprobadas = int(reprobadas or 0)
        out[sid] = {
            "asignaturas": int(total or 0),
            "reprobadas": reprobadas,
            "reprobo": reprobadas > 0,
            "promedio": round(float(promedio), 2) if promedio is not None else None,
        }
    return out


def continuidad(db: Session, periodo: str, student_ids=None) -> dict:
    """{student_id: True/False} — ¿hay rastro del estudiante en el período siguiente?

    False = no continuó. Es un proxy de deserción: puede ser retiro, cambio de carrera o
    simplemente que aún no se ha matriculado. No se afirma que "desertó".
    """
    siguiente = _sufijo_periodo(periodo)
    if not siguiente:
        return {}

    # CRÍTICO: si el período siguiente todavía no tiene NINGÚN dato, no se puede medir
    # continuidad. Sin esta comprobación, "nadie aparece en P69" se leería como "todos
    # desertaron" — 100% de deserción por el simple hecho de que el semestre no empezó.
    # Es preferible no responder a responder una barbaridad.
    hay_periodo_siguiente = (
        db.query(Enrollment.id).filter(Enrollment.periodo.in_([siguiente, siguiente[1:]])).first()
        or db.query(Grade.id).filter(Grade.periodo == siguiente).first()
    )
    if not hay_periodo_siguiente:
        return {}

    sids = set()
    qe = db.query(Enrollment.student_id).filter(Enrollment.periodo.in_([siguiente, siguiente[1:]]))
    qg = db.query(Grade.student_id).filter(Grade.periodo == siguiente)
    if student_ids:
        qe = qe.filter(Enrollment.student_id.in_(student_ids))
        qg = qg.filter(Grade.student_id.in_(student_ids))
    sids.update(r[0] for r in qe.distinct().all() if r[0])
    sids.update(r[0] for r in qg.distinct().all() if r[0])

    universo = student_ids or [s.id for s in db.query(Student.id).all()]
    return {sid: (sid in sids) for sid in universo}


def _tasa(numerador, denominador):
    return round(numerador / denominador * 100, 1) if denominador else None


def desenlaces_intervenidos(db: Session, periodo: str) -> dict:
    """Qué pasó de verdad con los intervenidos, frente a los no intervenidos.

    Los no intervenidos NO son un grupo de comparación emparejado: son todos los demás,
    que de entrada están en mejor situación (por eso no se les intervino). La diferencia
    entre ambos NO es el efecto de intervenir. Sirve para describir, no para atribuir.
    """
    intervenidos = {
        r[0] for r in db.query(Intervention.student_id)
        .filter(Intervention.periodo == periodo, Intervention.student_id.isnot(None))
        .distinct().all()
    }

    todos = [s.id for s in db.query(Student.id).all()]
    no_intervenidos = [s for s in todos if s not in intervenidos]

    acad = resultados_academicos(db, periodo)
    cont = continuidad(db, periodo)
    siguiente = _sufijo_periodo(periodo)

    def _grupo(ids, nombre):
        con_notas = [i for i in ids if i in acad]
        reprobaron = sum(1 for i in con_notas if acad[i]["reprobo"])
        con_cont = [i for i in ids if i in cont]
        no_siguieron = sum(1 for i in con_cont if not cont[i])
        retirados = db.query(sqlfunc.count(Student.id)).filter(
            Student.id.in_(ids), Student.retirado == True  # noqa: E712
        ).scalar() if ids else 0
        return {
            "grupo": nombre,
            "total": len(ids),
            "con_notas_cerradas": len(con_notas),
            "reprobaron": reprobaron,
            "tasa_reprobacion": _tasa(reprobaron, len(con_notas)),
            "evaluados_continuidad": len(con_cont),
            "no_continuaron": no_siguieron,
            "tasa_no_continuidad": _tasa(no_siguieron, len(con_cont)),
            "retirados_registrados": int(retirados or 0),
        }

    g_int = _grupo(sorted(intervenidos), "intervenidos")
    g_no = _grupo(no_intervenidos, "no_intervenidos")

    hay_notas = g_int["con_notas_cerradas"] > 0
    hay_continuidad = g_int["evaluados_continuidad"] > 0 and bool(cont)

    return {
        "periodo": periodo,
        "periodo_siguiente": siguiente,
        "disponible": hay_notas or hay_continuidad,
        "motivo_no_disponible": None if (hay_notas or hay_continuidad) else (
            f"Todavía no hay notas finales del {periodo}"
            + (f" ni matrículas del {siguiente}" if siguiente else "")
            + ". El desenlace real solo existe al cierre; antes no hay nada que medir."
        ),
        "umbral_aprobacion": NOTA_APROBACION,
        "intervenidos": g_int,
        "no_intervenidos": g_no,
        "advertencia": (
            "Describe qué pasó con cada grupo; NO es el efecto de intervenir. A los "
            "intervenidos se les eligió por estar peor, así que es esperable que reprueben "
            "más aunque la intervención ayude. Para estimar el efecto hace falta comparar "
            "contra estudiantes de riesgo similar: /analytics/effectiveness/comparado."
        ),
        "definiciones": {
            "reprobo": f"Al menos una asignatura con nota final < {NOTA_APROBACION} en {periodo}.",
            "no_continuo": (
                f"Sin matrícula ni notas en {siguiente}. Es un proxy de deserción: puede ser "
                "retiro, cambio de carrera o matrícula tardía. No es un acta de retiro."
            ),
        },
    }
