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


def test_fechas_naive_no_revientan():
    """Postgres puede devolver datetimes sin zona horaria."""
    sem = SemesterConfig(semestre="P68", activo=True, bloque_actual="2",
                         bloque2_inicio=datetime(2026, 6, 8), bloque2_fin=datetime(2026, 8, 15))
    assert dias_maximos_del_bloque(sem, AHORA) == 38
