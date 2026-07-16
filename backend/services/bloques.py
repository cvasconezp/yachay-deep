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
