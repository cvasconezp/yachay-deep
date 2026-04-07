"""Utilidades compartidas para los módulos de analítica."""
from typing import Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session
from ...models.grade import Grade


def _is_active_periodo(db_session, pf: str) -> bool:
    """Verifica si un periodo coincide con el semestre activo."""
    from ...models.course_config import SemesterConfig
    active = db_session.query(SemesterConfig.semestre).filter(
        SemesterConfig.activo == True).first()
    if not active or not active[0]:
        return False
    a = active[0].strip()
    return (a == pf or
            (a.startswith("P") and a[1:] == pf) or
            f"P{a}" == pf)


def apply_periodo_filter(query, periodo: Optional[str], column=None, db=None):
    """Aplica filtro de período a una query de SQLAlchemy.
    Maneja ambos formatos: 'P68' y '68' en la base de datos.
    Si el periodo es el activo e incluye NULL (grades legacy sin etiquetar).
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

        # Incluir NULL si es el periodo activo (grades cargados antes del fix)
        if db is not None and _is_active_periodo(db, pf):
            conditions.append(col.is_(None))

        query = query.filter(or_(*conditions))
    return query, pf
