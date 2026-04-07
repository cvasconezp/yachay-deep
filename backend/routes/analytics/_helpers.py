"""Utilidades compartidas para los módulos de analítica."""
from typing import Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session
from ...models.grade import Grade


def apply_periodo_filter(query, periodo: Optional[str], column=None, include_null=False):
    """Aplica filtro de período a una query de SQLAlchemy.
    Maneja ambos formatos: 'P68' y '68' en la base de datos.
    Si include_null=True, también incluye registros con periodo=NULL.
    Retorna (query_filtrado, periodo_normalizado)."""
    col = column or Grade.periodo
    pf = periodo if periodo else "actual"
    if pf == "actual":
        query = query.filter(col.is_(None))
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
