"""
Contrafactuales Conductuales para Yachay Deep.

A diferencia de counterfactual.py (basado en modelo ML / calificaciones),
este motor genera escenarios basados en el COMPORTAMIENTO del estudiante:
acceso al AVAC, entrega de tareas, matrícula.

Simula: "Si haces X, tu compromiso sube de Y% a Z%"
usando la misma fórmula del índice de compromiso (transformers.py v2).

Se activa para TODOS los estudiantes con compromiso < 0.65 o días sin acceso > 7,
independientemente de si el modelo ML tiene datos o no.
"""
import math
import logging
from typing import Optional
from sqlalchemy.orm import Session

from ..models.student import Student

logger = logging.getLogger(__name__)


def _simular_compromiso(dias_sin_acceso, pct_tareas, promedio_cal, estado_matricula):
    """Replica la fórmula v2 de calcular_indice_compromiso para simulación."""
    # Acceso AVAC (30%)
    if dias_sin_acceso is None:
        p_acceso = 0.03
    else:
        p_acceso = 0.30 * math.exp(-max(dias_sin_acceso, 0) / 10)

    # Tareas (30%)
    if pct_tareas is None:
        p_tareas = 0.05
    else:
        p_tareas = (pct_tareas / 100) * 0.30

    # Rendimiento (25%)
    if promedio_cal is not None and promedio_cal > 0:
        p_rendimiento = 0.25 / (1 + math.exp(-0.08 * (promedio_cal - 70)))
    else:
        p_rendimiento = 0.04

    # Admin (15%)
    if estado_matricula and "matriculad" in str(estado_matricula).lower():
        p_admin = 0.15
    else:
        p_admin = 0.03

    return round(p_acceso + p_tareas + p_rendimiento + p_admin, 3)


def generate_behavioral_counterfactual(
    db: Session,
    student_id: int,
) -> Optional[dict]:
    """
    Genera escenarios contrafactuales conductuales.

    Para cada variable conductual, simula qué pasaría si el estudiante mejora
    y calcula el nuevo índice de compromiso + nivel de riesgo.
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return None

    dias = student.dias_sin_acceso
    tareas = student.porcentaje_tareas
    promedio = student.promedio_calificaciones
    matricula = student.estado_matricula
    compromiso_actual = student.indice_compromiso

    # Solo generar si hay espacio de mejora
    if compromiso_actual is not None and compromiso_actual >= 0.65 and (dias is None or dias <= 3):
        return None  # ya está bien, no necesita contrafactual

    # Compromiso actual simulado (verificar consistencia)
    compromiso_simulado_base = _simular_compromiso(dias, tareas, promedio, matricula)

    escenarios = []

    # ── Escenario 1: Conectarse al AVAC esta semana ──
    if dias is not None and dias > 3:
        nuevo_compromiso = _simular_compromiso(1, tareas, promedio, matricula)
        delta = nuevo_compromiso - compromiso_simulado_base
        if delta > 0.01:
            nuevo_nivel = "Bajo" if nuevo_compromiso >= 0.65 else "Medio" if nuevo_compromiso >= 0.35 else "Alto"
            escenarios.append({
                "accion": f"Acceder al aula virtual AVAC esta semana (actualmente lleva {int(dias)} días sin ingresar)",
                "variable": "dias_sin_acceso",
                "valor_actual": int(dias),
                "valor_simulado": 1,
                "compromiso_actual": round(compromiso_simulado_base * 100),
                "compromiso_nuevo": round(nuevo_compromiso * 100),
                "ganancia": round(delta * 100),
                "nivel_riesgo_nuevo": nuevo_nivel,
                "factibilidad": "alta",
                "plazo": "esta semana",
            })

    # ── Escenario 2: Entregar tareas pendientes ──
    if tareas is not None and tareas < 80:
        # Simular subir a 80% de entrega
        target_tareas = min(tareas + 25, 90)  # incremento realista de 25pp
        nuevo_compromiso = _simular_compromiso(dias, target_tareas, promedio, matricula)
        delta = nuevo_compromiso - compromiso_simulado_base
        if delta > 0.01:
            tareas_pendientes = round((target_tareas - tareas) / 100 * 4)  # aprox 4 unidades por materia
            nuevo_nivel = "Bajo" if nuevo_compromiso >= 0.65 else "Medio" if nuevo_compromiso >= 0.35 else "Alto"
            escenarios.append({
                "accion": f"Entregar las tareas pendientes para subir de {round(tareas)}% a {round(target_tareas)}% de entrega",
                "variable": "porcentaje_tareas",
                "valor_actual": round(tareas),
                "valor_simulado": round(target_tareas),
                "compromiso_actual": round(compromiso_simulado_base * 100),
                "compromiso_nuevo": round(nuevo_compromiso * 100),
                "ganancia": round(delta * 100),
                "nivel_riesgo_nuevo": nuevo_nivel,
                "factibilidad": "alta",
                "plazo": "1-2 semanas",
            })

    # ── Escenario 3: Conectarse + entregar tareas (combinado) ──
    if dias is not None and dias > 7 and tareas is not None and tareas < 80:
        target_tareas = min(tareas + 25, 90)
        nuevo_compromiso = _simular_compromiso(1, target_tareas, promedio, matricula)
        delta = nuevo_compromiso - compromiso_simulado_base
        if delta > 0.02:
            nuevo_nivel = "Bajo" if nuevo_compromiso >= 0.65 else "Medio" if nuevo_compromiso >= 0.35 else "Alto"
            escenarios.append({
                "accion": f"Conectarse al AVAC y entregar tareas pendientes (acción combinada)",
                "variable": "combinado",
                "valor_actual": f"{int(dias)}d sin AVAC, {round(tareas)}% tareas",
                "valor_simulado": f"1d sin AVAC, {round(target_tareas)}% tareas",
                "compromiso_actual": round(compromiso_simulado_base * 100),
                "compromiso_nuevo": round(nuevo_compromiso * 100),
                "ganancia": round(delta * 100),
                "nivel_riesgo_nuevo": nuevo_nivel,
                "factibilidad": "alta",
                "plazo": "1-2 semanas",
            })

    # ── Escenario 4: Regularizar matrícula ──
    if not matricula or "matriculad" not in str(matricula).lower():
        nuevo_compromiso = _simular_compromiso(dias, tareas, promedio, "Matriculado")
        delta = nuevo_compromiso - compromiso_simulado_base
        if delta > 0.01:
            nuevo_nivel = "Bajo" if nuevo_compromiso >= 0.65 else "Medio" if nuevo_compromiso >= 0.35 else "Alto"
            escenarios.append({
                "accion": "Regularizar el estado de matrícula (actualmente no consta como matriculado)",
                "variable": "estado_matricula",
                "valor_actual": matricula or "sin datos",
                "valor_simulado": "Matriculado",
                "compromiso_actual": round(compromiso_simulado_base * 100),
                "compromiso_nuevo": round(nuevo_compromiso * 100),
                "ganancia": round(delta * 100),
                "nivel_riesgo_nuevo": nuevo_nivel,
                "factibilidad": "media",
                "plazo": "administrativo",
            })

    if not escenarios:
        return None

    # Ordenar por ganancia descendente
    escenarios.sort(key=lambda x: x["ganancia"], reverse=True)

    return {
        "tipo": "conductual",
        "compromiso_actual": round(compromiso_simulado_base * 100),
        "nivel_riesgo_actual": student.nivel_riesgo,
        "escenarios": escenarios,
    }
