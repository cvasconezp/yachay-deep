"""La ventana del bloque: no alertar por materias de un bloque que ya terminó.

CASO REAL (planteado por el usuario): un estudiante alertado por "56 días sin ingresar a
la materia Y". La materia Y era de Bloque 1 y ese bloque cerró hace más de un mes: no
entra porque la materia YA NO EXISTE. La alerta es correcta según el dato y absurda según
la realidad.

`días sin acceso` crece sola. Sin ventana temporal, todo curso terminado se convierte en
un generador infinito de alertas falsas, cada día más "graves".
"""
from datetime import datetime, timedelta, timezone

import pytest

from backend.models.course_config import SemesterConfig, CourseConfig
from backend.services.bloques import (
    ventana_bloque, dias_maximos_del_bloque, cursos_del_bloque_cerrado,
    bloque_esta_cerrado, acotar_dias,
)

AHORA = datetime(2026, 7, 16, tzinfo=timezone.utc)


def _sem(bloque="2", b1=(-120, -40), b2=(-38, 30)):
    """Fechas relativas a AHORA, en días."""
    return SemesterConfig(
        semestre="P68", activo=True, bloque_actual=bloque,
        bloque1_inicio=AHORA + timedelta(days=b1[0]), bloque1_fin=AHORA + timedelta(days=b1[1]),
        bloque2_inicio=AHORA + timedelta(days=b2[0]), bloque2_fin=AHORA + timedelta(days=b2[1]),
    )


# ── el reloj se detiene al cerrar el bloque ──
def test_bloque_en_curso_cuenta_hasta_hoy():
    assert dias_maximos_del_bloque(_sem(bloque="2"), AHORA) == 38


def test_bloque_cerrado_detiene_el_reloj():
    """EL BUG: (hoy - inicio) seguía creciendo tras el cierre, así que un bloque terminado
    hace un mes 'permitía' 30 días más de inactividad y la alerta empeoraba sola."""
    sem = _sem(bloque="1")                       # bloque 1: de -120 a -40 días
    dias = dias_maximos_del_bloque(sem, AHORA)
    assert dias == 80, "debe contar la vida del bloque (80d), no hasta hoy (120d)"


def test_ventana_no_pasa_del_fin():
    _, fin = ventana_bloque(_sem(bloque="1"), AHORA)
    assert fin == AHORA - timedelta(days=40)


def test_bloque_esta_cerrado():
    assert bloque_esta_cerrado(_sem(bloque="1"), AHORA) is True
    assert bloque_esta_cerrado(_sem(bloque="2"), AHORA) is False


# ── acotar días ──
def test_acotar_recorta_lo_imposible():
    """56 días sin acceso en un bloque que lleva 38 abierto es imposible."""
    assert acotar_dias(56, _sem(bloque="2"), AHORA) == 38


def test_acotar_respeta_lo_posible():
    assert acotar_dias(5, _sem(bloque="2"), AHORA) == 5


def test_acotar_tolera_none():
    assert acotar_dias(None, _sem(), AHORA) is None
    assert acotar_dias(10, None, AHORA) == 10


# ── excluir cursos del bloque cerrado ──
def test_excluye_los_cursos_del_otro_bloque(db):
    """El caso del usuario: estamos en bloque 2, la materia Y es de bloque 1."""
    db.add_all([
        CourseConfig(codigo_avac="111", asignatura="MATERIA Y", bloque="1", activo=True),
        CourseConfig(codigo_avac="222", asignatura="MATERIA Z", bloque="2", activo=True),
    ])
    db.commit()

    cerrados = cursos_del_bloque_cerrado(db, _sem(bloque="2"))
    assert "111" in cerrados, "la materia del bloque cerrado no debe alertar"
    assert "222" not in cerrados


def test_los_cursos_de_ambos_bloques_nunca_se_excluyen(db):
    db.add(CourseConfig(codigo_avac="333", asignatura="ANUAL", bloque="ambos", activo=True))
    db.commit()
    assert "333" not in cursos_del_bloque_cerrado(db, _sem(bloque="2"))


def test_sin_configuracion_no_excluye_nada(db):
    assert cursos_del_bloque_cerrado(db, None) == set()


