"""WF5 — aislamiento por tenant (tenant_id + helper tenant_query)."""
from backend.models import Student, Grade, Intervention
from backend.tenant_filter import tenant_query


def _seed(db):
    a1 = Student(nombre="A1", cedula="a1", tenant_id="ups")
    a2 = Student(nombre="A2", cedula="a2", tenant_id="ups")
    b1 = Student(nombre="B1", cedula="b1", tenant_id="otra")
    db.add_all([a1, a2, b1]); db.commit()
    return a1, a2, b1


def test_columna_tenant_id_existe():
    assert hasattr(Student, "tenant_id")
    assert hasattr(Grade, "tenant_id")
    assert hasattr(Intervention, "tenant_id")


def test_tenant_query_aisla_por_tenant(db):
    _seed(db)
    ups = tenant_query(db, Student, "ups").all()
    otra = tenant_query(db, Student, "otra").all()
    assert {s.nombre for s in ups} == {"A1", "A2"}
    assert {s.nombre for s in otra} == {"B1"}
    # tenant A nunca ve filas de tenant B
    assert all(s.tenant_id == "ups" for s in ups)
    assert all(s.tenant_id != "ups" for s in otra)


def test_tenant_none_no_filtra(db):
    _seed(db)
    # modo single-tenant/admin global: ve todo
    assert len(tenant_query(db, Student, None).all()) == 3
