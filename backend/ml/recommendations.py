"""
Motor de recomendaciones automáticas — Fase 4 del Framework Yachay Deep.
Genera sugerencias de intervención basadas en:
  - Probabilidades de riesgo (deserción / reprobación)
  - Contribuciones XAI (factores que explican el riesgo)
  - Indicadores del estudiante (días sin acceso, compromiso, tareas)
  - Historial de intervenciones previas
  - Calendario académico y estado del semestre
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..models.student import Student
from ..models.intervention import Intervention
from ..models.grade import Grade

logger = logging.getLogger(__name__)

# ── Umbrales ─────────────────────────────────────────────────────────────────
PROB_ALTO = 0.70
PROB_MODERADO = 0.40
DIAS_CRITICO = 14
DIAS_ALERTA = 7
COMPROMISO_BAJO = 0.30
COMPROMISO_MEDIO = 0.55
# porcentaje_tareas se almacena en escala 0-100 en la BD
TAREAS_BAJO = 40
TAREAS_MEDIO = 60


def _get_semester_context(db: Session) -> dict:
    """Obtiene contexto del semestre: bloque actual, calendario, si hay notas."""
    ctx = {
        "tiene_notas_actuales": False,
        "bloque_actual": "1",
        "primera_entrega_pasada": False,
        "dias_desde_inicio": 0,
    }
    try:
        from ..models.course_config import SemesterConfig
        sc = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
        if not sc:
            return ctx

        ctx["bloque_actual"] = sc.bloque_actual or "1"
        periodo = sc.semestre.strip() if sc.semestre else None

        # ¿Hay notas del periodo actual?
        if periodo:
            from ..models.grade import Grade as _G
            conditions = [_G.periodo == periodo]
            if periodo.startswith("P"):
                conditions.append(_G.periodo == periodo[1:])
            else:
                conditions.append(_G.periodo == f"P{periodo}")
            has_grades = db.query(_G.id).filter(or_(*conditions)).limit(1).first()
            ctx["tiene_notas_actuales"] = has_grades is not None

        # Calendario académico: ¿ya pasó alguna fecha de entrega?
        if sc.calendario_academico:
            try:
                cal = json.loads(sc.calendario_academico)
                now = datetime.now(timezone.utc)
                for ev in cal:
                    fecha = ev.get("fecha")
                    if fecha and ev.get("tipo") == "entrega":
                        dt = datetime.fromisoformat(fecha).replace(tzinfo=timezone.utc) if "T" in fecha else datetime.strptime(fecha, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                        if now >= dt:
                            ctx["primera_entrega_pasada"] = True
                            break
            except Exception:
                pass

        # Días desde inicio del bloque actual
        inicio = sc.bloque1_inicio if ctx["bloque_actual"] == "1" else sc.bloque2_inicio
        if inicio:
            if inicio.tzinfo is None:
                inicio = inicio.replace(tzinfo=timezone.utc)
            ctx["dias_desde_inicio"] = (datetime.now(timezone.utc) - inicio).days

    except Exception as e:
        logger.warning(f"_get_semester_context error: {e}")
    return ctx


def get_dias_sin_acceso_bloque(db: Session, student_id: int) -> Optional[float]:
    """
    Calcula dias_sin_acceso EXCLUYENDO cursos del bloque opuesto.

    Usa enfoque de blacklist (como alerts.py): excluye cursos explícitamente
    marcados como bloque contrario. Cursos con bloque=NULL o "ambos" se incluyen.

    Returns:
        dias_sin_acceso filtrado por bloque, o None si no hay datos.
        Usa el MÍNIMO entre cursos del bloque (mejor caso = más reciente acceso).
    """
    try:
        from ..models.course_config import SemesterConfig, CourseConfig
        from ..models.avac_access import AvacAccess

        sc = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
        if not sc:
            return None  # sin config, no podemos filtrar

        bloque_actual = sc.bloque_actual or "1"
        otro_bloque = "2" if bloque_actual == "1" else "1"

        # Obtener códigos de cursos del bloque OPUESTO (para excluirlos)
        cursos_excluir = (
            db.query(CourseConfig.codigo_avac)
            .filter(CourseConfig.bloque == otro_bloque)
            .all()
        )
        codigos_excluir = {c[0] for c in cursos_excluir if c[0]}

        # Buscar el acceso más reciente del estudiante, excluyendo bloque opuesto
        from sqlalchemy import func as sqlfunc
        query = db.query(
            sqlfunc.min(AvacAccess.dias_sin_acceso)
        ).filter(
            AvacAccess.student_id == student_id,
            AvacAccess.dias_sin_acceso.isnot(None),
        )

        if codigos_excluir:
            query = query.filter(~AvacAccess.codigo_curso.in_(codigos_excluir))

        result = query.scalar()
        return result

    except Exception as e:
        logger.warning("get_dias_sin_acceso_bloque error for student %s: %s", student_id, e)
        return None


def _prioridad(nivel: str) -> int:
    return {"urgente": 0, "importante": 1, "sugerida": 2}.get(nivel, 3)


def generate_recommendations(
    db: Session,
    student_id: int,
    xai_data: Optional[dict] = None,
) -> list[dict]:
    """
    Genera lista de recomendaciones para un estudiante.
    Cada recomendación tiene:
      - prioridad: "urgente" / "importante" / "sugerida"
      - accion: qué hacer
      - motivo: por qué (basado en datos)
      - medio: canal sugerido (WhatsApp, Tutoría, Bienestar, etc.)
      - destinatario: quién debería actuar
      - categoria: agrupación temática
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return []

    recs: list[dict] = []
    sem_ctx = _get_semester_context(db)
    usando_fallback = bool(xai_data and xai_data.get("periodo_usado"))
    inicio_semestre = not sem_ctx["tiene_notas_actuales"]

    prob_des = student.prob_desercion or 0
    prob_rep = student.prob_reprobacion or 0
    # Usar dias_sin_acceso filtrado por bloque actual (excluye cursos de bloque 2 durante bloque 1)
    dias_bloque = get_dias_sin_acceso_bloque(db, student_id)
    dias = dias_bloque if dias_bloque is not None else student.dias_sin_acceso
    compromiso = student.indice_compromiso
    tareas = student.porcentaje_tareas

    # Intervenciones previas pendientes
    intervenciones = (
        db.query(Intervention)
        .filter(Intervention.student_id == student_id)
        .order_by(Intervention.created_at.desc())
        .all()
    )
    tiene_intervencion_pendiente = any(
        i.estado and i.estado.lower() not in ("resuelto", "retirado", "sna")
        for i in intervenciones
    )
    total_intervenciones = len(intervenciones)

    # Materias con nota < 70 del periodo actual (o fallback al más reciente)
    from .features import _get_active_periodo
    active_p = _get_active_periodo(db)
    if active_p:
        p_conditions = [Grade.periodo == active_p]
        if active_p.startswith("P"):
            p_conditions.append(Grade.periodo == active_p[1:])
        else:
            p_conditions.append(Grade.periodo == f"P{active_p}")
        # También incluir NULL como legacy fallback
        p_conditions.append(Grade.periodo.is_(None))
        materias_reprobadas = (
            db.query(Grade)
            .filter(
                Grade.student_id == student_id,
                or_(*p_conditions),
                Grade.nota_final.isnot(None),
                Grade.nota_final < 70,
            )
            .all()
        )
    else:
        materias_reprobadas = (
            db.query(Grade)
            .filter(
                Grade.student_id == student_id,
                Grade.periodo.is_(None),
                Grade.nota_final.isnot(None),
                Grade.nota_final < 70,
            )
            .all()
        )
    materias_cero = [g for g in materias_reprobadas if (g.nota_final or 0) == 0]

    # ═══════════════════════════════════════════════════════════════════════
    # REGLAS DE RECOMENDACIÓN
    # ═══════════════════════════════════════════════════════════════════════

    # ── 1. Inactividad AVAC ──────────────────────────────────────────────
    # Solo alertar si llevamos suficientes días desde el inicio del bloque
    # (evita falsos positivos al inicio del semestre)
    dias_desde_inicio = sem_ctx["dias_desde_inicio"]
    if dias is not None and dias >= DIAS_CRITICO and dias_desde_inicio >= DIAS_CRITICO:
        recs.append({
            "prioridad": "urgente",
            "accion": f"Contactar inmediatamente al estudiante — lleva {dias} días sin acceder al AVAC",
            "motivo": "La inactividad prolongada es el principal indicador de abandono silencioso",
            "medio": "WhatsApp o llamada telefónica",
            "destinatario": "Tutor / Monitor",
            "categoria": "inactividad",
        })
    elif dias is not None and dias >= DIAS_ALERTA and dias_desde_inicio >= DIAS_ALERTA:
        recs.append({
            "prioridad": "importante",
            "accion": f"Verificar situación del estudiante — {dias} días sin acceso al AVAC",
            "motivo": "Señal temprana de desvinculación académica",
            "medio": "WhatsApp",
            "destinatario": "Tutor / Monitor",
            "categoria": "inactividad",
        })

    # ── 2. Riesgo de deserción alto ──────────────────────────────────────
    if prob_des >= PROB_ALTO:
        recs.append({
            "prioridad": "urgente",
            "accion": "Derivar a Bienestar Estudiantil para valoración integral",
            "motivo": f"Probabilidad de deserción del {round(prob_des*100)}% — riesgo crítico de abandono",
            "medio": "Derivación institucional",
            "destinatario": "Bienestar Estudiantil",
            "categoria": "desercion",
        })
        if not tiene_intervencion_pendiente:
            recs.append({
                "prioridad": "urgente",
                "accion": "Registrar intervención de seguimiento con contacto directo",
                "motivo": "No existe intervención activa para un estudiante en riesgo crítico",
                "medio": "WhatsApp o llamada telefónica",
                "destinatario": "Tutor / Monitor",
                "categoria": "desercion",
            })
    elif prob_des >= PROB_MODERADO:
        recs.append({
            "prioridad": "importante",
            "accion": "Programar entrevista de seguimiento académico",
            "motivo": f"Probabilidad de deserción del {round(prob_des*100)}% — riesgo moderado",
            "medio": "Email o WhatsApp",
            "destinatario": "Tutor / Monitor",
            "categoria": "desercion",
        })

    # ── 3. Riesgo de reprobación ─────────────────────────────────────────
    # Al inicio del semestre (sin notas actuales), solo mostrar predicción general
    if prob_rep >= PROB_ALTO:
        if materias_reprobadas and not inicio_semestre:
            nombres = [g.asignatura for g in materias_reprobadas[:3] if g.asignatura]
            lista = ", ".join(nombres) if nombres else "materias con bajo rendimiento"
            recs.append({
                "prioridad": "urgente",
                "accion": f"Programar tutoría académica focalizada en: {lista}",
                "motivo": f"Probabilidad de reprobación del {round(prob_rep*100)}% con {len(materias_reprobadas)} materia(s) bajo 70",
                "medio": "Tutoría académica",
                "destinatario": "Docente de la asignatura",
                "categoria": "reprobacion",
            })
        elif usando_fallback:
            recs.append({
                "prioridad": "importante",
                "accion": "Monitorear de cerca al estudiante cuando se publiquen las primeras notas",
                "motivo": f"Predicción basada en periodo anterior: probabilidad de reprobación del {round(prob_rep*100)}%",
                "medio": "Seguimiento periódico",
                "destinatario": "Tutor / Monitor",
                "categoria": "reprobacion",
            })
        else:
            recs.append({
                "prioridad": "urgente",
                "accion": "Evaluar rendimiento actual y programar apoyo académico",
                "motivo": f"Probabilidad de reprobación del {round(prob_rep*100)}%",
                "medio": "Tutoría académica",
                "destinatario": "Docente / Tutor",
                "categoria": "reprobacion",
            })
    elif prob_rep >= PROB_MODERADO and materias_reprobadas and not inicio_semestre:
        nombres = [g.asignatura for g in materias_reprobadas[:2] if g.asignatura]
        lista = ", ".join(nombres) if nombres else "materias críticas"
        recs.append({
            "prioridad": "importante",
            "accion": f"Refuerzo académico sugerido en: {lista}",
            "motivo": f"{len(materias_reprobadas)} materia(s) con nota actual bajo 70",
            "medio": "Tutoría académica",
            "destinatario": "Docente de la asignatura",
            "categoria": "reprobacion",
        })

    # ── 4. Materias con nota cero ────────────────────────────────────────
    # Solo si hay notas actuales (no al inicio del semestre)
    if materias_cero and not inicio_semestre:
        nombres = [g.asignatura for g in materias_cero[:3] if g.asignatura]
        lista = ", ".join(nombres) if nombres else "materias sin calificación"
        recs.append({
            "prioridad": "urgente",
            "accion": f"Investigar situación en: {lista} — nota actual es 0",
            "motivo": "Notas en cero pueden indicar abandono de materia o error de registro",
            "medio": "WhatsApp o llamada telefónica",
            "destinatario": "Tutor / Monitor",
            "categoria": "academico",
        })

    # ── 5. Compromiso bajo ───────────────────────────────────────────────
    if compromiso is not None and compromiso < COMPROMISO_BAJO:
        recs.append({
            "prioridad": "importante",
            "accion": "Indagar causas de bajo compromiso académico",
            "motivo": f"Índice de compromiso de {round(compromiso*100)}% — muy por debajo del esperado",
            "medio": "Entrevista personal",
            "destinatario": "Tutor / Bienestar Estudiantil",
            "categoria": "compromiso",
        })
    elif compromiso is not None and compromiso < COMPROMISO_MEDIO:
        recs.append({
            "prioridad": "sugerida",
            "accion": "Monitorear evolución del compromiso académico",
            "motivo": f"Índice de compromiso de {round(compromiso*100)}% — nivel medio-bajo",
            "medio": "Seguimiento periódico",
            "destinatario": "Tutor / Monitor",
            "categoria": "compromiso",
        })

    # ── 6. Entrega de tareas baja ────────────────────────────────────────
    # Solo alertar si ya pasó al menos una fecha de entrega del calendario
    if tareas is not None and tareas < TAREAS_BAJO and sem_ctx["primera_entrega_pasada"]:
        recs.append({
            "prioridad": "importante",
            "accion": "Contactar para conocer razones de no entrega de tareas",
            "motivo": f"Solo ha entregado el {round(tareas)}% de tareas — riesgo de acumulación",
            "medio": "WhatsApp",
            "destinatario": "Tutor / Monitor",
            "categoria": "tareas",
        })
    elif tareas is not None and tareas < TAREAS_MEDIO and sem_ctx["primera_entrega_pasada"]:
        recs.append({
            "prioridad": "sugerida",
            "accion": "Recordar importancia de entrega oportuna de tareas",
            "motivo": f"Porcentaje de entrega de tareas: {round(tareas)}%",
            "medio": "Email",
            "destinatario": "Tutor / Monitor",
            "categoria": "tareas",
        })

    # ── 7. Recomendaciones basadas en XAI ────────────────────────────────
    # Solo generar recomendaciones XAI detalladas si hay notas actuales
    if xai_data and not inicio_semestre:
        _add_xai_recommendations(recs, xai_data, student)

    # ── 8. Eventos críticos / Derivaciones a Bienestar ────────────────────
    derivaciones = [
        i for i in intervenciones
        if i.derivar_bienestar
    ]
    if derivaciones:
        ultima_deriv = derivaciones[0]
        tipo = ultima_deriv.tipo_evento_critico or "Evento crítico"
        if not ultima_deriv.email_enviado:
            recs.append({
                "prioridad": "urgente",
                "accion": f"Verificar derivación a Bienestar — el correo no fue enviado ({tipo})",
                "motivo": "Se registró una derivación pero el correo no llegó al departamento de Bienestar",
                "medio": "Contacto directo con Bienestar Estudiantil",
                "destinatario": "Monitor / Coordinación",
                "categoria": "bienestar",
            })
        recs.append({
            "prioridad": "urgente",
            "accion": f"Seguimiento al caso derivado a Bienestar — {tipo}",
            "motivo": "Los eventos críticos requieren acompañamiento continuo para prevenir deserción",
            "medio": "Coordinación con Bienestar Estudiantil",
            "destinatario": "Bienestar Estudiantil / Tutor",
            "categoria": "bienestar",
        })

    # ── 9. Seguimiento de intervenciones previas ─────────────────────────
    pendientes_seguimiento = [
        i for i in intervenciones
        if i.requiere_seguimiento and i.requiere_seguimiento.lower() == "si"
        and (not i.estado or i.estado.lower() not in ("resuelto",))
    ]
    if pendientes_seguimiento:
        ultima = pendientes_seguimiento[0]
        recs.append({
            "prioridad": "importante",
            "accion": f"Dar seguimiento a intervención pendiente ({ultima.motivo or 'sin motivo'})",
            "motivo": f"Hay {len(pendientes_seguimiento)} intervención(es) que requieren seguimiento",
            "medio": ultima.medio or "WhatsApp",
            "destinatario": "Tutor / Monitor",
            "categoria": "seguimiento",
        })

    # ── 10. Sin intervenciones y riesgo medio+ ──────────────────────────
    if total_intervenciones == 0 and (prob_des >= PROB_MODERADO or prob_rep >= PROB_MODERADO):
        recs.append({
            "prioridad": "sugerida",
            "accion": "Realizar primer contacto de seguimiento con el estudiante",
            "motivo": "Estudiante con riesgo detectado pero sin ninguna intervención registrada",
            "medio": "WhatsApp o email",
            "destinatario": "Tutor / Monitor",
            "categoria": "seguimiento",
        })

    # Ordenar por prioridad
    recs.sort(key=lambda r: _prioridad(r["prioridad"]))

    return recs


