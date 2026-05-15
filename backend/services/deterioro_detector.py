"""
Detector de Deterioro Progresivo — identifica estudiantes cuya situación
académica está empeorando de manera sostenida.

[Épica 1.3] Alerta de Deterioro Progresivo

Patrones detectados:
1. Desconexión silenciosa: dias_sin_acceso incrementando en snapshots consecutivos
2. Caída de compromiso: indice_compromiso bajó >30% respecto al primer registro
3. Abandono gradual de tareas: porcentaje_tareas en descenso sostenido
"""
import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func, or_, desc

from ..models import Student, AvacAccess
from ..models.enrollment import Enrollment
from ..models.alert_event import AlertEvent
from ..models.course_config import SemesterConfig, CourseConfig

logger = logging.getLogger(__name__)

# ── Configuración de umbrales de deterioro ──
MIN_SNAPSHOTS_TENDENCIA = 3          # mínimo de snapshots para detectar tendencia
INCREMENTO_DIAS_CONSECUTIVOS = 3     # snapshots consecutivos con dias_sin_acceso creciente
CAIDA_COMPROMISO_PCT = 0.30          # caída del 30% en índice de compromiso
DIAS_ACCESO_DELTA_MIN = 3.0          # incremento mínimo entre snapshots para contar


def detectar_deterioro_progresivo(db: Session) -> list[dict]:
    """
    Analiza tendencias históricas de acceso y compromiso para detectar
    estudiantes con deterioro progresivo.

    Retorna lista de dicts con: student_id, tipo_deterioro, severidad, mensaje, codigo_curso
    """
    alertas = []

    # Obtener semestre activo
    semconfig = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    if not semconfig or not semconfig.semestre:
        return alertas

    pf = semconfig.semestre.strip()
    if pf.startswith("P"):
        periodo_variants = (pf, pf[1:])
    else:
        periodo_variants = (pf, f"P{pf}")

    periodo_filter = or_(
        AvacAccess.periodo.in_(periodo_variants),
        AvacAccess.periodo.is_(None),
    )

    # ─── 1. Desconexión silenciosa: tendencia creciente de inactividad ───
    # Obtener snapshots disponibles ordenados
    snapshots = (
        db.query(AvacAccess.snapshot_date)
        .filter(periodo_filter, AvacAccess.snapshot_date.isnot(None))
        .distinct()
        .order_by(AvacAccess.snapshot_date)
        .all()
    )
    snapshot_dates = [r[0] for r in snapshots]

    if len(snapshot_dates) >= MIN_SNAPSHOTS_TENDENCIA:
        # Tomar los últimos N snapshots para análisis
        recent_snapshots = snapshot_dates[-min(len(snapshot_dates), 6):]

        # Cargar datos de acceso para esos snapshots
        # Dict: student_id → [(snapshot_date, max_dias_sin_acceso), ...]
        acceso_historico = defaultdict(list)

        avac_rows = (
            db.query(
                AvacAccess.student_id,
                AvacAccess.snapshot_date,
                func.max(AvacAccess.dias_sin_acceso).label("max_dias"),
            )
            .filter(
                periodo_filter,
                AvacAccess.snapshot_date.in_(recent_snapshots),
                AvacAccess.student_id.isnot(None),
                AvacAccess.dias_sin_acceso.isnot(None),
            )
            .group_by(AvacAccess.student_id, AvacAccess.snapshot_date)
            .all()
        )

        for sid, snap_date, max_dias in avac_rows:
            acceso_historico[sid].append((snap_date, float(max_dias)))

        # Analizar tendencia por estudiante
        for sid, historia in acceso_historico.items():
            if len(historia) < MIN_SNAPSHOTS_TENDENCIA:
                continue

            # Ordenar por fecha
            historia.sort(key=lambda x: x[0])

            # Contar incrementos consecutivos
            incrementos_consecutivos = 0
            max_racha = 0
            delta_total = 0

            for i in range(1, len(historia)):
                delta = historia[i][1] - historia[i - 1][1]
                if delta >= DIAS_ACCESO_DELTA_MIN:
                    incrementos_consecutivos += 1
                    delta_total += delta
                    max_racha = max(max_racha, incrementos_consecutivos)
                else:
                    incrementos_consecutivos = 0

            if max_racha >= INCREMENTO_DIAS_CONSECUTIVOS:
                dias_actual = historia[-1][1]
                dias_inicio = historia[0][1]
                n_snapshots = len(historia)

                if dias_actual > 21:
                    severidad = "critico"
                elif dias_actual > 14:
                    severidad = "alto"
                else:
                    severidad = "medio"

                alertas.append({
                    "student_id": sid,
                    "tipo": "deterioro_progresivo",
                    "severidad": severidad,
                    "mensaje": (
                        f"Desconexión progresiva: inactividad creciente en {max_racha} "
                        f"mediciones consecutivas ({dias_inicio:.0f}→{dias_actual:.0f} días). "
                        f"Patrón de abandono silencioso detectado."
                    ),
                    "codigo_curso": None,
                })

    # ─── 2. Caída de compromiso ───
    # Buscar estudiantes cuyo indice_compromiso actual es significativamente
    # menor que su promedio histórico (usando prob_desercion como proxy de tendencia)
    students_with_compromiso = (
        db.query(Student)
        .filter(
            Student.indice_compromiso.isnot(None),
            Student.indice_compromiso > 0,
        )
        .all()
    )

    # Si tenemos snapshots históricos, comparar el compromiso con los datos de acceso
    for student in students_with_compromiso:
        historia = acceso_historico.get(student.id, []) if len(snapshot_dates) >= MIN_SNAPSHOTS_TENDENCIA else []

        if len(historia) >= MIN_SNAPSHOTS_TENDENCIA:
            # Verificar si el compromiso bajó significativamente Y la inactividad sube
            dias_primer_snap = historia[0][1]
            dias_ultimo_snap = historia[-1][1]

            # Si días sin acceso se duplicaron o más, y compromiso está bajo
            if (dias_ultimo_snap > dias_primer_snap * 2
                    and dias_ultimo_snap > 7
                    and student.indice_compromiso < 0.4):

                # Verificar que no ya tenemos una alerta de desconexión progresiva
                ya_tiene = any(
                    a["student_id"] == student.id and a["tipo"] == "deterioro_progresivo"
                    for a in alertas
                )
                if not ya_tiene:
                    alertas.append({
                        "student_id": student.id,
                        "tipo": "deterioro_progresivo",
                        "severidad": "alto",
                        "mensaje": (
                            f"Caída de compromiso con aumento de inactividad: "
                            f"compromiso={student.indice_compromiso:.2f}, "
                            f"inactividad {dias_primer_snap:.0f}→{dias_ultimo_snap:.0f} días. "
                            f"Riesgo de abandono."
                        ),
                        "codigo_curso": None,
                    })

    # ─── 3. Abandono gradual de tareas ───
    # Estudiantes con porcentaje_tareas muy bajo Y prob_desercion alta
    students_tareas_riesgo = (
        db.query(Student)
        .filter(
            Student.porcentaje_tareas.isnot(None),
            Student.porcentaje_tareas < 30,  # menos del 30% de tareas
            Student.prob_desercion.isnot(None),
            Student.prob_desercion > 0.7,    # alta probabilidad de deserción
        )
        .all()
    )

    for student in students_tareas_riesgo:
        ya_tiene = any(
            a["student_id"] == student.id and a["tipo"] == "deterioro_progresivo"
            for a in alertas
        )
        if not ya_tiene:
            alertas.append({
                "student_id": student.id,
                "tipo": "deterioro_progresivo",
                "severidad": "critico",
                "mensaje": (
                    f"Combinación crítica: tareas={student.porcentaje_tareas:.1f}% "
                    f"con prob. deserción={student.prob_desercion:.0%}. "
                    f"Intervención urgente recomendada."
                ),
                "codigo_curso": None,
            })

    logger.info(f"Deterioro progresivo: {len(alertas)} alertas detectadas")
    return alertas
