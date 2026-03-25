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
    # Colapsar espacios múltiples (el reporte a veces tiene dobles espacios)
    texto = re.sub(r"\s+", " ", texto)
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


def extraer_grupo_numero(nombre_grupo: Optional[str]) -> Optional[str]:
    """
    Extrae el número de grupo/sección del campo NOMBRE_GRUPO del reporte.
    Soporta grupos de múltiples dígitos (corrección al bug del Excel que solo
    tomaba 1 carácter con MID(...,FIND("- ",...)+2,1)).

    Ejemplos:
      'Grupo - 3'                              → '3'
      'GRUPO - 5'                              → '5'
      'Grupo - 16 (Educacion Intercultural…)'  → '16'  ← bug en Excel: devolvía '1'
      'Grupo - 1 (Educación Intercultural…)'   → '1'
      'Eib 13041 Latacunga'                    → None   (no sigue el patrón)
      None / ''                                → None
    """
    if not nombre_grupo or pd.isna(nombre_grupo):
        return None
    # re.IGNORECASE cubre 'Grupo', 'GRUPO', 'grupo'
    m = re.search(r'grupo\s*-\s*(\d+)', str(nombre_grupo), re.IGNORECASE)
    return m.group(1) if m else None


def parse_nivel_academico(texto: Optional[str]) -> Optional[int]:
    """
    Convierte el campo NIVEL del formulario DatosEspecificos a número entero.

    Formatos encontrados en datos reales (P67):
      '1er nivel'  → 1
      '3er nivel'  → 3
      '5to nivel'  → 5
      '7mo nivel'  → 7
      5            → 5  (valor numérico directo del Excel)
      'Oyente condicionado' → None

    También soporta nombres completos: 'Primer nivel' → 1, 'Tercer nivel' → 3, etc.
    """
    if texto is None or (isinstance(texto, float) and pd.isna(texto)):
        return None

    # Valor numérico directo (algunas celdas Excel ya guardan el número)
    if isinstance(texto, (int, float)):
        try:
            v = int(texto)
            return v if 1 <= v <= 10 else None
        except (ValueError, TypeError):
            return None

    t = str(texto).strip().lower()

    # Número embebido: '5to nivel', '3er nivel', '1er nivel', '7mo nivel'
    # Sin \b para que capture el dígito aunque esté pegado al ordinal ('5to', '3er')
    m = re.search(r'(\d+)', t)
    if m:
        v = int(m.group(1))
        return v if 1 <= v <= 10 else None

    # Ordinales en texto: 'primer', 'segundo', etc.
    ordinals = [
        ('primer',   1), ('segundo',  2), ('tercer',   3), ('cuarto',   4),
        ('quinto',   5), ('sexto',    6), ('s[eé]ptim', 7), ('octavo',   8),
        ('noveno',   9), ('d[eé]cim', 10),
    ]
    for pattern, num in ordinals:
        if re.search(pattern, t):
            return num

    return None


