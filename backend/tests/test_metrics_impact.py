"""Tests de la fuente única de impacto (chore/estandar-casa, punto 5)."""
from backend.models.student import Student


def test_impact_empty(client):
    r = client.get("/metrics/impact")
    assert r.status_code == 200
    data = r.json()
    assert data["estudiantes_monitoreados"] == 0
    assert data["programas_activos"] == 0
    assert "definiciones" in data


def test_impact_counts(client, db):
    db.add_all([
        Student(nombre="A", carrera="Educación Básica"),
        Student(nombre="B", carrera="Educación Básica"),
        Student(nombre="C", carrera="Contabilidad"),
        Student(nombre="D", carrera=None),
    ])
    db.commit()

    data = client.get("/metrics/impact").json()
    assert data["estudiantes_monitoreados"] == 4
    # dos carreras distintas no nulas
    assert data["programas_activos"] == 2
    assert data["fuente"].startswith("GET /metrics/impact")
