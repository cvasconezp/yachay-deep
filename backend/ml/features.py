"""
Ingenieria de features para prediccion de desercion y reprobacion.
Consulta la tabla grades (datos historicos P57-P67) y construye
features por estudiante-periodo, agrupados por carrera.
"""
import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Periodos ordenados cronologicamente (P57+ para incluir datos históricos completos)
PERIODOS_ORDENADOS = ["P57", "P58", "P59", "P60", "P61", "P62", "P63", "P64", "P65", "P66", "P67"]

# ── Utilidades para mallas curriculares ──────────────────────────────────────
_MALLAS_DIR = Path(__file__).resolve().parent.parent / "data" / "mallas"


def _normalize_asig(name: str) -> str:
    """Normaliza nombre de asignatura: upper, colapsa whitespace/newlines."""
    return re.sub(r"\s+", " ", name.strip().upper())


def _strip_accents(text: str) -> str:
    """Elimina acentos para generar nombres de archivo."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _career_to_filename(carrera_upper: str) -> str:
    """Convierte nombre de carrera a nombre de archivo JSON."""
    base = _strip_accents(carrera_upper)
    base = re.sub(r"[^A-Z0-9]+", "_", base).strip("_")
    return f"{base}.json"


def _load_reference_malla(carrera_upper: str) -> set[str] | None:
    """Carga set de asignaturas desde JSON de referencia oficial.
    Retorna None si no existe archivo para esa carrera."""
    filename = _career_to_filename(carrera_upper)
    filepath = _MALLAS_DIR / filename
    if not filepath.exists():
        return None
    data = json.loads(filepath.read_text(encoding="utf-8"))
    niveles = data.get("niveles", {})
    asignaturas = set()
    for asigs in niveles.values():
        for asig in asigs:
            asignaturas.add(_normalize_asig(asig))
    return asignaturas


def _build_malla_from_grades(df_grades: pd.DataFrame) -> dict[str, set[str]]:
    """Infiere el set de asignaturas por carrera a partir de grades históricos.
    Para carreras sin JSON de referencia."""
    malla = {}
    for carrera, group in df_grades.groupby("carrera"):
        if carrera:
            malla[carrera.strip().upper()] = set(
                _normalize_asig(a) for a in group["asignatura"].dropna().unique()
            )
    return malla


def build_features(db: Session) -> pd.DataFrame:
    """
    Construye DataFrame con features + labels por (student_id, periodo).
    Incluye columna 'carrera' para entrenar modelos por carrera.

    Features por estudiante-periodo:
      - promedio_notas: media de nota_final
      - num_asignaturas: cantidad de materias
      - num_reprobadas: materias con nota < 70
      - pct_reprobadas: porcentaje reprobadas
      - nota_min, nota_max, std_notas
      - num_zeros: materias con nota = 0

    Labels:
      - deserto: 1 si NO aparece en el periodo siguiente, 0 si si
      - reprobo: 1 si alguna nota < 70, 0 si todas >= 70
    """
    query = text("""
        SELECT g.student_id, g.periodo, g.nota_final, g.carrera, g.asignatura
        FROM grades g
        WHERE g.periodo IS NOT NULL
        ORDER BY g.student_id, g.periodo
    """)

    rows = db.execute(query).fetchall()
    if not rows:
        logger.warning("No hay calificaciones historicas para construir features")
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=["student_id", "periodo", "nota_final", "carrera", "asignatura"])
    df["nota_final"] = pd.to_numeric(df["nota_final"], errors="coerce").fillna(0)

    # Determinar carrera principal por estudiante (la más frecuente)
    carrera_por_estudiante = (
        df.groupby("student_id")["carrera"]
        .agg(lambda x: x.mode().iloc[0] if not x.mode().empty else None)
        .to_dict()
    )

    # [BUG-06] FIX: Mapeo para no etiquetar egresados/graduados como desertores
    # Obtener nivel_academico de cada estudiante
    student_info_query = text("""
        SELECT id, nivel_academico FROM students
    """)
    student_info_rows = db.execute(student_info_query).fetchall()
    nivel_por_estudiante = {row[0]: row[1] for row in student_info_rows}

    # ── Cargar mallas de referencia oficiales (JSON) por carrera ──
    # Solo usamos JSONs oficiales para verificar egreso completo.
    # Para carreras sin JSON, nivel 8 es suficiente indicador de egreso.
    malla_por_carrera: dict[str, set[str]] = {}
    for carrera_key in set(c.strip().upper() for c in df["carrera"].dropna().unique()):
        ref = _load_reference_malla(carrera_key)
        if ref is not None:
            malla_por_carrera[carrera_key] = ref
            logger.info(f"Malla referencia cargada: {carrera_key} ({len(ref)} materias)")

    # ── Materias aprobadas (nota >= 70) por estudiante acumuladas ──
    # Un estudiante puede aprobar la misma materia en diferentes periodos;
    # contamos el set único de asignaturas aprobadas.
    aprobadas_mask = df["nota_final"] >= 70
    materias_aprobadas_por_sid: dict[int, set[str]] = {}
    for sid, group in df[aprobadas_mask].groupby("student_id"):
        materias_aprobadas_por_sid[sid] = set(
            _normalize_asig(a) for a in group["asignatura"].dropna().unique()
        )


    # Agrupar por estudiante-periodo
    grouped = df.groupby(["student_id", "periodo"])
    features = grouped.agg(
        promedio_notas=("nota_final", "mean"),
        num_asignaturas=("nota_final", "count"),
        num_reprobadas=("nota_final", lambda x: (x < 70).sum()),
        nota_min=("nota_final", "min"),
        nota_max=("nota_final", "max"),
        std_notas=("nota_final", "std"),
        num_zeros=("nota_final", lambda x: (x == 0).sum()),
    ).reset_index()

    features["std_notas"] = features["std_notas"].fillna(0)
    features["pct_reprobadas"] = features["num_reprobadas"] / features["num_asignaturas"]

    # Asignar carrera principal a cada registro
    features["carrera"] = features["student_id"].map(carrera_por_estudiante)

    # --- Labels ---
    # Conjunto de estudiantes presentes en cada periodo
    estudiantes_por_periodo = df.groupby("periodo")["student_id"].apply(set).to_dict()

    # Construir periodo_siguiente mapping
    periodos_en_datos = sorted(features["periodo"].unique().tolist())

    def periodo_siguiente(p: str) -> Optional[str]:
        if p in PERIODOS_ORDENADOS:
            idx = PERIODOS_ORDENADOS.index(p)
            if idx + 1 < len(PERIODOS_ORDENADOS):
                nxt = PERIODOS_ORDENADOS[idx + 1]
                if nxt in periodos_en_datos:
                    return nxt
        return None

    # Label desercion: 1 si no aparece en periodo siguiente
    # Excluir egresados para no contaminar el modelo con falsos positivos
    # Lógica de egreso: está en 8vo nivel Y aprobó todas las materias de la malla.
    # Si no cumple ambas condiciones y desapareció → deserción.
    def label_desercion(row):
        nxt = periodo_siguiente(row["periodo"])
        if nxt is None:
            return None  # ultimo periodo, no se puede evaluar

        sid = row["student_id"]

        # Verificar si el estudiante está en el siguiente periodo
        if sid in estudiantes_por_periodo.get(nxt, set()):
            return 0  # Sigue matriculado en siguiente periodo

        # ── No aparece en siguiente periodo: ¿desertó o egresó? ──

        # Egresado = nivel 8 + aprobó todas las materias de la malla
        nivel_ac = nivel_por_estudiante.get(sid)
        if nivel_ac is not None and nivel_ac >= 8:
            carrera = carrera_por_estudiante.get(sid, "")
            carrera_key = (carrera or "").strip().upper()
            malla = malla_por_carrera.get(carrera_key)
            aprobadas = materias_aprobadas_por_sid.get(sid, set())

            if malla is not None:
                # Verificar si aprobó todas las materias de la malla
                faltantes = malla - aprobadas
                if len(faltantes) == 0:
                    return 0  # Egresado: nivel 8 + malla completa
            else:
                # Sin malla de referencia: nivel 8 es suficiente indicador
                return 0

        # No está en nivel 8 o no completó la malla → deserción
        return 1

    features["deserto"] = features.apply(label_desercion, axis=1)

    # Label reprobacion: 1 si tiene alguna nota < 70
    features["reprobo"] = (features["num_reprobadas"] > 0).astype(int)

    # [GAP-F5-02] Feature de retroalimentación: ¿tuvo intervención en período anterior?
    # Esto cierra el feedback loop: intervenciones → modelo aprende de ellas
    try:
        interv_query = text("""
            SELECT i.student_id, g.periodo
            FROM interventions i
            JOIN grades g ON g.student_id = i.student_id AND g.periodo IS NOT NULL
            GROUP BY i.student_id, g.periodo
        """)
        interv_rows = db.execute(interv_query).fetchall()
        if interv_rows:
            interv_df = pd.DataFrame(interv_rows, columns=["student_id", "periodo"])
            interv_set = set(zip(interv_df["student_id"], interv_df["periodo"]))

            def tuvo_intervencion_previa(row):
                per = row["periodo"]
                sid = row["student_id"]
                if per in PERIODOS_ORDENADOS:
                    idx = PERIODOS_ORDENADOS.index(per)
                    if idx > 0:
                        prev = PERIODOS_ORDENADOS[idx - 1]
                        return 1 if (sid, prev) in interv_set else 0
                return 0

            features["tuvo_intervencion"] = features.apply(tuvo_intervencion_previa, axis=1)
        else:
            features["tuvo_intervencion"] = 0
    except Exception as e:
        logger.warning(f"No se pudo calcular feature de intervenciones: {e}")
        features["tuvo_intervencion"] = 0

    carreras = features["carrera"].dropna().nunique()
    logger.info(
        f"Features construidas: {len(features)} registros, "
        f"{features['student_id'].nunique()} estudiantes, "
        f"{carreras} carreras, periodos: {periodos_en_datos}"
    )

    return features


def _get_active_periodo(db: Session) -> Optional[str]:
    """Obtiene el periodo del semestre activo desde SemesterConfig."""
    try:
        from ..models.course_config import SemesterConfig
        sc = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
        return sc.semestre.strip() if sc and sc.semestre else None
    except Exception:
        return None


def _detect_current_periodo(db: Session) -> Optional[str]:
    """Detecta el periodo actual directamente de grades.
    Busca periodos que NO están en PERIODOS_ORDENADOS (históricos P57-P67).
    Si hay varios, toma el más reciente (mayor número)."""
    try:
        result = db.execute(text(
            "SELECT DISTINCT periodo FROM grades WHERE periodo IS NOT NULL"
        )).fetchall()
        all_periodos = [r[0] for r in result if r[0]]

        historicos = set(PERIODOS_ORDENADOS)
        # También incluir variantes sin P (ej. "67")
        for p in list(historicos):
            if p.startswith("P"):
                historicos.add(p[1:])

        current = [p for p in all_periodos if p not in historicos]
        if not current:
            return None

        # Ordenar: extraer número, el mayor es el más reciente
        import re as _re
        def _sort_key(p):
            m = _re.search(r"(\d+)", p)
            return int(m.group(1)) if m else 0

        current.sort(key=_sort_key, reverse=True)
        return current[0]
    except Exception as e:
        logger.warning(f"_detect_current_periodo error: {e}")
        return None


def _build_periodo_condition(periodo: Optional[str]) -> str:
    """Construye la condición SQL para filtrar por periodo activo.
    Maneja ambos formatos (P68/68) y fallback a NULL."""
    if not periodo:
        return "g.periodo IS NULL"

    conditions = ["g.periodo IS NULL"]  # siempre incluir NULL como fallback
    if periodo.startswith("P"):
        conditions.append(f"g.periodo = '{periodo}'")
        conditions.append(f"g.periodo = '{periodo[1:]}'")
    else:
        conditions.append(f"g.periodo = '{periodo}'")
        conditions.append(f"g.periodo = 'P{periodo}'")
    return f"({' OR '.join(conditions)})"


def build_current_features(db: Session) -> pd.DataFrame:
    """
    Construye features para estudiantes del semestre actual.
    Estrategia de detección de periodo:
      1. SemesterConfig activo
      2. Detección automática desde grades (periodo no histórico)
      3. Fallback a periodo=NULL

    [GAP-F2-01] Enriquecido con variables conductuales de la tabla students:
    dias_sin_acceso, porcentaje_tareas, indice_compromiso.
    Estas features mejoran la predicción según la literatura de Learning Analytics.
    """
    active_periodo = _get_active_periodo(db)
    periodo_cond = _build_periodo_condition(active_periodo)

    query = text(f"""
        SELECT g.student_id, g.nota_final, s.carrera,
               s.dias_sin_acceso, s.porcentaje_tareas, s.indice_compromiso
        FROM grades g
        JOIN students s ON s.id = g.student_id
        WHERE {periodo_cond}
    """)

    rows = db.execute(query).fetchall()
    logger.info(f"build_current_features: periodo_config={active_periodo}, rows={len(rows)}")

    # Fallback: si SemesterConfig no coincide con grades, detectar desde la tabla
    if not rows and active_periodo:
        detected = _detect_current_periodo(db)
        if detected and detected != active_periodo:
            logger.info(f"build_current_features: fallback a periodo detectado={detected}")
            periodo_cond2 = _build_periodo_condition(detected)
            query2 = text(f"""
                SELECT g.student_id, g.nota_final, s.carrera,
                       s.dias_sin_acceso, s.porcentaje_tareas, s.indice_compromiso
                FROM grades g
                JOIN students s ON s.id = g.student_id
                WHERE {periodo_cond2}
            """)
            rows = db.execute(query2).fetchall()
            logger.info(f"build_current_features: fallback rows={len(rows)}")

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=[
        "student_id", "nota_final", "carrera",
        "dias_sin_acceso", "porcentaje_tareas", "indice_compromiso",
    ])
    df["nota_final"] = pd.to_numeric(df["nota_final"], errors="coerce").fillna(0)

    # Carrera por estudiante (la más frecuente en grades actuales)
    carrera_por_estudiante = (
        df.groupby("student_id")["carrera"]
        .agg(lambda x: x.mode().iloc[0] if not x.mode().empty else None)
        .to_dict()
    )

    # [GAP-F2-01] Variables conductuales por estudiante (tomar primera fila, son iguales)
    conductual = df.groupby("student_id").agg(
        dias_sin_acceso=("dias_sin_acceso", "first"),
        porcentaje_tareas=("porcentaje_tareas", "first"),
        indice_compromiso=("indice_compromiso", "first"),
    ).reset_index()

    grouped = df.groupby("student_id")
    features = grouped.agg(
        promedio_notas=("nota_final", "mean"),
        num_asignaturas=("nota_final", "count"),
        num_reprobadas=("nota_final", lambda x: (x < 70).sum()),
        nota_min=("nota_final", "min"),
        nota_max=("nota_final", "max"),
        std_notas=("nota_final", "std"),
        num_zeros=("nota_final", lambda x: (x == 0).sum()),
    ).reset_index()

    features["std_notas"] = features["std_notas"].fillna(0)
    features["pct_reprobadas"] = features["num_reprobadas"] / features["num_asignaturas"]
    features["carrera"] = features["student_id"].map(carrera_por_estudiante)

    # [GAP-F2-01] Merge variables conductuales
    features = features.merge(conductual, on="student_id", how="left")
    features["dias_sin_acceso"] = features["dias_sin_acceso"].fillna(0)
    features["porcentaje_tareas"] = features["porcentaje_tareas"].fillna(50)  # neutral default
    features["indice_compromiso"] = features["indice_compromiso"].fillna(0.5)

    return features


# Features originales (8) — compatibles con modelos históricos
FEATURE_COLUMNS = [
    "promedio_notas",
    "num_asignaturas",
    "num_reprobadas",
    "pct_reprobadas",
    "nota_min",
    "nota_max",
    "std_notas",
    "num_zeros",
]

# [GAP-F2-01] Features extendidas con variables conductuales
# Disponibles solo para semestre actual (build_current_features).
# Los modelos se re-entrenarán progresivamente para usarlas.
EXTENDED_FEATURE_COLUMNS = FEATURE_COLUMNS + [
    "dias_sin_acceso",
    "porcentaje_tareas",
    "indice_compromiso",
]
