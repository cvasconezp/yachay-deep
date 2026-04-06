"""Utilidades compartidas para los módulos de analítica."""
from typing import Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session
from ...models.grade import Grade


def apply_periodo_filter(query, periodo: Optional[str], column=None):
    """Aplica filtro de período a una query de SQLAlchemy.
    Maneja ambos formatos: 'P68' y '68' en la base de datos.
    Retorna (query_filtrado, periodo_normalizado)."""
    col = column or Grade.periodo
    pf = periodo if periodo else "actual"
    if pf == "actual":
        query = query.filter(col.is_(None))
    elif pf != "todos":
        # Buscar tanto "P68" como "68" para cubrir datos no normalizados
        if pf.startswith("P"):
            raw = pf[1:]  # "68"
            query = query.filter(or_(col == pf, col == raw))
        else:
            query = query.filter(or_(col == pf, col == f"P{pf}"))
    return query, pf