def test_excluye_tambien_por_enrollment_bloque(db):
    """EL BUG: CourseConfig.bloque está sin poblar en producción. Mirando solo esa fuente
    salían 0 cursos a excluir cuando el generador de alertas encontraba 620 usando
    Enrollment.bloque, que es más completo."""
    from backend.models.enrollment import Enrollment
    db.add(Enrollment(student_id=None, codigo_grupo="999", asignatura="VIEJA",
                      bloque=1, periodo="68"))
    db.commit()

    cerrados = cursos_del_bloque_cerrado(db, _sem(bloque="2"))
    assert "999" in cerrados, "debe excluirse aunque CourseConfig no tenga el bloque"


def test_une_las_dos_fuentes(db):
    from backend.models.enrollment import Enrollment
    db.add(CourseConfig(codigo_avac="AAA", asignatura="A", bloque="1", activo=True))
    db.add(Enrollment(student_id=None, codigo_grupo="BBB", asignatura="B", bloque=1, periodo="68"))
    db.commit()
    assert {"AAA", "BBB"} <= cursos_del_bloque_cerrado(db, _sem(bloque="2"))


def test_fechas_naive_no_revientan():
    """Postgres puede devolver datetimes sin zona horaria."""
    sem = SemesterConfig(semestre="P68", activo=True, bloque_actual="2",
                         bloque2_inicio=datetime(2026, 6, 8), bloque2_fin=datetime(2026, 8, 15))
    assert dias_maximos_del_bloque(sem, AHORA) == 38


# ─────────────────────────────────────────────────────────────────────────────
# Tareas que aún no vencen
# ─────────────────────────────────────────────────────────────────────────────
import json
import pandas as pd
from backend.services.bloques import unidades_vencidas, filtrar_tareas_vencidas


def _sem_con_calendario(*dias_relativos):
    """Fechas de entrega relativas a AHORA."""
    cal = [
        {"fecha": (AHORA + timedelta(days=d)).date().isoformat(), "tipo": "entrega",
         "label": f"Entrega act. {i}"}
        for i, d in enumerate(dias_relativos, start=1)
    ]
    sem = _sem(bloque="2")
    sem.calendario_academico = json.dumps(cal)
    return sem


def _tareas(unidades):
    return pd.DataFrame({
        "correo": ["a@t.ec"] * len(unidades),
        "unidad": unidades,
        "entregada": [True] * len(unidades),
    })


def test_solo_las_unidades_con_fecha_pasada_estan_vencidas():
    """2 entregas pasadas, 2 futuras → solo vencen las unidades 1 y 2."""
    sem = _sem_con_calendario(-30, -10, 10, 30)
    assert unidades_vencidas(sem, AHORA) == {"1", "2"}


def test_sin_calendario_no_se_filtra():
    """Conservador: sin fechas configuradas no se puede saber, así que no se toca."""
    assert unidades_vencidas(_sem(bloque="2"), AHORA) is None
    df = _tareas(["1", "2", "3", "4"])
    assert len(filtrar_tareas_vencidas(df, _sem(bloque="2"), AHORA)) == 4


def test_descarta_las_tareas_que_aun_no_vencen():
    """EL BUG: quien entregó todo lo exigible salía con 50% porque contaban las futuras."""
    sem = _sem_con_calendario(-30, -10, 10, 30)
    df = _tareas(["1", "2", "3", "4"])
    out = filtrar_tareas_vencidas(df, sem, AHORA)
    assert set(out["unidad"]) == {"1", "2"}


def test_el_porcentaje_deja_de_estar_hundido():
    """Entregó las 2 vencidas y no las 2 futuras: es 100%, no 50%."""
    sem = _sem_con_calendario(-30, -10, 10, 30)
    df = pd.DataFrame({
        "correo": ["a@t.ec"] * 4,
        "unidad": ["1", "2", "3", "4"],
        "entregada": [True, True, False, False],
    })
    antes = df["entregada"].mean() * 100
    despues = filtrar_tareas_vencidas(df, sem, AHORA)["entregada"].mean() * 100
    assert antes == 50.0, "así se calculaba: castigaba por no haber entregado el futuro"
    assert despues == 100.0, "lo correcto: entregó todo lo exigible"


def test_si_no_ha_vencido_nada_no_deja_a_todos_a_cero():
    """Al inicio del bloque, filtrar todo dejaría a la institución sin datos de tareas."""
    sem = _sem_con_calendario(10, 20, 30)
    df = _tareas(["1", "2", "3"])
    assert len(filtrar_tareas_vencidas(df, sem, AHORA)) == 3