def normalizar_texto_simple(texto: Optional[str]) -> Optional[str]:
    """
    Normaliza texto en Title Case, elimina espacios extra y None/NaN.
    Útil para campos de residencia (Provincia, Ciudad, etc.).
    """
    if texto is None or (isinstance(texto, float) and pd.isna(texto)):
        return None
    s = str(texto).strip()
    if not s or s.lower() in ("nan", "none", "-"):
        return None
    # Title case preservando acentos
    return " ".join(w.capitalize() for w in s.split())


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
    if "numero_repitencias" in col_lower: rename_map[col_lower["numero_repitencias"]] = "numero_repitencias"
    if "numero repitencias" in col_lower: rename_map[col_lower["numero repitencias"]] = "numero_repitencias"
    if "nivel" in col_lower: rename_map[col_lower["nivel"]] = "nivel"
    if "nombre_grupo" in col_lower: rename_map[col_lower["nombre_grupo"]] = "nombre_grupo"
    if "nombre grupo" in col_lower: rename_map[col_lower["nombre grupo"]] = "nombre_grupo"
    df = df.rename(columns=rename_map)

    # Limpiar carrera
    if "carrera" in df.columns:
        df["carrera"] = df["carrera"].apply(normalizar_carrera)

    # Nota final a float
    if "nota_final" in df.columns:
        df["nota_final"] = pd.to_numeric(df["nota_final"], errors="coerce")

    # Número de repitencias a int
    if "numero_repitencias" in df.columns:
        df["numero_repitencias"] = pd.to_numeric(df["numero_repitencias"], errors="coerce").astype("Int64")

    # Nivel académico de la asignatura a int
    if "nivel" in df.columns:
        df["nivel"] = pd.to_numeric(df["nivel"], errors="coerce").astype("Int64")

    # NOMBRE_GRUPO → extraer número de grupo para estandarizar
    if "nombre_grupo" in df.columns:
        extracted = df["nombre_grupo"].apply(extraer_grupo_numero)
        if "grupo" in df.columns:
            df["grupo"] = extracted.fillna(df["grupo"])
        else:
            df["grupo"] = extracted

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
    bloque_actual: int = 1,   # 1 o 2
    promedio_calificaciones: Optional[float] = None,
    estado_matricula: Optional[str] = None,
) -> dict:
    """
    Modelo de riesgo ponderado multinivel (Framework Capa 5) — v2 MEJORADO.

    Mejoras respecto a v1:
      P1-FIX: Función de acceso AVAC continua (exponencial decreciente, no escalonada)
      P2-FIX: Rendimiento con gradiente continuo usando función sigmoide
      P3-FIX: Sin datos = señal de alerta proporcional (no neutral)
      P4-FIX: Umbrales de clasificación ajustados (0.65 y 0.35 para mayor sensibilidad)

    Score compuesto con 4 dimensiones:
      - 30% = acceso AVAC (engagement con la plataforma)
      - 30% = actividades entregadas (cumplimiento)
      - 25% = rendimiento académico (calificaciones)
      - 15% = factor administrativo (estado matrícula)

    Devuelve dict con {indice, nivel_riesgo, color_hex, componentes}
    """
    import math

    # ── Componente AVAC (30%) — función continua decreciente ──
    # [P1-FIX] Exponencial decreciente: f(d) = 0.30 * exp(-d/10)
    # d=0 → 0.30 (máximo), d=7 → 0.15, d=14 → 0.07, d=30 → 0.01, d>40 → ~0
    if dias_sin_acceso is None:
        # [P3-FIX] Sin datos de acceso = señal de alerta (no 0 absoluto)
        puntaje_acceso = 0.03  # peor que 30 días, mejor que nunca
    else:
        puntaje_acceso = round(0.30 * math.exp(-max(dias_sin_acceso, 0) / 10), 4)

    # ── Componente actividades (30%) — lineal proporcional ──
    if tareas_totales == 0:
        # [P3-FIX] Sin tareas registradas = señal moderada de alerta
        puntaje_tareas = 0.05
    else:
        puntaje_tareas = round((tareas_entregadas / tareas_totales) * 0.30, 4)

    # ── Componente rendimiento académico (25%) — sigmoide continua ──
    # [P2-FIX] Sigmoide centrada en 70 (umbral de aprobación): f(x) = 0.25 / (1 + exp(-0.08*(x-70)))
    # Nota 50 → 0.04, Nota 60 → 0.08, Nota 70 → 0.125, Nota 80 → 0.19, Nota 90 → 0.23
    # Gradiente suave sin "agujeros" entre rangos
    if promedio_calificaciones is not None and promedio_calificaciones > 0:
        puntaje_rendimiento = round(0.25 / (1 + math.exp(-0.08 * (promedio_calificaciones - 70))), 4)
    else:
        # [P3-FIX] Sin calificaciones = señal de alerta proporcional
        puntaje_rendimiento = 0.04  # equivalente a ~nota 50

    # ── Componente administrativo (15%) ──
    if estado_matricula and "matriculad" in str(estado_matricula).lower():
        puntaje_admin = 0.15
    elif estado_matricula:
        puntaje_admin = 0.05  # estado irregular pero presente
    else:
        # [P3-FIX] Sin datos de matrícula = señal de alerta
        puntaje_admin = 0.03

    indice = round(puntaje_acceso + puntaje_tareas + puntaje_rendimiento + puntaje_admin, 3)

    # [P4-FIX] Clasificación con umbrales ajustados para mayor sensibilidad
    # 0.65 y 0.35 en vez de 0.7 y 0.4 — detecta riesgo antes
    if indice >= 0.65:
        nivel = "Bajo"
        color = "#00B050"   # verde
    elif indice >= 0.35:
        nivel = "Medio"
        color = "#FFC000"   # amarillo
    else:
        nivel = "Alto"
        color = "#FF4C4C"   # rojo

    return {
        "indice_compromiso": indice,
        "nivel_riesgo": nivel,
        "color_riesgo": color,
        "puntaje_acceso": round(puntaje_acceso, 4),
        "puntaje_tareas": round(puntaje_tareas, 4),
        "puntaje_rendimiento": round(puntaje_rendimiento, 4),
        "puntaje_admin": round(puntaje_admin, 4),
    }


