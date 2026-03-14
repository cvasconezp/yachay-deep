"""
Motor de recomendaciones automáticas — Fase 4 del Framework Yachay Deep.
Genera sugerencias de intervención basadas en:
  - Probabilidades de riesgo (deserción / reprobación)
  - Contribuciones XAI (factores que explican el riesgo)
  - Indicadores del estudiante (días sin acceso, compromiso, tareas)
  - Historial de intervenciones previas
"""
from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session

from ..models.student import Student
from ..models.intervention import Intervention
from ..models.grade import Grade


# ── Umbrales ─────────────────────────────────────────────────────────────────
PROB_ALTO = 0.70
PROB_MODERADO = 0.40
DIAS_CRITICO = 14
DIAS_ALERTA = 7
COMPROMISO_BAJO = 0.30
COMPROMISO_MEDIO = 0.55
TAREAS_BAJO = 0.40
TAREAS_MEDIO = 0.60


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

    prob_des = student.prob_desercion or 0
    prob_rep = student.prob_reprobacion or 0
    dias = student.dias_sin_acceso
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

    # Materias actuales con nota < 70
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
    if dias is not None and dias >= DIAS_CRITICO:
        recs.append({
            "prioridad": "urgente",
            "accion": f"Contactar inmediatamente al estudiante — lleva {dias} días sin acceder al AVAC",
            "motivo": "La inactividad prolongada es el principal indicador de abandono silencioso",
            "medio": "WhatsApp o llamada telefónica",
            "destinatario": "Tutor / Monitor",
            "categoria": "inactividad",
        })
    elif dias is not None and dias >= DIAS_ALERTA:
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
    if prob_rep >= PROB_ALTO:
        if materias_reprobadas:
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
        else:
            recs.append({
                "prioridad": "urgente",
                "accion": "Evaluar rendimiento actual y programar apoyo académico",
                "motivo": f"Probabilidad de reprobación del {round(prob_rep*100)}%",
                "medio": "Tutoría académica",
                "destinatario": "Docente / Tutor",
                "categoria": "reprobacion",
            })
    elif prob_rep >= PROB_MODERADO and materias_reprobadas:
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
    if materias_cero:
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
    if tareas is not None and tareas < TAREAS_BAJO:
        recs.append({
            "prioridad": "importante",
            "accion": "Contactar para conocer razones de no entrega de tareas",
            "motivo": f"Solo ha entregado el {round(tareas*100)}% de tareas — riesgo de acumulación",
            "medio": "WhatsApp",
            "destinatario": "Tutor / Monitor",
            "categoria": "tareas",
        })
    elif tareas is not None and tareas < TAREAS_MEDIO:
        recs.append({
            "prioridad": "sugerida",
            "accion": "Recordar importancia de entrega oportuna de tareas",
            "motivo": f"Porcentaje de entrega de tareas: {round(tareas*100)}%",
            "medio": "Email",
            "destinatario": "Tutor / Monitor",
            "categoria": "tareas",
        })

    # ── 7. Recomendaciones basadas en XAI ────────────────────────────────
    if xai_data:
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
