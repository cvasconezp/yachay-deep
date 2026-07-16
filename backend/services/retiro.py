"""Retiro del estudiante: congelar su fotografía.

EL PROBLEMA
-----------
`días sin acceso` es una métrica mecánica: sube 1 cada día que el estudiante no entra.
Un estudiante que se retiró en junio seguía sumando días indefinidamente, así que:

  - generaba alertas nuevas cada día (ruido para los monitores, que ya sabían del retiro);
  - contaba como intervención "no exitosa" para siempre, porque nunca iba a mejorar —
    no porque la intervención fallara, sino porque el estudiante ya no está;
  - arrastraba hacia abajo los promedios de impacto.

Marcar "Retirado" en una intervención no hacía nada de esto: solo lo excluía de las
recomendaciones. El retiro es un DESENLACE, no un fracaso de la intervención, y hay que
poder distinguirlos.

QUÉ HACE
--------
Congela los indicadores en el instante del retiro y marca al estudiante. A partir de ahí
queda fuera de las alertas y del cálculo de efectividad, y se reporta aparte.
"""
from datetime import datetime, timezone
import logging

from sqlalchemy.orm import Session

from ..models.student import Student

logger = logging.getLogger(__name__)

# Valores de `Intervention.estado` que significan que el estudiante ya no está
ESTADOS_DE_RETIRO = {"retirado", "retiro", "deserto", "desertó"}


def es_estado_de_retiro(estado) -> bool:
    return (estado or "").strip().lower() in ESTADOS_DE_RETIRO


def marcar_retirado(db: Session, student: Student, motivo=None, cuando=None) -> bool:
    """Congela la foto del estudiante. Idempotente: no repisa un retiro anterior."""
    if student is None or student.retirado:
        return False

    student.retirado = True
    student.fecha_retiro = cuando or datetime.now(timezone.utc)
    student.motivo_retiro = motivo
    # Foto del último estado conocido: es el que vale para el análisis posterior
    student.retiro_snapshot_dias_sin_acceso = student.dias_sin_acceso
    student.retiro_snapshot_compromiso = student.indice_compromiso
    student.retiro_snapshot_porcentaje_tareas = student.porcentaje_tareas
    student.retiro_snapshot_nivel_riesgo = student.nivel_riesgo
    logger.info("Estudiante %s marcado como retirado; indicadores congelados", student.id)
    return True


def reactivar(db: Session, student: Student) -> bool:
    """Deshace el retiro (se marcó por error o el estudiante volvió)."""
    if student is None or not student.retirado:
        return False
    student.retirado = False
    student.fecha_retiro = None
    student.motivo_retiro = None
    return True


def filtrar_activos(query, modelo=Student):
    """Excluye retirados. Para alertas y cualquier cálculo de seguimiento."""
    return query.filter((modelo.retirado == False) | (modelo.retirado.is_(None)))  # noqa: E712