# ─────────────────────────────────────────────────────────────────────────────
# TRANSFORMER 5: Datos personales de estudiantes (reporte.xlsx)
# Reemplaza el origen "DataPersonales" del Power Query
# ─────────────────────────────────────────────────────────────────────────────

def transform_personales(carpeta_o_archivos) -> pd.DataFrame:
    """
    Lee todos los archivos *_reporte.xlsx que contengan datos personales
    (cedula, teléfono, correo, etc.) y devuelve una fila única por estudiante.

    La llave de cruce es CORREO_INSTITUCIONAL, que coincide con el campo
    'correo' en IngresosAVAC, TableauHistorico y Tareas.

    Args:
        carpeta_o_archivos: ruta a la carpeta con los .xlsx  o  lista de rutas
    """
    archivos: list[Path] = []
    if isinstance(carpeta_o_archivos, (str, Path)):
        carpeta = Path(carpeta_o_archivos)
        if carpeta.is_dir():
            archivos = sorted(carpeta.glob("*_reporte.xlsx"))
        else:
            logger.warning(f"Carpeta de reportes no encontrada: {carpeta}")
    else:
        archivos = [Path(f) for f in carpeta_o_archivos]

    if not archivos:
        logger.warning("transform_personales: no se encontraron archivos *_reporte.xlsx")
        return pd.DataFrame()

    dfs = []
    for archivo in archivos:
        try:
            df = pd.read_excel(
                archivo,
                engine="openpyxl",
                dtype={"CEDULA": str, "TELEFONO": str, "CELULAR": str},
            )
            df["_fuente"] = archivo.name
            dfs.append(df)
            logger.info(f"  Reporte leído: {archivo.name} ({len(df)} filas)")
        except Exception as e:
            logger.error(f"Error leyendo {archivo.name}: {e}")

    if not dfs:
        return pd.DataFrame()

    df = pd.concat(dfs, ignore_index=True)
    # Normalizar encabezados
    df.columns = [c.strip().upper() for c in df.columns]

    # ── Correo institucional (llave de cruce) ─────────────────────────────────
    if "CORREO_INSTITUCIONAL" not in df.columns:
        logger.error("transform_personales: columna CORREO_INSTITUCIONAL no encontrada")
        return pd.DataFrame()
    df["correo_institucional"] = df["CORREO_INSTITUCIONAL"].apply(extraer_correo_usuario)
    # Descartar filas sin correo válido
    df = df[df["correo_institucional"].str.contains("@", na=False)]

    # ── Cédula ────────────────────────────────────────────────────────────────
    def _limpiar_cedula(val) -> Optional[str]:
        if val is None or pd.isna(val):
            return None
        s = str(val).strip().split(".")[0]  # quitar decimales (Excel los añade)
        return s if s.isdigit() else None

    if "CEDULA" in df.columns:
        df["cedula"] = df["CEDULA"].apply(_limpiar_cedula)
    else:
        df["cedula"] = None

    # ── Nombre ────────────────────────────────────────────────────────────────
    if "ESTUDIANTES" in df.columns:
        df["nombre"] = df["ESTUDIANTES"].apply(normalizar_nombre)
    else:
        df["nombre"] = None

    # ── Correo personal ───────────────────────────────────────────────────────
    if "CORREO_PERSONAL" in df.columns:
        df["correo"] = df["CORREO_PERSONAL"].apply(extraer_correo_usuario)
    else:
        df["correo"] = None

    # ── Teléfono (prefiere CELULAR, fallback TELEFONO) ────────────────────────
    def _telefono(row) -> Optional[str]:
        for col in ("CELULAR", "TELEFONO"):
            val = row.get(col)
            if val is not None and not pd.isna(val):
                s = str(val).strip().split(".")[0]
                if s.isdigit() and int(s) > 0:
                    return s
        return None

    df["telefono"] = df.apply(_telefono, axis=1)

    # ── Carrera ───────────────────────────────────────────────────────────────
    if "CARRERA" in df.columns:
        df["carrera"] = df["CARRERA"].apply(normalizar_carrera)
    else:
        df["carrera"] = None

    # ── Estado matrícula: combina PAGADO + ESTADO_MATRICULADOS ────────────────
    def _estado_matricula(row) -> Optional[str]:
        pagado = str(row.get("PAGADO", "")).strip().upper()
        estado = str(row.get("ESTADO_MATRICULADOS", "")).strip()
        if pagado == "SI":
            return f"Matriculado - {estado}".rstrip("- ") if estado and estado.upper() != "NAN" else "Matriculado"
        elif pagado == "NO":
            return "Sin matrícula"
        return None

    if "PAGADO" in df.columns:
        df["estado_matricula"] = df.apply(_estado_matricula, axis=1)
    else:
        df["estado_matricula"] = None

    # ── Residencia (disponible solo en 2505060014_reporte.xlsx y similares) ───
    # Columnas: PAIS_DOM, PROVINCIA_DOM, CIUDAD_DOM, BARRIO
    for src_col, dest_col in [
        ("PAIS_DOM",      "pais"),
        ("PROVINCIA_DOM", "provincia"),
        ("CIUDAD_DOM",    "ciudad"),
        ("BARRIO",        "barrio"),
    ]:
        if src_col in df.columns:
            df[dest_col] = df[src_col].apply(normalizar_texto_simple)
        else:
            df[dest_col] = None

    # ── WhatsApp (si el reporte lo incluye) ───────────────────────────────────
    if "WHATSAPP_ESTUDIANTE" in df.columns:
        def _whatsapp(val) -> Optional[str]:
            if val is None or pd.isna(val):
                return None
            s = str(val).strip().split(".")[0]
            return s if s.isdigit() and int(s) > 0 else None
        df["whatsapp"] = df["WHATSAPP_ESTUDIANTE"].apply(_whatsapp)
    else:
        df["whatsapp"] = None

    # ── Datos demográficos (presentes en 2505060014_reporte.xlsx) ──────────────
    for src_col, dest_col in [
        ("FECHA_NACIMIENTO",         "fecha_nacimiento"),
        ("AUTOIDENTIFICACION_ETNICA", "autoidentificacion_etnica"),
        ("GENERO",                   "genero"),
    ]:
        if src_col in df.columns:
            if dest_col == "fecha_nacimiento":
                df[dest_col] = pd.to_datetime(df[src_col], errors="coerce")
            else:
                df[dest_col] = df[src_col].apply(
                    lambda v: normalizar_texto_simple(v) if pd.notna(v) else None
                )
        else:
            df[dest_col] = None

    # ── Grupo académico (NOMBRE_GRUPO → número) ─────────────────────────────
    if "NOMBRE_GRUPO" in df.columns:
        df["_grupo_num"] = df["NOMBRE_GRUPO"].apply(extraer_grupo_numero)
        # Mayoría por estudiante (puede tener grupos distintos por materia)
        _grupo_agg = (
            df.dropna(subset=["_grupo_num"])
            .groupby("correo_institucional")["_grupo_num"]
            .agg(lambda s: s.mode().iloc[0] if not s.mode().empty else s.iloc[0])
        )
        df["grupo"] = df["correo_institucional"].map(_grupo_agg)
    else:
        df["grupo"] = None

    # ── Nivel académico (NIVEL → moda por estudiante) ─────────────────────
    # El reporte tiene una fila por asignatura; NIVEL puede variar por materia.
    # Tomamos la moda (nivel más frecuente) como nivel_academico del estudiante.
    if "NIVEL" in df.columns:
        df["_nivel_raw"] = pd.to_numeric(df["NIVEL"], errors="coerce").astype("Int64")
        _nivel_agg = (
            df.dropna(subset=["_nivel_raw"])
            .groupby("correo_institucional")["_nivel_raw"]
            .agg(lambda s: s.mode().iloc[0] if not s.mode().empty else s.iloc[0])
        )
        df["nivel_academico"] = df["correo_institucional"].map(_nivel_agg)
    else:
        df["nivel_academico"] = None

    # ── Deduplicar: una fila por estudiante ───────────────────────────────────
    # Usamos groupby().first() en vez de drop_duplicates(keep="first") porque
    # .first() toma el primer valor NO-NULO de cada columna, coalesce-ando datos
    # de múltiples archivos de reporte que pueden tener columnas distintas.
    # Esto es crucial cuando un archivo tiene FECHA_NACIMIENTO/GENERO/ETNICA
    # y otro no: queremos conservar los valores existentes sin importar el orden
    # de lectura de archivos (que varía entre OS — glob no garantiza orden).
    df = df.groupby("correo_institucional", sort=False).first().reset_index()

    # ── Seleccionar solo columnas necesarias para el Student model ────────────
    cols_salida = [
        "correo_institucional",
        "cedula",
        "nombre",
        "correo",
        "telefono",
        "whatsapp",
        "carrera",
        "estado_matricula",
        "pais",
        "provincia",
        "ciudad",
        "barrio",
        # Nuevas del reporte institucional:
        "fecha_nacimiento",
        "genero",
        "autoidentificacion_etnica",
        "grupo",
        "nivel_academico",
    ]
    result = df[[c for c in cols_salida if c in df.columns]].copy()

    logger.info(f"Personales: {len(archivos)} archivo(s) → {len(result)} estudiantes únicos")
    return result.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# TRANSFORMER 5b: Cursos desde reporte.xlsx (CODIGO_GRUPO → CourseConfig)
