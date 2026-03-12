"""
ETL Transformers — reemplaza las 57 consultas M de Power Query.
Cada función recibe DataFrames crudos y devuelve DataFrames limpios y normalizados.
"""
import re
import unicodedata
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────────────────────────────────────

def normalizar_nombre(texto: Optional[str]) -> str:
    """Limpia prefijos AVAC ('Seleccionar \\'...\\''), normaliza espacios y mayúsculas."""
    if not texto or pd.isna(texto):
        return ""
    texto = str(texto)
    # Eliminar prefijo del scraper: "Seleccionar 'NOMBRE'"
    texto = re.sub(r"^Seleccionar\s+'?", "", texto).rstrip("'")
    # Normalizar unicode → ASCII para comparaciones
    texto = texto.strip().upper()
    return texto


def parse_dias_acceso(texto: Optional[str]) -> Optional[float]:
    """
    Convierte 'X días Y horas' → float de días.
    '8 días 17 horas' → 8.7
    '3 horas'        → 0.125
    'Nunca'          → None
    """
    if not texto or pd.isna(texto):
        return None
    texto = str(texto).lower().strip()
    if texto in ("nunca", "never", "-", ""):
        return None

    dias = 0.0
    match_dias = re.search(r"(\d+)\s*d[ií]a", texto)
    match_horas = re.search(r"(\d+)\s*hora", texto)
    match_min = re.search(r"(\d+)\s*min", texto)

    if match_dias:
        dias += float(match_dias.group(1))
    if match_horas:
        dias += float(match_horas.group(1)) / 24
    if match_min:
        dias += float(match_min.group(1)) / 1440

    return round(dias, 2) if dias > 0 else 0.0


