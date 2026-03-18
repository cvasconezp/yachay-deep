"""Utilidades compartidas para los módulos de analítica."""
from typing import Optional
from sqlalchemy.orm import Session
from ...models.grade import Grade


def apply_periodo_filter(query, periodo: Optional[str], column=None):
    """Aplica filtro de período a una query de SQLAlchemy.
    Retorna (query_filtrado, periodo_normalizado)."""
    col = column or Grade.periodo
    pf = periodo if periodo else "actual"
    if pf == "actual":
        query = query.filter(col.is_(None))
    elif pf != "todos":
        query = query.filter(col == pf)
    return query, pf