# Extrae la lista única de cursos AVAC para auto-poblar course_configs
# ─────────────────────────────────────────────────────────────────────────────

def extract_courses_from_reporte(carpeta_o_archivos) -> pd.DataFrame:
    """
    Lee los archivos *_reporte.xlsx y extrae la lista única de cursos.
    Columnas esperadas: CODIGO_GRUPO, NOMBRE_ASIGNATURA, CARRERA, NIVEL,
                        NOMBRE_GRUPO, DOCENTES (o DOCENTE).

    Retorna DataFrame con columnas:
        codigo_avac, nombre_asignatura, carrera, nivel, grupo, docente
    """
    archivos: list[Path] = []
    if isinstance(carpeta_o_archivos, (str, Path)):
        carpeta = Path(carpeta_o_archivos)
        if carpeta.is_dir():
            archivos = sorted(carpeta.glob("*_reporte.xlsx"))
    else:
        archivos = [Path(f) for f in carpeta_o_archivos]

    if not archivos:
        return pd.DataFrame()

    dfs = []
    for archivo in archivos:
        try:
            df = pd.read_excel(archivo, engine="openpyxl")
            df.columns = [c.strip().upper() for c in df.columns]
            dfs.append(df)
        except Exception as e:
            logger.error(f"extract_courses_from_reporte: error leyendo {archivo}: {e}")

    if not dfs:
        return pd.DataFrame()

    df = pd.concat(dfs, ignore_index=True)

    if "CODIGO_GRUPO" not in df.columns:
        logger.warning("extract_courses_from_reporte: CODIGO_GRUPO no encontrado en reporte")
        return pd.DataFrame()

    # Limpiar código AVAC
    df["codigo_avac"] = df["CODIGO_GRUPO"].astype(str).str.strip()
    df = df[df["codigo_avac"].str.isdigit()]  # solo códigos numéricos válidos

    # Extraer campos del curso
    if "NOMBRE_ASIGNATURA" in df.columns:
        df["nombre_asignatura"] = df["NOMBRE_ASIGNATURA"].astype(str).str.strip()
    elif "ASIGNATURA" in df.columns:
        df["nombre_asignatura"] = df["ASIGNATURA"].astype(str).str.strip()
    else:
        df["nombre_asignatura"] = None

    if "CARRERA" in df.columns:
        df["carrera"] = df["CARRERA"].apply(normalizar_carrera)
    else:
        df["carrera"] = None

    if "NIVEL" in df.columns:
        df["nivel"] = pd.to_numeric(df["NIVEL"], errors="coerce").astype("Int64")
    else:
        df["nivel"] = None

    if "NOMBRE_GRUPO" in df.columns:
        df["grupo"] = df["NOMBRE_GRUPO"].apply(extraer_grupo_numero)
    else:
        df["grupo"] = None

    # Docente: puede ser DOCENTES o DOCENTE
    doc_col = next((c for c in df.columns if c in ("DOCENTES", "DOCENTE")), None)
    if doc_col:
        df["docente"] = df[doc_col].astype(str).str.strip()
        df.loc[df["docente"].str.lower().isin(["nan", "none", ""]), "docente"] = None
    else:
        df["docente"] = None

    # Deduplicar: un registro por codigo_avac
    # Tomar first() de los demás campos (son iguales para un mismo código)
    cols = ["codigo_avac", "nombre_asignatura", "carrera", "nivel", "grupo", "docente"]
    result = df[cols].drop_duplicates(subset=["codigo_avac"]).reset_index(drop=True)

    logger.info(f"extract_courses_from_reporte: {len(result)} cursos únicos extraídos")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# TRANSFORMER 5c: Resumen_General (calificación docente)
