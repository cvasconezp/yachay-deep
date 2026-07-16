"""Umbrales de significancia: que la tasa de éxito deje de contar ruido."""
import pytest
from backend.services.intervention_metrics import clasificar, evaluar


def test_variacion_minima_no_es_mejora():
    """El fallo original: cualquier delta>0 contaba como éxito."""
    assert clasificar("compromiso", 0.001) == "sin_cambio"
    assert clasificar("porcentaje_tareas", 1.0) == "sin_cambio"
    assert clasificar("dias_sin_acceso", -1) == "sin_cambio"


def test_mejora_significativa_si_supera_el_umbral():
    assert clasificar("compromiso", 0.10) == "mejora"
    assert clasificar("porcentaje_tareas", 12.0) == "mejora"


def test_indicadores_invertidos_bajar_es_mejorar():
    assert clasificar("dias_sin_acceso", -5) == "mejora"
    assert clasificar("dias_sin_acceso", 5) == "empeora"
    assert clasificar("prob_desercion", -0.2) == "mejora"
    assert clasificar("prob_desercion", 0.2) == "empeora"


def test_sin_datos_no_rompe():
    assert clasificar("compromiso", None) == "sin_datos"
    assert clasificar("inventado", 1) == "sin_datos"


def test_no_es_exito_si_algo_empeora_de_verdad():
    """Mejorar tareas mientras la deserción se dispara no es un éxito."""
    r = evaluar({"porcentaje_tareas": 20.0, "prob_desercion": 0.30})
    assert r["mejoras"] == 1 and r["empeoramientos"] == 1
    assert r["exitosa"] is False


def test_exito_requiere_mejora_significativa():
    assert evaluar({"compromiso": 0.001, "porcentaje_tareas": 0.5})["exitosa"] is False
    assert evaluar({"compromiso": 0.10, "porcentaje_tareas": 0.5})["exitosa"] is True


def test_sin_datos_no_es_concluyente():
    r = evaluar({"compromiso": None, "prob_desercion": None})
    assert r["concluyente"] is False
    assert r["exitosa"] is False


def test_el_ruido_aleatorio_ya_no_da_75_por_ciento():
    """Regresión del bug de fondo.

    Con el criterio viejo (delta>0 OR delta<0, sin umbral), deltas aleatorios pequeños
    daban ~75% de 'éxito'. Con umbrales, el ruido cae en 'sin_cambio'.
    """
    import random
    random.seed(42)
    ruido = [
        {"compromiso": random.uniform(-0.01, 0.01),
         "porcentaje_tareas": random.uniform(-2, 2),
         "prob_desercion": random.uniform(-0.01, 0.01)}
        for _ in range(200)
    ]
    viejo = sum(1 for d in ruido if d["compromiso"] > 0 or d["prob_desercion"] < 0)
    nuevo = sum(1 for d in ruido if evaluar(d)["exitosa"])

    assert viejo > 130, f"el criterio viejo debería inflar (~150/200), dio {viejo}"
    assert nuevo == 0, f"el ruido no debe contar como éxito, contó {nuevo}"
