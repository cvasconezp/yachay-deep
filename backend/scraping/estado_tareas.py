"""
Scraping de Estado de Tareas — versión headless con TOTP 2FA.
Reemplaza bloque1_estado_tareas.py con login automático.
"""
import os
import time
import datetime
import re
import unicodedata
import logging
import pandas as pd
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# ESTRUCTURA FIJA DE COLUMNAS (replica Power Query)
# ─────────────────────────────────────────────────────────────────────────────
COLUMNAS_ESTANDAR = [
    "Nombre", "Correo", "Total del Curso", "Total Entregas", "Total Calificadas"
]

CAMPOS_DETALLE = [
    "Estado", "Calificación", "Última modificación (entrega)",
    "Archivos enviados", "Última modificación (calificación)",
    "Comentarios de retroalimentación", "Anotar PDF",
    "Archivos de retroalimentación", "Calificación final"
]

ORDEN_UNIDADES_SALIDA = ["4", "2", "3", "1"]

for _u in ORDEN_UNIDADES_SALIDA:
    for _campo in CAMPOS_DETALLE:
        COLUMNAS_ESTANDAR.append(f"{_campo} {_u}")

COLUMNAS_ESTANDAR.extend(["Código Curso", "Fecha Extracción"])

EQUIVALENCIA_UNIDADES = {
    "1": ["1", "uno", "i"], "2": ["2", "dos", "ii"],
    "3": ["3", "tres", "iii"], "4": ["4", "cuatro", "iv"],
}

PALABRAS_EXCLUIDAS = ["autoevaluacion", "cuestionario", "examen", "recuperacion", "asistencia"]

BASE_URL = os.getenv("AVAC_BASE_URL", "https://avac.ups.edu.ec/grado68")


# ─────────────────────────────────────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────────────────────────────────────

def _limpiar(texto):
    if not texto:
        return ""
    return texto.replace("\n", " ").replace("\r", " ").replace("\t", " ").replace(";", ",").strip()


def _normalizar(texto):
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("utf-8")
    return re.sub(r"[^a-zA-Z0-9]", " ", texto).lower()


# ─────────────────────────────────────────────────────────────────────────────
# SCRAPING DE REPORTE GENERAL (CALIFICACIONES)
# ─────────────────────────────────────────────────────────────────────────────

def _procesar_reporte_general(soup, es_especial=False):
    """
    Procesa el HTML de calificaciones del curso y extrae Total del Curso por alumno.
    Para cursos especiales también extrae totales de unidad.
    Recibe un BeautifulSoup ya parseado (evita requests duplicadas).
    """
    datos = {}
    try:

        headers = soup.select(
            "table#user-grades tr.heading th, table.generaltable tr th.header"
        )

        idx_email = idx_nombre = idx_total_curso = -1
        mapa_unidades = {}

        for idx, th in enumerate(headers):
            texto = _normalizar(th.get_text(strip=True) + " " + (th.get("title") or ""))
            if "correo" in texto or "email" in texto:
                idx_email = idx
            elif "nombre" in texto and idx_nombre == -1:
                idx_nombre = idx
            if "total" in texto and "curso" in texto:
                idx_total_curso = idx
            if es_especial and "total" in texto:
                for u, keys in EQUIVALENCIA_UNIDADES.items():
                    if any(k in texto for k in keys):
                        mapa_unidades[idx] = u
                        break

        filas = soup.select("table#user-grades tr, table.generaltable tbody tr")
        for fila in filas:
            celdas = fila.find_all(["td", "th"])
            if not celdas or idx_email == -1:
                continue
            try:
                raw_email = celdas[idx_email].get_text(strip=True)
            except IndexError:
                continue
            if "@" not in raw_email:
                continue
            email = raw_email.lower()
            nombre = celdas[idx_nombre].get_text(strip=True) if idx_nombre != -1 else "Desconocido"
            if email not in datos:
                datos[email] = {"Nombre": nombre, "Correo": email}
            if idx_total_curso != -1 and len(celdas) > idx_total_curso:
                val = _limpiar(celdas[idx_total_curso].get_text(strip=True))
                datos[email]["Total del Curso"] = val if val != "-" else ""
            if es_especial:
                for idx_col, unidad in mapa_unidades.items():
                    if len(celdas) > idx_col:
                        val = _limpiar(celdas[idx_col].get_text(strip=True))
                        val = val if val != "-" else ""
                        datos[email][f"Calificación {unidad}"] = val
                        if val:
                            datos[email][f"Estado {unidad}"] = "Finalizado (Total)"
    except Exception as e:
        logger.warning(f"Error leyendo tabla general: {e}")

    return datos


