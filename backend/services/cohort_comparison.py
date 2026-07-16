"""Estimación del efecto de intervenir, comparando contra estudiantes NO intervenidos.

POR QUÉ HACE FALTA
------------------
Comparar el "antes" y el "después" de los intervenidos NO mide el efecto de la
intervención. A los estudiantes se los interviene precisamente por estar en el extremo
peor, y los extremos tienden a moverse hacia la media por sí solos (regresión a la
media). Parte de la mejora ocurriría sin hacer nada. Sin un grupo de comparación,
"los intervenidos mejoraron" no autoriza a decir "mejoraron porque intervinimos".

CÓMO SE PUEDE HACER AQUÍ
------------------------
El ETL guarda una foto diaria por estudiante en `avac_accesses` y `task_submissions`
(columna `snapshot_date`). Eso permite reconstruir los indicadores de CUALQUIER
estudiante en una fecha pasada — no solo de los intervenidos, que son los únicos con
snapshot propio. Con eso se arma una comparación de diferencias-en-diferencias:

    efecto ≈ (después - antes | intervenidos) - (después - antes | no intervenidos)

El segundo término es lo que habría pasado igualmente. Restarlo es lo que separa el
efecto de la intervención del movimiento natural.

LÍMITES (leer antes de usar la cifra)
-------------------------------------
No es un experimento: los monitores eligen a quién contactar, y esa elección puede
correlacionar con cosas que no medimos (quién contesta el teléfono, quién ya pensaba
quedarse). El emparejamiento por carrera e indicadores de base reduce el sesgo, no lo
elimina. Es la mejor estimación disponible sin asignación aleatoria, y debe presentarse
como estimación, no como prueba.
"""
from datetime import date, timedelta
import logging

from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from ..models.student import Student
from ..models.intervention import Intervention
from ..models.avac_access import AvacAccess
from ..models.task_submission import TaskSubmission

logger = logging.getLogger(__name__)

# Tolerancias de emparejamiento: un control es comparable si arranca parecido.
CALIPER_DIAS = 3.0        # ± 3 días sin acceso
CALIPER_TAREAS = 10.0     # ± 10 puntos de % de tareas
MIN_CONTROLES = 3         # menos de 3 controles → el caso no se usa
MIN_PAREJAS = 10          # menos de 10 parejas → no se reporta efecto
VENTANA_LIMPIA = 7        # días antes de T sin intervención para ser control


def _snapshot_mas_cercano(db: Session, modelo, objetivo: date, periodo=None):
    """Fecha de snapshot más cercana <= objetivo (las fotos no son de todos los días)."""
    q = db.query(sqlfunc.max(modelo.snapshot_date)).filter(modelo.snapshot_date <= objetivo)
    if periodo:
        q = q.filter(modelo.periodo == periodo)
    return q.scalar()


def indicadores_en_fecha(db: Session, fecha: date, periodo=None) -> dict:
    """{student_id: {"dias_sin_acceso", "porcentaje_tareas"}} reconstruido en `fecha`.

    Replica el cálculo del ETL: días sin acceso = MÁXIMO entre cursos;
    % de tareas = media de entregadas × 100.
    """
    out: dict[int, dict] = {}

    snap_acc = _snapshot_mas_cercano(db, AvacAccess, fecha, periodo)
    if snap_acc:
        q = db.query(AvacAccess.student_id, sqlfunc.max(AvacAccess.dias_sin_acceso)) \
              .filter(AvacAccess.snapshot_date == snap_acc)
        if periodo:
            q = q.filter(AvacAccess.periodo == periodo)
        for sid, dias in q.group_by(AvacAccess.student_id).all():
            if sid is not None:
                out.setdefault(sid, {})["dias_sin_acceso"] = float(dias) if dias is not None else None

    snap_tar = _snapshot_mas_cercano(db, TaskSubmission, fecha, periodo)
    if snap_tar:
        q = db.query(TaskSubmission.student_id, sqlfunc.avg(sqlfunc.cast(TaskSubmission.entregada, __import__("sqlalchemy").Float))) \
              .filter(TaskSubmission.snapshot_date == snap_tar)
        if periodo:
            q = q.filter(TaskSubmission.periodo == periodo)
        for sid, media in q.group_by(TaskSubmission.student_id).all():
            if sid is not None:
                out.setdefault(sid, {})["porcentaje_tareas"] = float(media) * 100 if media is not None else None

    for v in out.values():
        v.setdefault("dias_sin_acceso", None)
        v.setdefault("porcentaje_tareas", None)
    return out


def _delta(antes, despues):
    if antes is None or despues is None:
        return None
    return despues - antes


