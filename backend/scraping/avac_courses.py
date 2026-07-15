"""Resolución del aula correcta en AVAC a partir del código de curso.

Problema: `/course/search.php?q=408456` puede devolver VARIAS aulas, porque Moodle
busca el código también dentro del shortname de aulas combinadas. Ejemplo real:

  - id 7718 → shortname "408456"          ← el aula real
  - id 5013 → shortname "405109/408456"   ← aula de TUTORÍA que agrupa dos códigos

El código antiguo hacía `select_one(...)` (se quedaba con el PRIMER resultado), que
suele ser la de tutoría → datos vacíos o del curso equivocado.

Solución: cuando hay más de un candidato, se compara el shortname real de cada aula
contra el código buscado y gana la coincidencia EXACTA. El shortname se lee del
<title> de la página de participantes, que tiene formato "408456: Participantes | Grado 68"
(o "405109/408456 | Grado 68" si redirige a la página de matriculación).
"""
from urllib.parse import urlparse, parse_qs
import logging

logger = logging.getLogger(__name__)


def extraer_candidatos(soup) -> list[str]:
    """IDs de curso de los resultados de búsqueda, en el orden en que aparecen."""
    ids: list[str] = []

    def _add(cid):
        if cid and cid not in ids:
            ids.append(cid)

    for box in soup.select(".coursebox"):
        cid = box.get("data-courseid")
        if not cid:
            a = box.select_one("a[href*='view.php?id=']")
            if a and a.get("href"):
                cid = parse_qs(urlparse(a["href"]).query).get("id", [None])[0]
        _add(cid)

    if not ids:  # temas sin .coursebox
        for a in soup.select("a[href*='/course/view.php?id=']"):
            _add(parse_qs(urlparse(a.get("href", "")).query).get("id", [None])[0])
    return ids


def shortname_desde_titulo(soup) -> str | None:
    """'408456: Participantes | Grado 68' → '408456'.
    '405109/408456 | Grado 68'          → '405109/408456'."""
    if not soup.title:
        return None
    t = soup.title.get_text(strip=True)
    if not t:
        return None
    t = t.split("|")[0]      # quita el nombre del sitio
    t = t.split(":")[0]      # quita ': Participantes'
    return t.strip() or None


def resolver_course_id(codigo, candidatos: list[str], obtener_shortname) -> str | None:
    """Elige el id del aula que corresponde a `codigo`.

    obtener_shortname(course_id) -> str | None  (solo se llama si hay ambigüedad,
    así que el caso normal de 1 resultado no paga ninguna petición extra).
    """
    if not candidatos:
        return None
    if len(candidatos) == 1:
        return candidatos[0]

    codigo = str(codigo).strip()
    vistos = []
    for cid in candidatos:
        sn = obtener_shortname(cid)
        vistos.append((cid, sn))
        if sn and sn.strip() == codigo:
            logger.info(f"🎯 {codigo}: {len(candidatos)} aulas encontradas → id={cid} (shortname exacto)")
            return cid

    logger.warning(
        f"⚠️  {codigo}: {len(candidatos)} aulas y ninguna con shortname exacto {vistos}. "
        f"Se usa la primera (id={candidatos[0]}); revisa si el aula está bien nombrada en AVAC."
    )
    return candidatos[0]