# ─────────────────────────────────────────────────────────────────────────────
# SCRAPING PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def scrape_tareas(output_dir: str, codigos=None, base_url: str = None, db=None):
    """
    Scraping de estado de tareas para cada curso activo.
    Prioridad de autenticación: cookie → Selenium → error.

    Args:
        output_dir: carpeta donde guardar los CSVs estado_*.csv
        codigos: lista de códigos AVAC; si None, lee de la BD
        base_url: URL base de AVAC (default env AVAC_BASE_URL)
        db: SQLAlchemy session (para leer CourseConfig)
    """
    from .ingresos_avac import get_active_codigos, get_session_headless, get_session_cookie
    from ..config import settings as _settings

    base_url = base_url or _settings.AVAC_BASE_URL
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Obtener códigos de cursos activos
    if codigos is None:
        codigos = get_active_codigos(db)

    if not codigos:
        logger.warning("No hay códigos de cursos activos para scrapear tareas.")
        return {"codigos_procesados": 0, "errores": []}

    # Autenticación: cookie → Selenium → error
    session_cookie = _settings.AVAC_SESSION_COOKIE
    username = _settings.AVAC_USERNAME
    password = _settings.AVAC_PASSWORD
    totp_secret = _settings.AVAC_TOTP_SECRET
    session = None

    if session_cookie:
        logger.info("🍪 Tareas: modo cookie (MoodleSession directa)")
        try:
            session = get_session_cookie(session_cookie, base_url)
        except RuntimeError as e:
            logger.warning(f"Cookie inválida para tareas: {e}")

    if session is None and username and password:
        logger.info("🔑 Tareas: modo Selenium (credenciales + SSO)")
        session = get_session_headless(username, password, base_url, totp_secret=totp_secret)

    if session is None:
        logger.error("No se pudo autenticar en AVAC para tareas (ni cookie ni Selenium).")
        return {"codigos_procesados": 0, "errores": ["Autenticación fallida"]}

    logger.info(f"Procesando tareas de {len(codigos)} cursos...")
    errores = []
    procesados = 0

    for codigo_curso in codigos:
        try:
            start_time = time.time()

            # A. Buscar ID del curso (formato Moodle 4.x)
            resp = session.get(
                f"{base_url}/course/search.php?areaids=core_course-course&q={codigo_curso}",
                timeout=30,
            )
            soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")
            link_curso = (
                soup.select_one(".coursebox a[href*='view.php?id=']")
                or soup.select_one("a[href*='/course/view.php?id=']")
            )

            if not link_curso:
                logger.warning(f"Curso {codigo_curso} no encontrado en AVAC.")
                continue

            id_curso = parse_qs(urlparse(link_curso["href"]).query).get("id", [None])[0]
            if not id_curso:
                continue

            # B. Datos generales (totales de calificaciones) — una sola request
            url_calif = f"{base_url}/grade/report/index.php?id={id_curso}"
            resp_calif = session.get(url_calif, timeout=30)
            soup_calif = BeautifulSoup(resp_calif.content, "html.parser", from_encoding="utf-8")
            datos_estudiantes = _procesar_reporte_general(soup_calif, es_especial=False)
            logger.info(f"  {codigo_curso}: {len(datos_estudiantes)} alumnos en tabla general")

            # C. Detalles de tareas por unidad
            links_tareas = soup_calif.select("th a[href*='/mod/assign/view.php?id=']")

            tareas_ids_vistos = set()
            for link in links_tareas:
                titulo = link.get_text(strip=True)
                href = link["href"]
                id_tarea = parse_qs(urlparse(href).query).get("id", [None])[0]

                if id_tarea in tareas_ids_vistos:
                    continue

                tit_norm = _normalizar(titulo)
                if any(ex in tit_norm for ex in PALABRAS_EXCLUIDAS):
                    continue

                # Detectar unidad (1-4)
                unidad_detectada = None
                for u, keys in EQUIVALENCIA_UNIDADES.items():
                    if re.search(r"\b(" + "|".join(keys) + r")\b", tit_norm):
                        unidad_detectada = u
                        break
                if not unidad_detectada:
                    continue

                tareas_ids_vistos.add(id_tarea)
                logger.debug(f"    Tarea U{unidad_detectada}: {titulo}")

                # Detalles por alumno desde tabla de grading
                url_g = f"{base_url}/mod/assign/view.php?id={id_tarea}&action=grading&perpage=5000"
                s_grad = BeautifulSoup(session.get(url_g, timeout=60).text, "html.parser")

                for fila in s_grad.select("table.generaltable tbody tr"):
                    if "@" not in fila.get_text():
                        continue

                    def gv(cls_num):
                        c = fila.select_one(f".c{cls_num}")
                        return _limpiar(c.get_text(" ", strip=True)) if c else ""

                    email = gv(1).lower()
                    if not email or "@" not in email:
                        continue

                    if email not in datos_estudiantes:
                        datos_estudiantes[email] = {"Nombre": gv(0), "Correo": email}

                    d = datos_estudiantes[email]
                    u = unidad_detectada
                    d[f"Estado {u}"] = gv(2)
                    d[f"Calificación {u}"] = gv(3)
                    d[f"Última modificación (entrega) {u}"] = gv(4)
                    d[f"Archivos enviados {u}"] = gv(5)
                    d[f"Última modificación (calificación) {u}"] = gv(6)
                    d[f"Comentarios de retroalimentación {u}"] = gv(7)
                    d[f"Anotar PDF {u}"] = gv(8)
                    d[f"Archivos de retroalimentación {u}"] = gv(9)
                    d[f"Calificación final {u}"] = gv(10)

            # D. Calcular totales y guardar CSV
            filas_csv = []
            for email, datos in sorted(datos_estudiantes.items()):
                row = datos.copy()
                entregadas = calificadas = 0
                for u in ["1", "2", "3", "4"]:
                    est = str(row.get(f"Estado {u}", "")).lower()
                    if "enviado" in est or "calificado" in est:
                        entregadas += 1
                    if "calificado" in est:
                        calificadas += 1
                row["Total Entregas"] = entregadas
                row["Total Calificadas"] = calificadas
                filas_csv.append(row)

            df_final = pd.DataFrame(filas_csv)
            df_final["Código Curso"] = codigo_curso
            df_final["Fecha Extracción"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            df_final = df_final.reindex(columns=COLUMNAS_ESTANDAR, fill_value="")

            archivo = output_path / f"estado_{codigo_curso}.csv"
            df_final.to_csv(archivo, index=False, encoding="utf-8-sig", sep=";")

            elapsed = round(time.time() - start_time, 2)
            logger.info(f"  {codigo_curso}: guardado en {elapsed}s ({len(filas_csv)} filas)")
            procesados += 1

        except Exception as e:
            logger.error(f"Error en curso {codigo_curso}: {e}")
            errores.append({"codigo": codigo_curso, "error": str(e)})

    logger.info(f"Tareas scraping: {procesados}/{len(codigos)} procesados, {len(errores)} errores")
    return {"codigos_procesados": procesados, "errores": errores}