def test_df_vacio_no_revienta():
    sem = _sem_con_calendario(-10)
    assert len(filtrar_tareas_vencidas(pd.DataFrame(), sem, AHORA)) == 0
    assert filtrar_tareas_vencidas(None, sem, AHORA) is None


# ─────────────────────────────────────────────────────────────────────────────
# El calendario real de la UPS (P68) — mezcla los dos bloques
# ─────────────────────────────────────────────────────────────────────────────
CALENDARIO_UPS = json.dumps([
    {"fecha": "2026-04-06", "tipo": "inicio", "label": "Inicio primer bloque"},
    {"fecha": "2026-04-19", "tipo": "entrega", "label": "Entrega actividades 1"},
    {"fecha": "2026-05-03", "tipo": "entrega", "label": "Entrega actividades 2"},
    {"fecha": "2026-05-17", "tipo": "entrega", "label": "Entrega actividades 3"},
    {"fecha": "2026-05-29", "tipo": "entrega", "label": "Entrega actividades 4"},
    {"fecha": "2026-05-30", "tipo": "paso_notas", "label": "Paso de notas primer bloque"},
    {"fecha": "2026-06-08", "tipo": "inicio", "label": "Inicio segundo bloque"},
    {"fecha": "2026-06-21", "tipo": "entrega", "label": "Entrega actividades 1"},
    {"fecha": "2026-07-05", "tipo": "entrega", "label": "Entrega actividades 2"},
    {"fecha": "2026-07-19", "tipo": "entrega", "label": "Entrega actividades 3"},
    {"fecha": "2026-07-31", "tipo": "entrega", "label": "Entrega actividades 4"},
    {"fecha": "2026-08-01", "tipo": "paso_notas", "label": "Paso de notas segundo bloque"},
])


def _sem_ups(bloque="2"):
    return SemesterConfig(
        semestre="P68", activo=True, bloque_actual=bloque,
        bloque1_inicio=datetime(2026, 4, 6, tzinfo=timezone.utc),
        bloque1_fin=datetime(2026, 6, 7, tzinfo=timezone.utc),
        bloque2_inicio=datetime(2026, 6, 8, tzinfo=timezone.utc),
        bloque2_fin=datetime(2026, 8, 15, tzinfo=timezone.utc),
        calendario_academico=CALENDARIO_UPS,
    )


def test_calendario_real_solo_cuenta_las_entregas_del_bloque_2():
    # EL BUG: se enumeraban las entregas de AMBOS bloques seguidas y se incluía el paso de
    # notas. Al 16/07 daba "unidades 1..7 vencidas"; como las unidades reales son 1-4,
    # todas contaban y el filtro no descartaba nada (0 tareas descartadas en producción).
    venc = unidades_vencidas(_sem_ups("2"), AHORA)   # AHORA = 16/07/2026
    assert venc == {"1", "2"}, (
        f"solo vencieron las entregas del 21/06 y 05/07; las del 19/07 y 31/07 no. Dio {venc}"
    )


def test_en_el_bloque_1_cuenta_sus_propias_entregas():
    # Numeradas DENTRO del bloque: la 1a de B1 es la unidad 1, no la del semestre.
    venc = unidades_vencidas(_sem_ups("1"), datetime(2026, 5, 10, tzinfo=timezone.utc))
    assert venc == {"1", "2"}, "al 10/05 vencieron las del 19/04 y 03/05"


def test_el_paso_de_notas_no_cuenta_como_entrega():
    venc = unidades_vencidas(_sem_ups("2"), datetime(2026, 8, 2, tzinfo=timezone.utc))
    assert venc == {"1", "2", "3", "4"}, "4 entregas en B2 (el paso de notas no es una)"


def test_al_empezar_el_bloque_no_ha_vencido_nada():
    venc = unidades_vencidas(_sem_ups("2"), datetime(2026, 6, 10, tzinfo=timezone.utc))
    assert venc == set(), "el 10/06 aun no vencia ninguna entrega del bloque 2"


def test_el_porcentaje_con_el_calendario_real():
    # Entrego las 2 vencidas y no las 2 futuras: 100%, no 50%.
    df = pd.DataFrame({
        "correo": ["a@t.ec"] * 4,
        "unidad": ["1", "2", "3", "4"],
        "entregada": [True, True, False, False],
    })
    out = filtrar_tareas_vencidas(df, _sem_ups("2"), AHORA)
    assert set(out["unidad"]) == {"1", "2"}
    assert out["entregada"].mean() * 100 == 100.0
