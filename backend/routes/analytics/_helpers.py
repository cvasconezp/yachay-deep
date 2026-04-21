"""Utilidades compartidas para los módulos de analítica."""
from typing import Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session
from ...models.grade import Grade


def apply_periodo_filter(query, periodo: Optional[str], column=None, include_null=False):
    """Aplica filtro de período a una query de SQLAlchemy.

    Maneja ambos formatos: 'P68' y '68' en la base de datos.

    Args:
        query: SQLAlchemy query
        periodo: Periodo a filtrar ('P68', '68', 'actual', 'todos', None)
        column: Columna a filtrar (default: Grade.periodo).
                Cuando se pasa una columna de Enrollment, 'actual' no filtra
                (enrollment siempre tiene periodo asignado).
        include_null: Si True, incluye registros con periodo=NULL (grades legacy)

    Retorna (query_filtrado, periodo_normalizado).
    """
    col = column or Grade.periodo
    is_grade_column = column is None  # True si estamos filtrando Grade.periodo
    pf = periodo if periodo else "actual"

    if pf == "actual":
        if is_grade_column:
            # Grades: "actual" = periodo es NULL (legacy sin etiqueta)
            query = query.filter(col.is_(None))
        # Enrollment/otros: "actual" no filtra (siempre tienen periodo)
    elif pf != "todos":
        conditions = []
        if pf.startswith("P"):
            raw = pf[1:]
            conditions = [col == pf, col == raw]
        else:
            conditions = [col == pf, col == f"P{pf}"]

        # Incluir NULL (grades legacy cargados antes del fix de etiquetado)
        if include_null:
            conditions.append(col.is_(None))

        query = query.filter(or_(*conditions))
    return query, pf


# ── Normalización de nivel de riesgo ───────────────────────────────

_RIESGO_MAP = {
    "alto": "Alto", "medio": "Medio", "bajo": "Bajo",
    "Alto": "Alto", "Medio": "Medio", "Bajo": "Bajo",
    "ALTO": "Alto", "MEDIO": "Medio", "BAJO": "Bajo",
}


def normalize_riesgo(valor: Optional[str]) -> Optional[str]:
    """Normaliza nivel_riesgo a 'Alto', 'Medio', 'Bajo' o None."""
    if not valor:
        return None
    return _RIESGO_MAP.get(valor.strip(), None)


def build_risk_map(risk_counts) -> dict:
    """Construye risk_map normalizado desde query results [(nivel_riesgo, count)]."""
    result = {"Alto": 0, "Medio": 0, "Bajo": 0}
    for nivel, cnt in risk_counts:
        normalized = normalize_riesgo(nivel)
        if normalized:
            result[normalized] += cnt
    return result


# ── Umbrales académicos configurables ──────────────────────────────

# Defaults (usados cuando SemesterConfig no tiene valor)
DEFAULTS = {
    "nota_aprobacion": 70.0,
    "dias_inactividad": 14,
    "tareas_minimo": 50.0,
    "compromiso_minimo": 0.4,
}


def get_umbrales(db: Session) -> dict:
    """Carga umbrales académicos desde SemesterConfig activo, con defaults."""
    from ...models.course_config import SemesterConfig
    sc = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    return {
        "nota_aprobacion": (sc.umbral_nota_aprobacion if sc and sc.umbral_nota_aprobacion is not None
                            else DEFAULTS["nota_aprobacion"]),
        "dias_inactividad": (sc.umbral_dias_inactividad if sc and sc.umbral_dias_inactividad is not None
                             else DEFAULTS["dias_inactividad"]),
        "tareas_minimo": (sc.umbral_tareas_minimo if sc and sc.umbral_tareas_minimo is not None
                          else DEFAULTS["tareas_minimo"]),
        "compromiso_minimo": (sc.umbral_compromiso_minimo if sc and sc.umbral_compromiso_minimo is not None
                              else DEFAULTS["compromiso_minimo"]),
    }