def _add_xai_recommendations(recs: list, xai_data: dict, student: Student):
    """Genera recomendaciones específicas basadas en los factores XAI más influyentes."""
    for target, label in [("explicacion_desercion", "deserción"), ("explicacion_reprobacion", "reprobación")]:
        explicaciones = xai_data.get(target, [])
        if not explicaciones:
            continue

        # Solo considerar factores que incrementan el riesgo
        factores_riesgo = [f for f in explicaciones if f["direccion"] == "incrementa"]
        if not factores_riesgo:
            continue

        top = factores_riesgo[0]
        feature = top["feature"]
        valor = top["valor"]
        media = top["media_carrera"]

        if feature == "num_zeros" and valor > 0:
            recs.append({
                "prioridad": "importante",
                "accion": f"Investigar las {int(valor)} materia(s) con nota cero — principal factor de riesgo de {label}",
                "motivo": f"El promedio de la carrera es {media} materias con cero; este estudiante tiene {int(valor)}",
                "medio": "Revisión académica",
                "destinatario": "Coordinación académica",
                "categoria": "xai",
            })
        elif feature == "pct_reprobadas" and valor > media:
            recs.append({
                "prioridad": "importante",
                "accion": f"Atención al alto porcentaje de materias reprobadas ({round(valor, 1)}%) — factor principal de {label}",
                "motivo": f"El promedio de la carrera es {round(media, 1)}%; este estudiante está significativamente por encima",
                "medio": "Tutoría académica",
                "destinatario": "Docente / Tutor",
                "categoria": "xai",
            })
        elif feature == "nota_min" and valor < media:
            recs.append({
                "prioridad": "sugerida",
                "accion": f"Refuerzo focalizado en la materia con nota más baja ({round(valor, 1)}) — factor de {label}",
                "motivo": f"La nota mínima promedio en la carrera es {round(media, 1)}; este estudiante está por debajo",
                "medio": "Tutoría académica",
                "destinatario": "Docente de la asignatura",
                "categoria": "xai",
            })
        elif feature == "std_notas" and valor > media:
            recs.append({
                "prioridad": "sugerida",
                "accion": f"Evaluar rendimiento desigual entre materias — alta dispersión de notas",
                "motivo": f"Dispersión de {round(valor, 1)} vs promedio de carrera {round(media, 1)} — indica rendimiento muy variable",
                "medio": "Seguimiento periódico",
                "destinatario": "Tutor / Monitor",
                "categoria": "xai",
            })
