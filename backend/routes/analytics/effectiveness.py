"""
Épica 4.2: Análisis de Efectividad de Intervenciones

Compara snapshots pre-intervención con estado actual post-intervención
para medir el impacto real de las intervenciones.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc, case, and_

from ...database import get_db
from ...models.student import Student
from ...models.intervention import Intervention
from ...auth.jwt import get_current_user
from ...services.intervention_metrics import evaluar, clasificar, INDICADORES

router = APIRouter(prefix="/analytics/effectiveness", tags=["analytics-effectiveness"])


def _calcular_efectividad_intervencion(inv, student) -> dict:
    """Calcula el delta de indicadores para una intervención cerrada."""
    result = {
        "intervention_id": inv.id,
        "student_id": inv.student_id,
        "medio": inv.medio,
        "motivo": inv.motivo,
        "resultado": inv.resultado,
        "estado_workflow": inv.estado_workflow,
        "carrera": inv.carrera,
    }

    # Deltas: comparar snapshot (momento de intervención) con estado actual
    if inv.snapshot_compromiso is not None and student and student.indice_compromiso is not None:
        result["delta_compromiso"] = round(student.indice_compromiso - inv.snapshot_compromiso, 3)
    else:
        result["delta_compromiso"] = None

    if inv.snapshot_porcentaje_tareas is not None and student and student.porcentaje_tareas is not None:
        result["delta_tareas"] = round(student.porcentaje_tareas - inv.snapshot_porcentaje_tareas, 1)
    else:
        result["delta_tareas"] = None

    if inv.snapshot_prob_desercion is not None and student and student.prob_desercion is not None:
        result["delta_prob_desercion"] = round(student.prob_desercion - inv.snapshot_prob_desercion, 3)
    else:
        result["delta_prob_desercion"] = None

    # Días sin acceso: también entra en la evaluación (bajar es mejorar)
    if inv.snapshot_dias_sin_acceso is not None and student and student.dias_sin_acceso is not None:
        result["delta_dias_sin_acceso"] = student.dias_sin_acceso - inv.snapshot_dias_sin_acceso
    else:
        result["delta_dias_sin_acceso"] = None

    # Éxito con UMBRALES de significancia (mismos que el panel individual).
    # Antes bastaba con delta>0, así que el ruido contaba como mejora.
    ev = evaluar({
        "compromiso": result["delta_compromiso"],
        "dias_sin_acceso": result["delta_dias_sin_acceso"],
        "porcentaje_tareas": result["delta_tareas"],
        "prob_desercion": result["delta_prob_desercion"],
    })
    result["exitosa"] = ev["exitosa"]
    result["concluyente"] = ev["concluyente"]
    result["mejoras"] = ev["mejoras"]
    result["empeoramientos"] = ev["empeoramientos"]
    result["detalle"] = ev["detalle"]

    return result


@router.get("")
def get_effectiveness(
    periodo: str = Query(None),
    dias_minimos: int = Query(14, ge=0, le=180,
                             description="Antigüedad mínima de la intervención para poder medirla"),
    solo_cerradas: bool = Query(False,
                                description="Restringir a intervenciones marcadas resueltas/cerradas"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Evolución de los estudiantes intervenidos, con umbrales de significancia.

    Se miden las intervenciones con al menos `dias_minimos` de antigüedad: sin tiempo
    transcurrido no hay "después" que comparar. No se exige que estén cerradas.
    """

    # Antes se exigía estado_workflow in ("resuelto","cerrado"). Pero ese campo NO se
    # escribe desde ninguna pantalla de la app: se quedaba en "pendiente" siempre, así que
    # esta vista estaba condenada a salir vacía hiciera lo que hiciera el usuario (que
    # marcaba `resultado`, otro campo distinto).
    #
    # Lo que hace medible una intervención es el TIEMPO transcurrido y tener una foto del
    # antes, no el trámite administrativo de cerrarla. Se mide por ahí.
    from datetime import datetime, timedelta, timezone
    corte = datetime.now(timezone.utc) - timedelta(days=dias_minimos)

    q = db.query(Intervention).filter(Intervention.created_at <= corte)
    if periodo:
        q = q.filter(Intervention.periodo == periodo)
    if solo_cerradas:
        q = q.filter(Intervention.estado_workflow.in_(["resuelto", "cerrado"]))

    intervenciones = q.all()

    # Cuántas quedaron fuera y por qué. Sin esto, el usuario ve 70 en Intervenciones y 48
    # aquí, y no tiene forma de saber qué pasó con las otras 22.
    q_todas = db.query(Intervention)
    if periodo:
        q_todas = q_todas.filter(Intervention.periodo == periodo)
    total_periodo = q_todas.count()
    excluidas_recientes = total_periodo - q.count() if not solo_cerradas else None

    if not intervenciones:
        return {
            "total_analizadas": 0,
            "motivo_vacio": (
                f"No hay intervenciones con al menos {dias_minimos} días de antigüedad"
                + (" y marcadas como resueltas/cerradas" if solo_cerradas else "")
                + ". El impacto necesita tiempo transcurrido para poder medirse."
            ),
            "tasa_exito_global": 0,
            "por_medio": [],
            "por_motivo": [],
            "por_carrera": [],
            "ranking_medios": [],
        }

    # Obtener estudiantes para comparación
    student_ids = list({inv.student_id for inv in intervenciones if inv.student_id})
    students_map = {}
    if student_ids:
        students = db.query(Student).filter(Student.id.in_(student_ids)).all()
        students_map = {s.id: s for s in students}

    # El retiro es un DESENLACE, no un fracaso de la intervención: el estudiante ya no
    # está, así que sus indicadores nunca van a mejorar. Contarlos como "no exitosas"
    # hundía la tasa por un motivo que no tiene que ver con la calidad del contacto.
    resultados = []
    retirados = 0
    for inv in intervenciones:
        student = students_map.get(inv.student_id)
        if student is not None and getattr(student, "retirado", False):
            retirados += 1
            continue
        resultados.append(_calcular_efectividad_intervencion(inv, student))

    total = len(resultados)
    concluyentes = [r for r in resultados if r.get("concluyente")]
    exitosas = sum(1 for r in concluyentes if r["exitosa"])
    # Sin este desglose no se distingue "el criterio es exigente" de "no está funcionando"
    con_empeoramiento = sum(1 for r in concluyentes if r.get("empeoramientos", 0) > 0)
    sin_mejora = sum(1 for r in concluyentes
                     if r.get("mejoras", 0) == 0 and r.get("empeoramientos", 0) == 0)
    mejora_parcial = sum(1 for r in concluyentes
                         if r.get("mejoras", 0) > 0 and r.get("empeoramientos", 0) > 0)
    # Denominador = solo las que tienen datos suficientes. Una intervención sin datos
    # no es un fracaso; contarla como tal hundiría la tasa artificialmente.
    tasa_global = round(exitosas / len(concluyentes) * 100, 1) if concluyentes else 0

    # ── Por indicador: la lectura honesta ────────────────────────────────────────
    # El binario "exitosa" miente en los dos sentidos: sin umbral cuenta ruido; con
    # "cero empeoramientos" basta un indicador ruidoso para tumbar un caso que mejoró en
    # todo lo demás. Reportar indicador por indicador dice la verdad sin resumirla mal.
    por_indicador = {}
    for ind, campo in (("dias_sin_acceso", "delta_dias_sin_acceso"),
                       ("compromiso", "delta_compromiso"),
                       ("porcentaje_tareas", "delta_tareas"),
                       ("prob_desercion", "delta_prob_desercion")):
        mejoraron = empeoraron = igual = sin_datos = 0
        for r in resultados:
            c = clasificar(ind, r.get(campo))
            if c == "mejora": mejoraron += 1
            elif c == "empeora": empeoraron += 1
            elif c == "sin_cambio": igual += 1
            else: sin_datos += 1
        medidos = mejoraron + empeoraron + igual
        por_indicador[ind] = {
            "mejoraron": mejoraron, "empeoraron": empeoraron,
            "sin_cambio": igual, "sin_datos": sin_datos, "medidos": medidos,
            "pct_mejoraron": round(mejoraron / medidos * 100, 1) if medidos else None,
        }

    # Al menos una mejora significativa (sin exigir que nada empeore)
    con_alguna_mejora = sum(1 for r in concluyentes if r.get("mejoras", 0) > 0)

    # ── ¿Hubo contacto de verdad? ────────────────────────────────────────────────
    # "No contestó" o "Buzón de voz" no son intervenciones fallidas: son intentos que no
    # llegaron. Contarlos como "la intervención no funcionó" es como contar una carta
    # devuelta al remitente como "la carta no convenció".
    #
    # Se reportan las dos lecturas, que es lo estándar al evaluar:
    #   - por intención de tratar: todos los intentos. No alcanzar a la gente TAMBIÉN es
    #     un fallo del proceso, y esconderlo maquilla el resultado.
    #   - por contacto efectivo: solo quienes respondieron. Mide si hablar sirve.
    # La diferencia entre ambas dice si el problema es el mensaje o la capacidad de llegar.
    SIN_RESPUESTA = {"no contestó", "no contesto", "buzón de voz", "buzon de voz",
                     "mensaje enviado sin respuesta"}
    def _hubo_contacto(r):
        res = (r.get("resultado") or "").strip().lower()
        if not res:
            return None                      # aún sin registrar
        return res not in SIN_RESPUESTA

    contactados = [r for r in concluyentes if _hubo_contacto(r) is True]
    sin_respuesta = sum(1 for r in resultados if _hubo_contacto(r) is False)
    sin_registrar = sum(1 for r in resultados if _hubo_contacto(r) is None)
    exitosas_contactadas = sum(1 for r in contactados if r["exitosa"])
    con_mejora_contactadas = sum(1 for r in contactados if r.get("mejoras", 0) > 0)

    # ── Matriz de transición de riesgo ───────────────────────────────────────────
    # "¿Cuántos se recuperaron?" en el lenguaje que todo el mundo entiende.
    NIVELES = ["Alto", "Medio", "Bajo"]
    _orden = {n.lower(): i for i, n in enumerate(NIVELES)}
    matriz, mejoraron_nivel, empeoraron_nivel, se_mantuvieron = {}, 0, 0, 0
    for inv in intervenciones:
        st = students_map.get(inv.student_id)
        antes = (inv.snapshot_nivel_riesgo or "").strip().capitalize()
        ahora = ((st.nivel_riesgo if st else None) or "").strip().capitalize()
        if antes not in NIVELES or ahora not in NIVELES:
            continue
        clave = f"{antes}->{ahora}"
        matriz[clave] = matriz.get(clave, 0) + 1
        if _orden[ahora.lower()] > _orden[antes.lower()]:
            mejoraron_nivel += 1      # Alto(0) -> Medio(1) = mejora
        elif _orden[ahora.lower()] < _orden[antes.lower()]:
            empeoraron_nivel += 1
        else:
            se_mantuvieron += 1

    # Agrupación por medio
    por_medio = _agrupar_por(resultados, "medio")
    # Agrupación por motivo
    por_motivo = _agrupar_por(resultados, "motivo")
    # Agrupación por carrera
    por_carrera = _agrupar_por(resultados, "carrera")

    # Ranking de medios más efectivos — solo los que tienen muestra suficiente.
    # Ordenar por tasa sin filtrar dejaba arriba a grupos de 2 o 3 casos.
    ranking = sorted(
        [m for m in por_medio if m["muestra_suficiente"]],
        key=lambda x: x["tasa_exito"], reverse=True,
    )

    return {
        "total_analizadas": total,
        "retirados_excluidos": retirados,
        "total_periodo": total_periodo,
        "excluidas_por_recientes": excluidas_recientes,
        "dias_minimos": dias_minimos,
        "solo_cerradas": solo_cerradas,
        "analizadas_concluyentes": len(concluyentes),
        "sin_datos_suficientes": total - len(concluyentes),
        "tasa_exito_global": tasa_global,
        "exitosas": exitosas,
        "no_exitosas": len(concluyentes) - exitosas,
        "desglose_no_exitosas": {
            "mejoro_pero_empeoro_en_otro": mejora_parcial,
            "sin_cambios_significativos": sin_mejora,
            "solo_empeoro": con_empeoramiento - mejora_parcial,
        },
        "criterio_exito": (
            "Al menos una mejora por encima del umbral Y ningún empeoramiento por encima "
            "del umbral. Es un criterio exigente a propósito: mejorar un indicador mientras "
            "otro se hunde no es un éxito."
        ),
        "por_medio": por_medio,
        "por_motivo": por_motivo,
        "por_carrera": por_carrera,
        "ranking_medios": ranking,
        "con_alguna_mejora": con_alguna_mejora,
        "contacto": {
            "sin_respuesta": sin_respuesta,
            "sin_registrar": sin_registrar,
            "contactados_medidos": len(contactados),
            "tasa_contacto_efectivo": (
                round(len(contactados) / (len(contactados) + sin_respuesta) * 100, 1)
                if (len(contactados) + sin_respuesta) else None
            ),
            # Solo entre quienes SÍ respondieron
            "exitosas_entre_contactados": exitosas_contactadas,
            "con_mejora_entre_contactados": con_mejora_contactadas,
            "tasa_exito_entre_contactados": (
                round(exitosas_contactadas / len(contactados) * 100, 1) if contactados else None
            ),
            "como_leerlo": (
                "'tasa_exito_global' cuenta todos los intentos (intención de tratar); "
                "'tasa_exito_entre_contactados' solo a quienes respondieron. Si la primera "
                "es mucho peor que la segunda, el problema no es el mensaje: es que no se "
                "está logrando contactar a los estudiantes."
            ),
        },
        "por_indicador": por_indicador,
        "transicion_riesgo": {
            "matriz": matriz,
            "bajaron_de_nivel": mejoraron_nivel,
            "subieron_de_nivel": empeoraron_nivel,
            "se_mantuvieron": se_mantuvieron,
            "total": mejoraron_nivel + empeoraron_nivel + se_mantuvieron,
        },
        "umbrales": {k: v["umbral"] for k, v in INDICADORES.items()},
        "advertencia": (
            "Mide la evolución de los estudiantes intervenidos, NO el efecto causal de "
            "la intervención. Los intervenidos se eligen por estar en el extremo peor, y "
            "los extremos tienden a mejorar solos (reversión a la media). Para estimar el "
            "efecto atribuible use /analytics/effectiveness/comparado."
        ),
    }