# Fuente: scraping AVAC → Resumen_General*.csv
# Aporta: curso, actividad, si fue calificada, puntualidad de retroalimentación
# ─────────────────────────────────────────────────────────────────────────────

def transform_resumen_general(carpeta_o_archivos) -> pd.DataFrame:
    """
    Lee archivos Resumen_General*.csv del scraping AVAC.
    Retorna DataFrame con estado de calificación por actividad y curso.

    Columnas esperadas del CSV (pueden variar por versión del scraping):
        codigo_curso, nombre_curso, actividad, tipo_actividad,
        calificada (Sí/No), fecha_limite, fecha_calificacion, docente
    """
    archivos: list[Path] = []
    if isinstance(carpeta_o_archivos, (str, Path)):
        carpeta = Path(carpeta_o_archivos)
        if carpeta.is_dir():
            # Buscar en Reportes/ y en raíz de data/
            archivos = sorted(carpeta.glob("Resumen_General*.csv"))
        elif carpeta.is_file() and carpeta.name.lower().startswith("resumen_general"):
            archivos = [carpeta]
    else:
        archivos = [Path(f) for f in carpeta_o_archivos]

    if not archivos:
        logger.info("transform_resumen_general: no se encontraron archivos Resumen_General*.csv")
        return pd.DataFrame()

    dfs = []
    for archivo in archivos:
        try:
            df = pd.read_csv(archivo, encoding="utf-8-sig")
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
            df["_fuente"] = archivo.name
            dfs.append(df)
            logger.info(f"  Resumen_General leído: {archivo.name} ({len(df)} filas)")
        except Exception as e:
            logger.error(f"Error leyendo Resumen_General {archivo.name}: {e}")

    if not dfs:
        return pd.DataFrame()

    df = pd.concat(dfs, ignore_index=True)
    logger.info(f"transform_resumen_general: {len(df)} registros de calificación docente")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# TRANSFORMER 6: DatosEspecificos EIB (Microsoft Forms)
