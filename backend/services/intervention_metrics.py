"""Umbrales de significancia para medir el efecto de una intervención.

FUENTE ÚNICA. Antes vivían duplicados: routes/interventions.py (panel individual) sí
usaba umbrales, pero analytics/effectiveness.py contaba como éxito CUALQUIER variación:

    exitosa = (delta_compromiso > 0) or (delta_prob_desercion < 0)

Eso no mide nada. Sin umbral, el ruido de medición cuenta como mejora; y al ser un OR
de dos condiciones aproximadamente independientes, con datos puramente aleatorios la
"tasa de éxito" tendería a ~75% (1 - 0.5*0.5). Es decir, el número salía alto aunque
las intervenciones no sirvieran. Las dos vistas además se contradecían entre sí.
"""

# Un cambio menor a estos valores no se considera mejora real.
UMBRAL_COMPROMISO = 0.03     # 3 puntos porcentuales (índice 0-1)
UMBRAL_DIAS_ACCESO = 2       # 2 días
UMBRAL_TAREAS = 5.0          # 5 puntos porcentuales
UMBRAL_PROB = 0.03           # 3 puntos porcentuales de probabilidad

# invertir=True → bajar es mejorar (días sin acceso, probabilidades de riesgo)
INDICADORES = {
    "compromiso":        {"umbral": UMBRAL_COMPROMISO,  "invertir": False},
    "dias_sin_acceso":   {"umbral": UMBRAL_DIAS_ACCESO, "invertir": True},
    "porcentaje_tareas": {"umbral": UMBRAL_TAREAS,      "invertir": False},
    "prob_desercion":    {"umbral": UMBRAL_PROB,        "invertir": True},
    "prob_reprobacion":  {"umbral": UMBRAL_PROB,        "invertir": True},
}


def clasificar(indicador: str, delta) -> str:
    """'mejora' | 'empeora' | 'sin_cambio' | 'sin_datos'."""
    cfg = INDICADORES.get(indicador)
    if cfg is None or delta is None:
        return "sin_datos"
    valor = -delta if cfg["invertir"] else delta
    if valor > cfg["umbral"]:
        return "mejora"
    if valor < -cfg["umbral"]:
        return "empeora"
    return "sin_cambio"


def evaluar(deltas: dict) -> dict:
    """Resume los deltas de una intervención aplicando los umbrales.

    'exitosa' exige al menos una mejora significativa Y ningún empeoramiento
    significativo: si un indicador mejora y otro se hunde, eso no es un éxito.
    """
    detalle, mejoras, empeoramientos = {}, 0, 0
    for ind, delta in deltas.items():
        if ind not in INDICADORES:
            continue
        c = clasificar(ind, delta)
        detalle[ind] = c
        if c == "mejora":
            mejoras += 1
        elif c == "empeora":
            empeoramientos += 1

    evaluados = sum(1 for v in detalle.values() if v != "sin_datos")
    return {
        "detalle": detalle,
        "mejoras": mejoras,
        "empeoramientos": empeoramientos,
        "evaluados": evaluados,
        "exitosa": mejoras > 0 and empeoramientos == 0,
        "concluyente": evaluados > 0,
    }