def comparar_cohortes(db: Session, periodo=None, dias_seguimiento: int = 30) -> dict:
    """Diferencias-en-diferencias entre intervenidos y no intervenidos comparables."""
    q = db.query(Intervention).filter(Intervention.student_id.isnot(None))
    if periodo:
        q = q.filter(Intervention.periodo == periodo)
    intervenciones = [i for i in q.all() if i.created_at]

    if not intervenciones:
        return {"disponible": False, "motivo": "No hay intervenciones con fecha en el período."}

    # Fecha de la primera intervención de cada estudiante (la que inicia el tratamiento)
    primera: dict[int, date] = {}
    for i in intervenciones:
        d = i.created_at.date()
        if i.student_id not in primera or d < primera[i.student_id]:
            primera[i.student_id] = d

    todas_fechas = {sid: d for sid, d in primera.items()}
    carrera_de = {s.id: s.carrera for s in db.query(Student.id, Student.carrera).all()}

    parejas, sin_control = [], 0
    cache: dict[date, dict] = {}

    def _ind(f: date):
        if f not in cache:
            cache[f] = indicadores_en_fecha(db, f, periodo)
        return cache[f]

    for sid, T in todas_fechas.items():
        T_fin = T + timedelta(days=dias_seguimiento)
        base_all, out_all = _ind(T), _ind(T_fin)

        base_t, out_t = base_all.get(sid), out_all.get(sid)
        if not base_t or not out_t:
            continue
        d_dias_t = _delta(base_t["dias_sin_acceso"], out_t["dias_sin_acceso"])
        d_tar_t = _delta(base_t["porcentaje_tareas"], out_t["porcentaje_tareas"])
        if d_dias_t is None and d_tar_t is None:
            continue

        # Controles: misma carrera, sin ninguna intervención en la ventana, base similar
        controles = []
        for cid, cbase in base_all.items():
            if cid == sid or cid in todas_fechas:
                continue                                   # nunca intervenido
            if carrera_de.get(cid) != carrera_de.get(sid):
                continue
            cout = out_all.get(cid)
            if not cout:
                continue
            if base_t["dias_sin_acceso"] is not None and cbase["dias_sin_acceso"] is not None:
                if abs(cbase["dias_sin_acceso"] - base_t["dias_sin_acceso"]) > CALIPER_DIAS:
                    continue
            if base_t["porcentaje_tareas"] is not None and cbase["porcentaje_tareas"] is not None:
                if abs(cbase["porcentaje_tareas"] - base_t["porcentaje_tareas"]) > CALIPER_TAREAS:
                    continue
            controles.append((
                _delta(cbase["dias_sin_acceso"], cout["dias_sin_acceso"]),
                _delta(cbase["porcentaje_tareas"], cout["porcentaje_tareas"]),
            ))

        if len(controles) < MIN_CONTROLES:
            sin_control += 1
            continue

        def _media(vals):
            v = [x for x in vals if x is not None]
            return sum(v) / len(v) if v else None

        parejas.append({
            "n_controles": len(controles),
            "d_dias_t": d_dias_t, "d_tar_t": d_tar_t,
            "d_dias_c": _media([c[0] for c in controles]),
            "d_tar_c": _media([c[1] for c in controles]),
        })

    if len(parejas) < MIN_PAREJAS:
        return {
            "disponible": False,
            "motivo": (
                f"Solo {len(parejas)} intervenciones tienen un grupo de comparación válido "
                f"(hacen falta {MIN_PAREJAS}). Con menos, cualquier diferencia es ruido."
            ),
            "parejas": len(parejas),
            "descartadas_sin_control": sin_control,
        }

    def _prom(clave):
        v = [p[clave] for p in parejas if p[clave] is not None]
        return round(sum(v) / len(v), 2) if v else None

    dias_t, dias_c = _prom("d_dias_t"), _prom("d_dias_c")
    tar_t, tar_c = _prom("d_tar_t"), _prom("d_tar_c")

    def _efecto(t, c, invertir=False):
        if t is None or c is None:
            return None
        e = round(t - c, 2)
        return {"intervenidos": t, "no_intervenidos": c, "efecto_estimado": e,
                "favorable": (e < 0) if invertir else (e > 0)}

    return {
        "disponible": True,
        "dias_seguimiento": dias_seguimiento,
        "parejas_analizadas": len(parejas),
        "controles_por_caso_promedio": round(sum(p["n_controles"] for p in parejas) / len(parejas), 1),
        "descartadas_sin_control": sin_control,
        "dias_sin_acceso": _efecto(dias_t, dias_c, invertir=True),
        "porcentaje_tareas": _efecto(tar_t, tar_c),
        "como_leerlo": (
            "'efecto_estimado' es la diferencia entre lo que cambiaron los intervenidos y lo "
            "que cambiaron estudiantes comparables sin intervenir. Ese segundo número es lo que "
            "habría pasado igualmente; por eso se resta."
        ),
        "advertencia": (
            "Estimación, no prueba. Los monitores eligen a quién contactar y esa elección puede "
            "correlacionar con factores no medidos. El emparejamiento por carrera e indicadores "
            "de base reduce el sesgo, no lo elimina. Solo una asignación aleatoria permitiría "
            "hablar de causalidad."
        ),
    }