# Fuente: formulario de inicio de semestre → "DatosEspecificos EIB (P67).xlsx"
# Aporta: nivel académico, sede, residencia granular, whatsapp, etnia
# ─────────────────────────────────────────────────────────────────────────────

def transform_datos_especificos(carpeta_o_archivos) -> pd.DataFrame:
    """
    Lee el/los archivos DatosEspecificos*.xlsx (respuestas del formulario EIB).
    Hoja de datos: 'Sheet1'.
    Llave de cruce: 'Correo Institucional' → correo_institucional.

    Columnas de salida:
      correo_institucional, cedula, nombre, whatsapp,
      nivel_academico (int 1–8),
      sede (Centro de apoyo normalizado),
      pais, provincia, ciudad (Cantón), parroquia, barrio

    Args:
        carpeta_o_archivos: ruta a la carpeta con los .xlsx  o  lista de rutas
    """
    archivos: list[Path] = []
    if isinstance(carpeta_o_archivos, (str, Path)):
        carpeta = Path(carpeta_o_archivos)
        if carpeta.is_dir():
            archivos = list(carpeta.glob("*.xlsx"))
        else:
            logger.warning(f"Carpeta DatosEspecificos no encontrada: {carpeta}")
    else:
        archivos = [Path(f) for f in carpeta_o_archivos]

    if not archivos:
        logger.warning("transform_datos_especificos: no se encontraron archivos .xlsx")
        return pd.DataFrame()

    dfs = []
    for archivo in archivos:
        try:
            # La hoja de datos se llama 'Sheet1'; si no existe, leer la primera
            xl = pd.ExcelFile(archivo, engine="openpyxl")
            sheet = "Sheet1" if "Sheet1" in xl.sheet_names else xl.sheet_names[0]
            df = xl.parse(sheet)
            df["_fuente"] = archivo.name
            dfs.append(df)
            logger.info(f"  DatosEspecificos leído: {archivo.name} ({len(df)} filas)")
        except Exception as e:
            logger.error(f"Error leyendo {archivo.name}: {e}")

    if not dfs:
        return pd.DataFrame()

    df = pd.concat(dfs, ignore_index=True)

    # ── Correo institucional (llave de cruce) ─────────────────────────────────
    col_correo = next(
        (c for c in df.columns if "correo institucional" in c.lower()),
        None
    )
    if not col_correo:
        logger.error("transform_datos_especificos: columna 'Correo Institucional' no encontrada")
        return pd.DataFrame()
    df["correo_institucional"] = df[col_correo].apply(extraer_correo_usuario)
    df = df[df["correo_institucional"].str.contains("@", na=False)]

    # ── Cédula ────────────────────────────────────────────────────────────────
    col_cedula = next((c for c in df.columns if "cédula" in c.lower() or "cedula" in c.lower()), None)
    if col_cedula:
        def _limpiar_cedula(val) -> Optional[str]:
            if val is None or pd.isna(val):
                return None
            s = str(val).strip().split(".")[0]
            return s if s.isdigit() else None
        df["cedula"] = df[col_cedula].apply(_limpiar_cedula)
    else:
        df["cedula"] = None

    # ── Nombre (Apellidos + Nombres) ──────────────────────────────────────────
    col_apellidos = next((c for c in df.columns if c.strip().lower() == "apellidos"), None)
    col_nombres   = next((c for c in df.columns if c.strip().lower() == "nombres"), None)
    if col_apellidos and col_nombres:
        df["nombre"] = (
            df[col_apellidos].fillna("").apply(str).str.strip()
            + " "
            + df[col_nombres].fillna("").apply(str).str.strip()
        ).str.strip().str.upper()
        df["nombre"] = df["nombre"].replace("", None)
    else:
        df["nombre"] = None

    # ── WhatsApp ──────────────────────────────────────────────────────────────
    col_wp = next((c for c in df.columns if "whatsapp" in c.lower()), None)
    if col_wp:
        def _to_whatsapp(val) -> Optional[str]:
            if val is None or pd.isna(val):
                return None
            s = str(val).strip().split(".")[0]
            return s if s.isdigit() and int(s) > 0 else None
        df["whatsapp"] = df[col_wp].apply(_to_whatsapp)
    else:
        df["whatsapp"] = None

    # ── Nivel académico ───────────────────────────────────────────────────────
    col_nivel = next(
        (c for c in df.columns if c.strip().upper() == "NIVEL"),
        None
    )
    if col_nivel:
        df["nivel_academico"] = df[col_nivel].apply(parse_nivel_academico)
    else:
        df["nivel_academico"] = None

    # ── Sede / Centro de apoyo ────────────────────────────────────────────────
    SEDES_VALIDAS = {"cayambe", "amazonia norte", "amazonía norte", "latacunga",
                     "otavalo", "riobamba", "cuenca", "quito"}

    def _normalizar_sede(texto):
        val = normalizar_texto_simple(texto)
        if val is None:
            return None
        # Descartar valores numéricos o demasiado cortos (errores de entrada)
        if val.replace(" ", "").isdigit() or len(val) < 3:
            return None
        # Normalizar variantes conocidas
        low = val.lower().strip()
        if "amazon" in low:
            return "Amazonía Norte"
        # Validar contra sedes conocidas (warn pero no descartar desconocidas)
        return val
    col_centro = next(
        (c for c in df.columns if "centro de apoyo" in c.lower()),
        None
    )
    if col_centro:
        df["sede"] = df[col_centro].apply(_normalizar_sede)
    else:
        df["sede"] = None

    # ── Residencia ────────────────────────────────────────────────────────────
    for src_col_pattern, dest_col in [
        ("país",      "pais"),
        ("provincia", "provincia"),
        ("cantón",    "ciudad"),      # Cantón → ciudad (más granular que CIUDAD_DOM)
        ("parroquia", "parroquia"),
        ("barrio",    "barrio"),
    ]:
        src_col = next(
            (c for c in df.columns if src_col_pattern in c.lower()),
            None
        )
        if src_col:
            df[dest_col] = df[src_col].apply(normalizar_texto_simple)
        else:
            df[dest_col] = None

    # ── Deduplicar por correo institucional ───────────────────────────────────
    df = df.drop_duplicates(subset=["correo_institucional"], keep="first")

    cols_salida = [
        "correo_institucional",
        "cedula",
        "nombre",
        "whatsapp",
        "nivel_academico",
        "sede",
        "pais",
        "provincia",
        "ciudad",
        "parroquia",
        "barrio",
    ]
    result = df[[c for c in cols_salida if c in df.columns]].copy()

    logger.info(
        f"DatosEspecificos: {len(archivos)} archivo(s) → {len(result)} estudiantes únicos"
    )
    return result.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# TRANSFORMER 3b: Calificaciones históricas — TableauHistorico (P60–P67+)
