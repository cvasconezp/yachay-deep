"""El componente de acceso debe medir el uso de la PLATAFORMA, no la materia abandonada.

MEDIDO SOBRE DATOS REALES (5.996 estudiantes, julio 2026):
    máximo entre asignaturas:  prom. 34.9 días → puntaje 0.0091 de 0.30
    último acceso real:        prom.  4.2 días → puntaje 0.1977 de 0.30   (22x)

2.485 estudiantes habían entrado a AVAC en los últimos 7 días, pero 2.379 tenían alguna
materia sin tocar hace más de 30. Con varias materias eso es casi inevitable: el 30% del
índice se anulaba para casi todos y solo 33 de 3.493 lograban salir "Bajo". El modelo no
discriminaba, condenaba.
"""
from backend.etl.transformers import calcular_indice_compromiso


def _ind(**kw):
    base = dict(dias_sin_acceso=None, tareas_entregadas=8, tareas_totales=10, notas=[],
                promedio_calificaciones=75.0, estado_matricula="Matriculado")
    base.update(kw)
    return calcular_indice_compromiso(**base)


def test_el_caso_tenesaca_deja_de_estar_condenado(db):
    """Entra a diario pero tiene una materia abandonada hace 99 días."""
    r = _ind(dias_sin_acceso=99, dias_desde_ultimo_acceso=2)
    assert r["puntaje_acceso"] > 0.24, "entró hace 2 días: el componente debe estar casi lleno"
    assert r["nivel_riesgo"] in ("Bajo", "Sin riesgo")


def test_sin_el_arreglo_el_mismo_estudiante_sale_alto(db):
    """Prueba de que la causa era el estadístico: mismo estudiante, juzgado por el máximo."""
    r = _ind(dias_sin_acceso=99)          # sin dias_desde_ultimo_acceso → usa el máximo
    assert r["puntaje_acceso"] < 0.01
    assert r["nivel_riesgo"] != "Bajo"


def test_quien_de_verdad_no_entra_sigue_en_riesgo(db):
    """El arreglo no debe amnistiar a los que sí están abandonando."""
    r = _ind(dias_sin_acceso=87, dias_desde_ultimo_acceso=87, tareas_entregadas=0,
             tareas_totales=10, promedio_calificaciones=40.0)
    assert r["nivel_riesgo"] == "Alto"


def test_el_promedio_institucional_pasa_de_alto_a_medio(db):
    """Con los promedios REALES: 34.9d de máximo, 4.2d de último acceso, 45% de tareas.

    promedio_calificaciones=None reproduce el dato real: notas+admin sumaban 0.183, que
    es exactamente el default de "sin calificaciones" (0.04) + matriculado (0.15). A mitad
    de bloque la mayoría aún no tiene notas cargadas.
    """
    con_maximo = _ind(dias_sin_acceso=34.9, tareas_entregadas=45, tareas_totales=100,
                      promedio_calificaciones=None)
    con_ultimo = _ind(dias_sin_acceso=34.9, dias_desde_ultimo_acceso=4.2,
                      tareas_entregadas=45, tareas_totales=100,
                      promedio_calificaciones=None)
    assert con_maximo["indice_compromiso"] < con_ultimo["indice_compromiso"]
    assert con_maximo["nivel_riesgo"] == "Alto"
    assert con_ultimo["nivel_riesgo"] == "Medio"


def test_compatibilidad_hacia_atras(db):
    """Sin el dato nuevo, se comporta como antes (no rompe llamadas existentes)."""
    a = _ind(dias_sin_acceso=20)
    b = _ind(dias_sin_acceso=20, dias_desde_ultimo_acceso=None)
    assert a["puntaje_acceso"] == b["puntaje_acceso"]


def test_sin_ningun_dato_de_acceso_sigue_siendo_señal(db):
    r = _ind(dias_sin_acceso=None, dias_desde_ultimo_acceso=None)
    assert r["puntaje_acceso"] == 0.03


def test_un_buen_estudiante_puede_ser_bajo(db):
    """Antes era aritméticamente imposible para el promedio."""
    r = _ind(dias_sin_acceso=30, dias_desde_ultimo_acceso=1,
             tareas_entregadas=8, tareas_totales=10, promedio_calificaciones=75.0)
    assert r["nivel_riesgo"] in ("Bajo", "Sin riesgo"), f"quedó {r['indice_compromiso']}"
