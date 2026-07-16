"""Ventana temporal del bloque académico. Fuente única.

EL PROBLEMA QUE RESUELVE
------------------------
Un estudiante salía alertado por "56 días sin ingresar a la materia Y". Pero la materia Y
era de Bloque 1 y ese bloque cerró hace un mes: no entra porque la materia YA NO EXISTE.
La alerta es correcta según el dato y absurda según la realidad.

`días sin acceso` es una métrica mecánica que crece sola. Sin una ventana temporal, todo
curso terminado se convierte en un generador infinito de alertas falsas: cuanto más viejo,
más "grave" parece.

Además, esta lógica estaba duplicada y divergente: el dashboard aplicaba un tope por fecha
de inicio de bloque y excluía cursos del bloque contrario; el ETL —que es quien calcula el
nivel de riesgo— no hacía ninguna de las dos cosas. Por eso Dashboard y Ficha mostraban
números distintos del mismo estudiante.
"""
from datetime import datetime, timezone
import logging

from sqlalchemy.orm import Session

from ..models.course_config import CourseConfig, SemesterConfig

logger = logging.getLogger(__name__)


def _aware(dt):
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def semestre_activo(db: Session):
    return db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()  # noqa: E712


def ventana_bloque(semconfig, ahora=None) -> tuple:
    """(inicio, fin_efectivo) del bloque actual. fin_efectivo = min(fin, hoy)."""
    if not semconfig:
        return None, None
    ahora = ahora or datetime.now(timezone.utc)
    bloque = str(semconfig.bloque_actual or "1")

    if bloque == "2":
        inicio, fin = _aware(semconfig.bloque2_inicio), _aware(semconfig.bloque2_fin)
    else:
        inicio, fin = _aware(semconfig.bloque1_inicio), _aware(semconfig.bloque1_fin)

    # Si el bloque ya cerró, el reloj se detiene en su fin: los días no siguen corriendo
    fin_efectivo = min(fin, ahora) if fin else ahora
    return inicio, fin_efectivo


def dias_maximos_del_bloque(semconfig, ahora=None) -> int | None:
    """Días transcurridos del bloque actual. Nadie puede llevar más días sin acceso
    que los que el bloque lleva existiendo."""
    inicio, fin_efectivo = ventana_bloque(semconfig, ahora)
    if not inicio:
        return None
    return max((fin_efectivo - inicio).days, 0)


def cursos_del_bloque_cerrado(db: Session, semconfig) -> set[str]:
    """Códigos AVAC de cursos que NO pertenecen al bloque en curso.

    Se excluyen sus alertas: si el bloque terminó, el estudiante no entra porque la
    materia acabó, no porque esté abandonando.
    """
    if not semconfig:
        return set()
    bloque = str(semconfig.bloque_actual or "1")
    otro = "2" if bloque == "1" else "1"

    codigos = set()
    for (cod,) in db.query(CourseConfig.codigo_avac).filter(CourseConfig.bloque == otro).all():
        if cod:
            codigos.add(str(cod))
    return codigos


def bloque_esta_cerrado(semconfig, ahora=None) -> bool:
    if not semconfig:
        return False
    ahora = ahora or datetime.now(timezone.utc)
    bloque = str(semconfig.bloque_actual or "1")
    fin = _aware(semconfig.bloque2_fin if bloque == "2" else semconfig.bloque1_fin)
    return bool(fin and ahora > fin)


def acotar_dias(dias, semconfig, ahora=None):
    """Recorta los días sin acceso a la vida del bloque.

    Sin esto, un curso de un bloque cerrado acumula días indefinidamente y su "gravedad"
    crece sola con el calendario, no con el comportamiento del estudiante.
    """
    if dias is None:
        return None
    tope = dias_maximos_del_bloque(semconfig, ahora)
    if tope is None:
        return dias
    return min(int(dias), tope)


# ─────────────────────────────────────────────────────────────────────────────
# Unidades vencidas
# ─────────────────────────────────────────────────────────────────────────────
def _calendario(semconfig) -> list:
    import json
    if not semconfig or not semconfig.calendario_academico:
        return []
    try:
        return json.loads(semconfig.calendario_academico)
    except (json.JSONDecodeError, TypeError):
        return []


def unidades_vencidas(semconfig, ahora=None) -> set | None:
    """Unidades cuya fecha de entrega ya pasó. None = sin calendario → no filtrar.

    EL PROBLEMA: `porcentaje_tareas` = entregadas / TODAS las tareas del curso, incluidas
    las que aún no vencen. A mitad de bloque, un estudiante que entregó puntualmente todo
    lo exigible aparece con un 33% si el curso tiene 12 tareas y solo han vencido 4.
    Eso no mide incumplimiento: mide el calendario. Y hunde el índice de todos por igual
    (el promedio institucional era 29%).

    Se usan las fechas de entrega del calendario académico ya configurado: la N-ésima
    fecha de entrega corresponde a la unidad N.
    """
    from datetime import datetime as _dt, timezone as _tz

    ahora = ahora or _dt.now(_tz.utc)
    entregas = []
    for e in _calendario(semconfig):
        if e.get("tipo") not in ("entrega", "paso_notas"):
            continue
        try:
            f = _dt.fromisoformat(str(e.get("fecha")).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        entregas.append(_aware(f))

    if not entregas:
        return None          # sin calendario configurado: no se filtra nada

    entregas.sort()
    return {str(i) for i, f in enumerate(entregas, start=1) if f <= ahora}


def filtrar_tareas_vencidas(df_tareas, semconfig, ahora=None):
    """Deja solo las tareas de unidades cuya entrega ya venció.

    Conservador: sin calendario, o si no quedaría ninguna unidad, devuelve el df intacto.
    Es preferible un porcentaje pesimista a dejar a todos sin datos de tareas.
    """
    if df_tareas is None or len(df_tareas) == 0 or "unidad" not in getattr(df_tareas, "columns", []):
        return df_tareas
    vencidas = unidades_vencidas(semconfig, ahora)
    if vencidas is None:
        return df_tareas
    if not vencidas:
        logger.info("Ninguna unidad ha vencido todavía: no se filtran tareas (se evita dejar todo a cero)")
        return df_tareas

    filtrado = df_tareas[df_tareas["unidad"].astype(str).isin(vencidas)]
    if len(filtrado) == 0:
        return df_tareas
    descartadas = len(df_tareas) - len(filtrado)
    if descartadas:
        logger.info(
            "📅 %d registros de tareas descartados: unidades que aún no vencen "
            "(antes contaban como no entregadas y hundían el %% de todos)", descartadas,
        )
    return filtrado