# Por debajo de este N, una tasa de éxito no significa nada: con 3 casos, uno solo
# mueve la cifra 33 puntos. Se calcula igual pero se marca como no fiable.
MIN_MUESTRA_FIABLE = 10


def _agrupar_por(resultados: list, campo: str) -> list:
    """Agrupa por un campo y calcula la tasa de éxito SOLO sobre las concluyentes."""
    grupos = {}
    for r in resultados:
        key = r.get(campo) or "Sin especificar"
        if key not in grupos:
            grupos[key] = {"total": 0, "concluyentes": 0, "exitosas": 0,
                           "delta_compromiso_sum": 0, "delta_count": 0}
        grupos[key]["total"] += 1
        if r.get("concluyente"):
            grupos[key]["concluyentes"] += 1
            if r["exitosa"]:
                grupos[key]["exitosas"] += 1
        if r.get("delta_compromiso") is not None:
            grupos[key]["delta_compromiso_sum"] += r["delta_compromiso"]
            grupos[key]["delta_count"] += 1

    return [{
        campo: k,
        "total": v["total"],
        "concluyentes": v["concluyentes"],
        "exitosas": v["exitosas"],
        "tasa_exito": round(v["exitosas"] / v["concluyentes"] * 100, 1) if v["concluyentes"] else 0,
        "muestra_suficiente": v["concluyentes"] >= MIN_MUESTRA_FIABLE,
        "delta_compromiso_promedio": round(v["delta_compromiso_sum"] / v["delta_count"], 3) if v["delta_count"] else None,
    } for k, v in sorted(grupos.items(), key=lambda x: x[1]["total"], reverse=True)]


@router.get("/comparado")
def get_effectiveness_comparado(
    periodo: str = Query(None),
    dias_seguimiento: int = Query(30, ge=7, le=180),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Efecto estimado de intervenir, comparando contra no intervenidos comparables.

    A diferencia de /analytics/effectiveness (que solo mira el antes/después de los
    intervenidos), aquí se descuenta lo que habría pasado igualmente. Es lo único que
    permite hablar de efecto atribuible — y aun así es una estimación, no una prueba.
    """
    from ...services.cohort_comparison import comparar_cohortes
    return comparar_cohortes(db, periodo=periodo, dias_seguimiento=dias_seguimiento)


@router.get("/desenlaces")
def get_desenlaces(
    periodo: str = Query(..., description="Período a evaluar, ej. P68"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Qué pasó DE VERDAD: aprobó, reprobó, continuó o no.

    El resto de la vista de impacto se apoya en prob_desercion / prob_reprobacion, que son
    PREDICCIONES. Esto mira hechos: notas finales y matrícula del período siguiente.
    Solo hay datos al cierre del período; si no los hay, se dice.
    """
    from ...services.outcomes import desenlaces_intervenidos
    return desenlaces_intervenidos(db, periodo)
