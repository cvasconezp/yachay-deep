"""WF5 — helper de aislamiento por tenant (tenant_query).

NOTA: la columna tenant_id NO está activa en los modelos de producción todavía
(se difiere a la fase multi-tenant / 4+ clientes, ver Runbook WF5 y
SECURITY_INFRA_CHECKLIST). Aquí validamos el helper con un modelo de prueba
aislado, para que la lógica de aislamiento quede verificada y lista para activar.
"""
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.tenant_filter import tenant_query

_Base = declarative_base()


class _RowConTenant(_Base):
    __tablename__ = "row_con_tenant"
    id = Column(Integer, primary_key=True)
    nombre = Column(String)
    tenant_id = Column(String, index=True)


def _mk_session():
    eng = create_engine("sqlite://")
    _Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add_all([
        _RowConTenant(nombre="A1", tenant_id="ups"),
        _RowConTenant(nombre="A2", tenant_id="ups"),
        _RowConTenant(nombre="B1", tenant_id="otra"),
    ])
    s.commit()
    return s


def test_tenant_query_aisla_por_tenant():
    s = _mk_session()
    ups = tenant_query(s, _RowConTenant, "ups").all()
    otra = tenant_query(s, _RowConTenant, "otra").all()
    assert {r.nombre for r in ups} == {"A1", "A2"}
    assert {r.nombre for r in otra} == {"B1"}
    # tenant A nunca ve filas de tenant B
    assert all(r.tenant_id == "ups" for r in ups)


def test_tenant_none_no_filtra():
    s = _mk_session()
    assert len(tenant_query(s, _RowConTenant, None).all()) == 3
