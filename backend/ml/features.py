"""
Ingenieria de features para prediccion de desercion y reprobacion.
Consulta la tabla grades (datos historicos P60-P67) y construye
features por estudiante-periodo, agrupados por carrera.
"""
import logging
from typing import Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Periodos ordenados cronologicamente
PERIODOS_ORDENADOS = ["P60", "P61", "P62", "P63", "P64", "P65", "P66", "P67"]


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
        SELECT g.student_id, g.periodo, g.nota_final, g.carrera
        FROM grades g
        WHERE g.periodo IS NOT NULL
        ORDER BY g.student_id, g.periodo
    """)

    rows = db.execute(query).fetchall()
    if not rows:
        logger.warning("No hay calificaciones historicas para construir features")
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=["student_id", "periodo", "nota_final", "carrera"])
    df["nota_final"] = pd.to_numeric(df["nota_final"], errors="coerce").fillna(0)

    # Determinar carrera principal por estudiante (la más frecuente)
    carrera_por_estudiante = (
        df.groupby("student_id")["carrera"]
        .agg(lambda x: x.mode().iloc[0] if not x.mode().empty else None)
        .to_dict()
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
    def label_desercion(row):
        nxt = periodo_siguiente(row["periodo"])
        if nxt is None:
            return None  # ultimo periodo, no se puede evaluar
        return 0 if row["student_id"] in estudiantes_por_periodo.get(nxt, set()) else 1

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


def build_current_features(db: Session) -> pd.DataFrame:
    """
    Construye features para estudiantes del semestre actual (periodo IS NULL).
    Incluye carrera del estudiante para seleccionar modelo correcto.

    [GAP-F2-01] Enriquecido con variables conductuales de la tabla students:
    dias_sin_acceso, porcentaje_tareas, indice_compromiso.
    Estas features mejoran la predicción según la literatura de Learning Analytics.
    """
    query = text("""
        SELECT g.student_id, g.nota_final, s.carrera,
               s.dias_sin_acceso, s.porcentaje_tareas, s.indice_compromiso
        FROM grades g
        JOIN students s ON s.id = g.student_id
        WHERE g.periodo IS NULL
    """)

    rows = db.execute(query).fetchall()
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