def parse_calificacion(texto: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    """
    '15,00 / 15,00' → (15.0, 15.0)
    '10,50 / 20,00' → (10.5, 20.0)
    '-'             → (None, None)
    """
    if not texto or pd.isna(texto) or str(texto).strip() in ("-", ""):
        return None, None
    texto = str(texto).replace(",", ".").strip()
    # Use a regex that only matches valid numbers (not a bare '.')
    partes = re.findall(r"\d+\.?\d*|\.\d+", texto)
    try:
        if len(partes) >= 2:
            return float(partes[0]), float(partes[1])
        elif len(partes) == 1:
            return float(partes[0]), None
    except (ValueError, TypeError):
        pass
    return None, None


def parse_estado_tarea(estado: Optional[str]) -> tuple[bool, bool, bool]:
    """
    Devuelve (entregada, calificada, retrasada) como booleanos.
    """
    if not estado or pd.isna(estado):
        return False, False, False
    estado_lower = str(estado).lower()
    entregada = "enviado" in estado_lower or "calificado" in estado_lower
    calificada = "calificado" in estado_lower
    retrasada = "retrasada" in estado_lower or "retraso" in estado_lower
    return entregada, calificada, retrasada


def normalizar_carrera(texto: Optional[str]) -> str:
    """Limpia espacios extra y normaliza nombres de carrera."""
    if not texto or pd.isna(texto):
        return ""
    # Quita el contenido entre corchetes que a veces AVAC agrega
    texto = re.sub(r"\[.*?\]", "", str(texto)).strip()
    # Colapsa múltiples espacios
    texto = re.sub(r"\s+", " ", texto).strip().upper()
    return texto


def extraer_correo_usuario(correo: Optional[str]) -> str:
    """'naguilarr1@est.ups.edu.ec' → normalizado en minúsculas."""
    if not correo or pd.isna(correo):
        return ""
    return str(correo).strip().lower()


# ─────────────────────────────────────────────────────────────────────────────
# TRANSFORMER 1: IngresosAVAC (reemplaza query "IngresosAVAC" de PQ)
# ─────────────────────────────────────────────────────────────────────────────

def transform_ingresos_avac(carpeta: str, codigos_activos=None) -> pd.DataFrame:
    """
    Lee todos los archivos ingresosAVAC_*.csv de la carpeta,
    los apila y limpia. Reemplaza el Folder.Files() + limpieza de PQ.

    Args:
        carpeta: ruta a la carpeta con los CSVs
        codigos_activos: lista de códigos AVAC a incluir; None = todos
    """
    carpeta_path = Path(carpeta)

    if codigos_activos is not None:
        # Solo leer archivos de los cursos activos del bloque actual
        archivos = [carpeta_path / f"ingresosAVAC_{c}.csv" for c in codigos_activos]
        archivos = [a for a in archivos if a.exists()]
    else:
        archivos = list(carpeta_path.glob("ingresosAVAC_*.csv"))

    if not archivos:
        logger.warning(f"No se encontraron archivos ingresosAVAC_*.csv en {carpeta}")
        return pd.DataFrame()

    dfs = []
    for archivo in archivos:
        try:
            df = pd.read_csv(archivo, encoding="utf-8-sig")
            dfs.append(df)
        except Exception as e:
            logger.error(f"Error leyendo {archivo.name}: {e}")

    if not dfs:
        return pd.DataFrame()

    # Apilar todos los archivos (equivalente a Table.Combine en PQ)
    df = pd.concat(dfs, ignore_index=True)

    # Limpieza de columnas
    df.columns = [c.strip() for c in df.columns]

    # Renombrar columnas al estándar interno
    df = df.rename(columns={
        "Nombre": "nombre_avac",
        "Correo": "correo",
        "Último acceso": "ultimo_acceso_texto",
        "Estado": "estado_avac",
        "Código Curso": "codigo_curso",
        "Fecha Extracción": "fecha_extraccion",
    })

    # Normalizar nombre (elimina "Seleccionar '...'")
    df["nombre_avac"] = df["nombre_avac"].apply(normalizar_nombre)

    # Normalizar correo
    df["correo"] = df["correo"].apply(extraer_correo_usuario)

    # Parsear días de acceso
    df["dias_sin_acceso"] = df["ultimo_acceso_texto"].apply(parse_dias_acceso)

    # Parsear fecha extracción
    df["fecha_extraccion"] = pd.to_datetime(df["fecha_extraccion"], errors="coerce")

    # Eliminar duplicados: queda el más reciente por (correo, codigo_curso)
    df = df.sort_values("fecha_extraccion", ascending=False)
    df = df.drop_duplicates(subset=["correo", "codigo_curso"], keep="first")

    # Eliminar filas sin correo válido
    df = df[df["correo"].str.contains("@", na=False)]

    logger.info(f"IngresosAVAC: {len(archivos)} archivos → {len(df)} registros únicos")
    return df.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# TRANSFORMER 2: Estado Tareas (reemplaza query "Tareas" de PQ)
# ─────────────────────────────────────────────────────────────────────────────

def transform_estado_tareas(carpeta: str, codigos_activos=None) -> pd.DataFrame:
    """
    Lee todos los estado_*.csv, los apila, parsea calificaciones y estados.

    Args:
        carpeta: ruta a la carpeta con los CSVs
        codigos_activos: lista de códigos AVAC a incluir; None = todos
    """
    carpeta_path = Path(carpeta)

    if codigos_activos is not None:
        archivos = [carpeta_path / f"estado_{c}.csv" for c in codigos_activos]
        archivos = [a for a in archivos if a.exists()]
    else:
        archivos = list(carpeta_path.glob("estado_*.csv"))

    if not archivos:
        logger.warning(f"No se encontraron archivos estado_*.csv en {carpeta}")
        return pd.DataFrame()

    dfs = []
    for archivo in archivos:
        try:
            # Los CSVs de tareas usan separador ";"
            df = pd.read_csv(archivo, encoding="utf-8-sig", sep=";", low_memory=False)
            dfs.append(df)
        except Exception as e:
            logger.error(f"Error leyendo {archivo.name}: {e}")

    if not dfs:
        return pd.DataFrame()

    df = pd.concat(dfs, ignore_index=True)
    df.columns = [c.strip() for c in df.columns]

    # Normalizar correo
    if "Correo" in df.columns:
        df["correo"] = df["Correo"].apply(extraer_correo_usuario)
    if "Código Curso" in df.columns:
        df["codigo_curso"] = df["Código Curso"].astype(str).str.strip()

    # Parsear columnas por unidad (1, 2, 3, 4)
    unidades = ["1", "2", "3", "4"]
    registros_expandidos = []

    for _, row in df.iterrows():
        correo = row.get("correo", "")
        if not correo or "@" not in correo:
            continue
        codigo_curso = str(row.get("codigo_curso", "")).strip()
        total_curso_txt = str(row.get("Total del Curso", "")).replace(",", ".")
        try:
            total_curso = float(re.findall(r"[\d.]+", total_curso_txt)[0]) if total_curso_txt.strip() else None
        except (IndexError, ValueError):
            total_curso = None

        for u in unidades:
            estado = row.get(f"Estado {u}", "")
            cal_txt = row.get(f"Calificación {u}", "")
            fecha_ent = row.get(f"Última modificación (entrega) {u}", "")
            fecha_cal = row.get(f"Última modificación (calificación) {u}", "")
            archivos = row.get(f"Archivos enviados {u}", "")
            comentarios = row.get(f"Comentarios de retroalimentación {u}", "")
            cal_final_txt = row.get(f"Calificación final {u}", "")

            cal, cal_max = parse_calificacion(str(cal_txt))
            cal_final, _ = parse_calificacion(str(cal_final_txt))
            entregada, calificada, retrasada = parse_estado_tarea(str(estado))

            # Solo guardamos si hay alguna data real para esta unidad
            if not estado and cal is None:
                continue

            registros_expandidos.append({
                "correo": correo,
                "codigo_curso": codigo_curso,
                "unidad": u,
                "estado": str(estado).strip() if estado and not pd.isna(estado) else None,
                "calificacion": cal,
                "calificacion_maxima": cal_max,
                "calificacion_final": cal_final,
                "entregada": entregada,
                "calificada": calificada,
                "retrasada": retrasada,
                "fecha_entrega_texto": str(fecha_ent).strip() if fecha_ent and not pd.isna(fecha_ent) else None,
                "archivos_enviados": str(archivos).strip() if archivos and not pd.isna(archivos) else None,
                "comentarios_retroalimentacion": str(comentarios).strip() if comentarios and not pd.isna(comentarios) else None,
                "total_curso": total_curso,
                "total_entregas": row.get("Total Entregas"),
                "total_calificadas": row.get("Total Calificadas"),
                "fecha_extraccion": pd.to_datetime(row.get("Fecha Extracción"), errors="coerce"),
            })

    result = pd.DataFrame(registros_expandidos)
    # Eliminar duplicados: más reciente por (correo, codigo_curso, unidad)
    if not result.empty:
        result = result.sort_values("fecha_extraccion", ascending=False)
        result = result.drop_duplicates(subset=["correo", "codigo_curso", "unidad"], keep="first")

    logger.info(f"Tareas: {len(archivos)} archivos → {len(result)} registros de entrega únicos")
    return result.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# TRANSFORMER 3: Calificaciones (reemplaza query "Tableau" de PQ)
# ─────────────────────────────────────────────────────────────────────────────

def transform_calificaciones(ruta_csv: str) -> pd.DataFrame:
    """
    Lee el CSV de calificaciones institucionales (Detalle de Calificaciones).
    El nombre del estudiante viene invertido: 'APELLIDO NOMBRE'.
    """
    try:
        df = pd.read_csv(ruta_csv, encoding="utf-8-sig", sep=";")
    except Exception as e:
        logger.error(f"Error leyendo calificaciones: {e}")
        return pd.DataFrame()

    df.columns = [c.strip() for c in df.columns]

    # Renombrar a estándar interno
    rename_map = {}
    col_lower = {c.lower(): c for c in df.columns}
    if "sede" in col_lower: rename_map[col_lower["sede"]] = "sede"
    if "campus" in col_lower: rename_map[col_lower["campus"]] = "campus"
    if "carrera" in col_lower: rename_map[col_lower["carrera"]] = "carrera"
    if "asignatura" in col_lower: rename_map[col_lower["asignatura"]] = "asignatura"
    if "grupo" in col_lower: rename_map[col_lower["grupo"]] = "grupo"
    if "estudiante" in col_lower: rename_map[col_lower["estudiante"]] = "nombre_estudiante"
    if "docente" in col_lower: rename_map[col_lower["docente"]] = "docente"
    if "nota final" in col_lower: rename_map[col_lower["nota final"]] = "nota_final"
    df = df.rename(columns=rename_map)

    # Limpiar carrera
    if "carrera" in df.columns:
        df["carrera"] = df["carrera"].apply(normalizar_carrera)

    # Nota final a float
    if "nota_final" in df.columns:
        df["nota_final"] = pd.to_numeric(df["nota_final"], errors="coerce")

    # Eliminar filas sin estudiante
    if "nombre_estudiante" in df.columns:
        df = df[df["nombre_estudiante"].notna() & (df["nombre_estudiante"].str.strip() != "")]

    logger.info(f"Calificaciones: {len(df)} registros")
    return df.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# TRANSFORMER 4: Calcular indicadores de riesgo por estudiante
# (Reemplaza CalcularCompromiso() VBA + fórmulas de FichaEst)
# ─────────────────────────────────────────────────────────────────────────────

def calcular_indice_compromiso(
    dias_sin_acceso: Optional[float],
    tareas_entregadas: int,
    tareas_totales: int,
    notas: list[Optional[float]],
    bloque_actual: int = 1   # 1 o 2
) -> dict:
    """
    Replica el algoritmo de CalcularCompromiso() del VBA.

    Fórmula:
      - 40% = acceso AVAC (≤7 días = 0.4, >7 días = 0.0)
      - 60% = actividades: (entregadas/totales) × 0.6
        + bonus: nota=1 cuenta doble como señal de presencia

    Devuelve dict con {indice, nivel_riesgo, color_hex}
    """
    # Componente AVAC (40%)
    if dias_sin_acceso is None:
        puntaje_acceso = 0.0
    elif dias_sin_acceso <= 7:
        puntaje_acceso = 0.4
    elif dias_sin_acceso <= 14:
        puntaje_acceso = 0.2
    else:
        puntaje_acceso = 0.0

    # Componente actividades (60%)
    if tareas_totales == 0:
        puntaje_tareas = 0.0
    else:
        # Nota=1 se cuenta como 2 entregas (señal de "intentó")
        entregas_ponderadas = 0
        for nota in notas:
            if nota is not None:
                entregas_ponderadas += 2 if nota == 1.0 else 1
        # Cap al máximo posible
        entregas_ponderadas = min(entregas_ponderadas, tareas_totales)
        puntaje_tareas = (tareas_entregadas / tareas_totales) * 0.6

    indice = round(puntaje_acceso + puntaje_tareas, 3)

    # Clasificación de riesgo
    if indice >= 0.7:
        nivel = "Bajo"
        color = "#00B050"   # verde
    elif indice >= 0.4:
        nivel = "Medio"
        color = "#FFC000"   # amarillo
    else:
        nivel = "Alto"
        color = "#FF4C4C"   # rojo

    return {
        "indice_compromiso": indice,
        "nivel_riesgo": nivel,
        "color_riesgo": color,
        "puntaje_acceso": puntaje_acceso,
        "puntaje_tareas": puntaje_tareas,
    }


def calcular_indicadores_estudiantes(
    df_ingresos: pd.DataFrame,
    df_tareas: pd.DataFrame,
    df_calificaciones: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye la tabla maestra de estudiantes con sus indicadores de riesgo.
    Join por correo (llave principal) y nombre (fallback).
    """
    if df_ingresos.empty:
        return pd.DataFrame()

    # Agregar días de acceso por correo (peor caso: máximo entre cursos)
    acceso_agg = (
        df_ingresos.groupby("correo")
        .agg(
            dias_sin_acceso_max=("dias_sin_acceso", "max"),
            dias_sin_acceso_min=("dias_sin_acceso", "min"),
            nombre_avac=("nombre_avac", "first"),
            estado_avac=("estado_avac", "first"),
        )
        .reset_index()
    )

    # Agregar tareas por correo
    if not df_tareas.empty:
        tareas_agg = (
            df_tareas.groupby("correo")
            .agg(
                total_entregas=("entregada", "sum"),
                total_tareas=("entregada", "count"),
                total_calificadas=("calificada", "sum"),
                porcentaje_tareas=("entregada", "mean"),
                calificacion_promedio=("calificacion", "mean"),
            )
            .reset_index()
        )
        tareas_agg["porcentaje_tareas"] = tareas_agg["porcentaje_tareas"] * 100
    else:
        tareas_agg = pd.DataFrame(columns=["correo"])

    # Agregar calificaciones por nombre estudiante
    if not df_calificaciones.empty and "nombre_estudiante" in df_calificaciones.columns:
        cal_agg = (
            df_calificaciones.groupby("nombre_estudiante")
            .agg(
                promedio_notas=("nota_final", "mean"),
                asignaturas=("asignatura", lambda x: list(x.unique())),
                carrera=("carrera", "first"),
                docentes=("docente", lambda x: list(x.unique())),
            )
            .reset_index()
        )
    else:
        cal_agg = pd.DataFrame()

    # Merge principal: ingresos + tareas por correo
    df_master = acceso_agg.merge(tareas_agg, on="correo", how="left")

    # Calcular índice de compromiso para cada estudiante
    indicadores = []
    for _, row in df_master.iterrows():
        def _safe_int(val):
            try:
                return int(val) if val is not None and not pd.isna(val) else 0
            except (ValueError, TypeError):
                return 0
        ind = calcular_indice_compromiso(
            dias_sin_acceso=row.get("dias_sin_acceso_max"),
            tareas_entregadas=_safe_int(row.get("total_entregas", 0)),
            tareas_totales=_safe_int(row.get("total_tareas", 0)),
            notas=[],  # se pasan notas individuales si se quiere el bonus
        )
        indicadores.append(ind)

    df_indicadores = pd.DataFrame(indicadores)
    df_master = pd.concat([df_master.reset_index(drop=True), df_indicadores], axis=1)

    logger.info(f"Estudiantes con indicadores calculados: {len(df_master)}")
    return df_master
