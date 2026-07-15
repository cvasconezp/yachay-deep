"""Elegir el aula correcta cuando la búsqueda de AVAC devuelve varias.

Caso real (código 408456 en Grado 68):
  - id 5013 → "(A) INTEGRACIÓN CURRICULAR GRUPO - 1 TUTORIA", shortname "405109/408456"
  - id 7718 → "(A) MÉTODOS ALTERNATIVOS DE RESOLUCIÓN DE CONFLICTOS GRUPO - 1", shortname "408456"
El aula real es la 7718, pero aparece SEGUNDA en los resultados.
"""
from bs4 import BeautifulSoup
from backend.scraping.avac_courses import (
    extraer_candidatos, shortname_desde_titulo, resolver_course_id,
)

BUSQUEDA_2_RESULTADOS = """
<div class="courses">
  <div class="coursebox clearfix odd first" data-courseid="5013" data-type="1">
    <div class="info"><div class="coursename">
      <a class="aalink" href="https://avac.ups.edu.ec/grado68/course/view.php?id=5013">(A) INTEGRACIÓN CURRICULAR GRUPO - 1 TUTORIA</a>
    </div></div>
    <div class="content"><div class="coursecat">Categoría: NIVEL 8</div></div>
  </div>
  <div class="coursebox clearfix even last" data-courseid="7718" data-type="1">
    <div class="info"><div class="coursename">
      <a class="aalink" href="https://avac.ups.edu.ec/grado68/course/view.php?id=7718">(A) MÉTODOS ALTERNATIVOS DE RESOLUCIÓN DE CONFLICTOS GRUPO - 1</a>
    </div></div>
    <div class="content"><div class="coursecat">Categoría: NIVEL 5</div></div>
  </div>
</div>
"""

SHORTNAMES = {"5013": "405109/408456", "7718": "408456"}


def _soup(html):
    return BeautifulSoup(html, "html.parser")


def test_extrae_los_dos_candidatos_en_orden():
    assert extraer_candidatos(_soup(BUSQUEDA_2_RESULTADOS)) == ["5013", "7718"]


def test_shortname_desde_titulo_pagina_participantes():
    s = _soup("<html><head><title>408456: Participantes | Grado 68</title></head></html>")
    assert shortname_desde_titulo(s) == "408456"


def test_shortname_desde_titulo_pagina_matriculacion():
    s = _soup("<html><head><title>405109/408456 | Grado 68</title></head></html>")
    assert shortname_desde_titulo(s) == "405109/408456"


def test_elige_el_aula_real_no_la_de_tutoria():
    """El fallo reportado: antes se quedaba con 5013 (TUTORIA) por ser la primera."""
    candidatos = extraer_candidatos(_soup(BUSQUEDA_2_RESULTADOS))
    elegido = resolver_course_id("408456", candidatos, lambda cid: SHORTNAMES[cid])
    assert elegido == "7718"


def test_un_solo_resultado_no_pide_shortname():
    """Caso normal: no debe pagar peticiones extra."""
    llamadas = []

    def _sn(cid):
        llamadas.append(cid)
        return "408456"

    assert resolver_course_id("408456", ["7718"], _sn) == "7718"
    assert llamadas == []


def test_sin_coincidencia_exacta_usa_la_primera_y_no_revienta():
    elegido = resolver_course_id("999999", ["5013", "7718"], lambda cid: SHORTNAMES[cid])
    assert elegido == "5013"


def test_sin_candidatos_devuelve_none():
    assert resolver_course_id("408456", [], lambda cid: None) is None


def test_shortname_none_no_rompe_la_seleccion():
    elegido = resolver_course_id("408456", ["5013", "7718"], lambda cid: None if cid == "5013" else "408456")
    assert elegido == "7718"
