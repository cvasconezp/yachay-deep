"""[WF5] Utilidades de aislamiento por tenant (multi-tenant en BD compartida).

Estrategia (ver Runbook WF5):
  - 1-3 clientes: instancias separadas (no se usa esto).
  - 4+ clientes: BD compartida con tenant_id + RLS. Activar entonces:
      1) Poblar tenant_id en datos existentes.
      2) Usar tenant_query() en TODAS las lecturas de datos de cliente.
      3) Activar RLS en Postgres (scripts/enable_rls.sql) como defensa en profundidad.
"""
from sqlalchemy.orm import Session


def tenant_query(db: Session, model, tenant_id):
    """Devuelve una query del modelo SIEMPRE filtrada por tenant_id.

    Si tenant_id es None (modo single-tenant / admin global) no filtra,
    para mantener compatibilidad con los despliegues de instancia única.
    """
    q = db.query(model)
    if tenant_id is not None:
        q = q.filter(model.tenant_id == tenant_id)
    return q


def set_rls_tenant(db: Session, tenant_id):
    """Fija el tenant del request a nivel de sesión Postgres (para RLS).
    No-op en SQLite (dev/test)."""
    from sqlalchemy import text
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return
    db.execute(text("SET app.tenant_id = :tid"), {"tid": str(tenant_id) if tenant_id is not None else ""})
