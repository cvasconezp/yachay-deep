"""Cuarto nivel: "Sin riesgo".

Con solo tres niveles y ninguno neutro, TODO estudiante llevaba etiqueta de riesgo y
"Medio" acababa siendo el cajón de sastre (51.8% del total tras limpiar los datos). Una
etiqueta que lleva la mitad de la gente no sirve para priorizar, que es su único propósito.
"Sin riesgo" saca del radar a quien va bien y devuelve a "Bajo" su sentido de "vigilar de
lejos".
"""
from backend.etl.transformers import (
    calcular_indice_compromiso, UMBRAL_SIN_RIESGO, UMBRAL_BAJO, UMBRAL_MEDIO, NIVELES_RIESGO,
)


def _ind(**kw):
    base = dict(dias_sin_acceso=None, tareas_entregadas=10, tareas_totales=10, notas=[],
                promedio_calificaciones=95.0, estado_matricula="Matriculado",
                dias_desde_ultimo_acceso=0)
    base.update(kw)
    return calcular_indice_compromiso(**base)


def test_el_estudiante_ejemplar_sale_del_radar():
    """Entró hoy, entregó todo, notas de 95: no hay nada que vigilar."""
    r = _ind()
    assert r["indice_compromiso"] >= UMBRAL_SIN_RIESGO
    assert r["nivel_riesgo"] == "Sin riesgo"


def test_bajo_recupera_su_significado():
    """Va bien pero no perfecto: 'vigilar de lejos', no 'sin riesgo'."""
    r = _ind(dias_desde_ultimo_acceso=3, tareas_entregadas=8, promedio_calificaciones=75.0)
    assert UMBRAL_BAJO <= r["indice_compromiso"] < UMBRAL_SIN_RIESGO
    assert r["nivel_riesgo"] == "Bajo"


def test_los_otros_tres_niveles_no_cambian():
    medio = _ind(dias_desde_ultimo_acceso=10, tareas_entregadas=5, promedio_calificaciones=65.0)
    assert medio["nivel_riesgo"] == "Medio"
    alto = _ind(dias_desde_ultimo_acceso=60, tareas_entregadas=0, promedio_calificaciones=30.0)
    assert alto["nivel_riesgo"] == "Alto"


def test_los_umbrales_estan_ordenados():
    assert UMBRAL_MEDIO < UMBRAL_BAJO < UMBRAL_SIN_RIESGO <= 1.0


def test_el_orden_de_niveles_va_de_peor_a_mejor():
    assert NIVELES_RIESGO == ["Alto", "Medio", "Bajo", "Sin riesgo"]


def test_sin_datos_suficientes_sigue_sin_clasificar():
    """No clasificar es distinto de 'sin riesgo': no sabemos, no es que vaya bien."""
    r = calcular_indice_compromiso(
        dias_sin_acceso=None, tareas_entregadas=0, tareas_totales=0, notas=[],
        promedio_calificaciones=None, estado_matricula=None, dias_desde_ultimo_acceso=None,
    )
    assert r["nivel_riesgo"] is None


def test_justo_en_el_umbral_es_sin_riesgo():
    """Frontera inclusiva, como los demás umbrales."""
    r = _ind(dias_desde_ultimo_acceso=1, tareas_entregadas=9, promedio_calificaciones=85.0)
    assert (r["indice_compromiso"] >= UMBRAL_SIN_RIESGO) == (r["nivel_riesgo"] == "Sin riesgo")