# Reemplaza la lectura manual de la carpeta "Tableau Histórico" del Excel.
# Cada CSV cubre un período académico; el período se extrae del nombre de archivo.
# ─────────────────────────────────────────────────────────────────────────────

def transform_calificaciones_historico(carpeta: str) -> pd.DataFrame:
    """
    Lee todos los CSVs de la carpeta TableauHistorico y devuelve un DataFrame
    unificado con el campo 'periodo' extraído del nombre de cada archivo.

    Nombre esperado: "Detalle de Calificaciones _data(P67).csv"
    Separador: semicolon (;)
    Columnas: Sede, Campus, Carrera, Asignatura, Grupo, Estudiante, Docente, Nota Final
    Escala de Nota Final: 0–100

    Incluye todas las carreras (sin filtro).
    """
    carpeta_path = Path(carpeta)

    # Buscar todos los CSVs en la carpeta (independiente del nombre exacto)
    archivos = sorted(carpeta_path.glob("*.csv"))

    if not archivos:
        logger.warning(f"transform_calificaciones_historico: no se encontraron CSVs en {carpeta}")
        return pd.DataFrame()

    dfs = []
    for archivo in archivos:
        try:
            # Extraer período del nombre: "...(P67).csv" → "P67"
            m = re.search(r'\(P(\d+)\)', archivo.name, re.IGNORECASE)
            periodo = f"P{m.group(1)}" if m else archivo.stem

            df = pd.read_csv(archivo, sep=";", encoding="utf-8-sig", low_memory=False)
            df.columns = [c.strip() for c in df.columns]

            # Renombrar columnas al estándar interno (case-insensitive)
            rename_map = {}
            col_lower = {c.lower(): c for c in df.columns}
            if "sede"        in col_lower: rename_map[col_lower["sede"]]        = "sede"
            if "campus"      in col_lower: rename_map[col_lower["campus"]]      = "campus"
            if "carrera"     in col_lower: rename_map[col_lower["carrera"]]     = "carrera"
            if "asignatura"  in col_lower: rename_map[col_lower["asignatura"]]  = "asignatura"
            if "grupo"       in col_lower: rename_map[col_lower["grupo"]]       = "grupo"
            if "estudiante"  in col_lower: rename_map[col_lower["estudiante"]]  = "nombre_estudiante"
            if "docente"     in col_lower: rename_map[col_lower["docente"]]     = "docente"
            if "nota final"  in col_lower: rename_map[col_lower["nota final"]]  = "nota_final"
            df = df.rename(columns=rename_map)

            if "carrera" not in df.columns:
                logger.warning(f"  {archivo.name}: columna 'Carrera' no encontrada")
                continue

            # Limpiar carrera
            df["carrera"] = df["carrera"].apply(normalizar_carrera)

            # Nota final a float (escala 0–100)
            if "nota_final" in df.columns:
                df["nota_final"] = pd.to_numeric(df["nota_final"], errors="coerce")

            # Eliminar filas sin estudiante o sin asignatura
            if "nombre_estudiante" in df.columns:
                df = df[df["nombre_estudiante"].notna() & (df["nombre_estudiante"].str.strip() != "")]

            # Normalizar nombre estudiante a mayúsculas para consistencia
            if "nombre_estudiante" in df.columns:
                df["nombre_estudiante"] = df["nombre_estudiante"].str.strip().str.upper()

            # Añadir campo período
            df["periodo"] = periodo

            dfs.append(df)
            logger.info(f"  TableauHistorico {periodo}: {len(df)} registros EIB ({archivo.name})")

        except Exception as e:
            logger.error(f"Error leyendo {archivo.name}: {e}")

    if not dfs:
        return pd.DataFrame()

    df_all = pd.concat(dfs, ignore_index=True)
    logger.info(
        f"Calificaciones históricas: {len(archivos)} archivos → {len(df_all)} registros EIB "
        f"({df_all['periodo'].nunique() if 'periodo' in df_all.columns else 0} períodos)"
    )
    return df_all.reset_index(drop=True)


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

    # Merge con calificaciones si hay datos: agregar promedio por correo
    if not cal_agg.empty and "nombre_estudiante" in cal_agg.columns:
        # Intentar cruce por nombre normalizado
        df_master["nombre_norm"] = df_master["nombre_avac"].apply(
            lambda x: normalizar_nombre(x) if pd.notna(x) else ""
        )
        cal_agg["nombre_norm"] = cal_agg["nombre_estudiante"].apply(
            lambda x: normalizar_nombre(x) if pd.notna(x) else ""
        )
        df_master = df_master.merge(
            cal_agg[["nombre_norm", "promedio_notas"]],
            on="nombre_norm", how="left",
        )
        df_master.drop(columns=["nombre_norm"], inplace=True, errors="ignore")
    else:
        df_master["promedio_notas"] = None

    # Calcular índice de compromiso para cada estudiante
    indicadores = []
    for _, row in df_master.iterrows():
        def _safe_int(val):
            try:
                return int(val) if val is not None and not pd.isna(val) else 0
            except (ValueError, TypeError):
                return 0

        promedio = row.get("promedio_notas")
        if promedio is not None and pd.notna(promedio):
            promedio = float(promedio)
        else:
            promedio = None

        ind = calcular_indice_compromiso(
            dias_sin_acceso=row.get("dias_sin_acceso_max"),
            tareas_entregadas=_safe_int(row.get("total_entregas", 0)),
            tareas_totales=_safe_int(row.get("total_tareas", 0)),
            notas=[],
            promedio_calificaciones=promedio,
        )
        indicadores.append(ind)

    df_indicadores = pd.DataFrame(indicadores)
    df_master = pd.concat([df_master.reset_index(drop=True), df_indicadores], axis=1)

    logger.info(f"Estudiantes con indicadores calculados: {len(df_master)}")
    return df_master
