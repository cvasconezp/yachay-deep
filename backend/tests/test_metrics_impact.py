"""Tests de la cifra de impacto.

La cifra de estudiantes/carreras sale de datos institucionales reales. Estuvo
publicada en la landing comercial vía un endpoint SIN autenticación: cualquiera podía
pedir /api/metrics/impact y obtener el conteo real de la institución. Sin convenio
firmado eso no es defendible, así que el endpoint quedó cerrado y estos tests lo fijan
para que no vuelva a abrirse por descuido.
"""
from backend.models.student import Student
from backend.auth.jwt import create_access_token


def _headers(user):
    # get_current_user lee 'sub' como el ID del usuario, no el email
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


def test_impact_requiere_autenticacion(client, db):
    """El endpoint NO debe ser público — esta es la regresión que importa."""
    db.add(Student(nombre="A", carrera="Educación Básica"))
    db.commit()

    r = client.get("/metrics/impact")
    assert r.status_code in (401, 403), (
        "/metrics/impact volvió a ser público: expone conteos institucionales reales "
        "a cualquiera. Requiere convenio firmado antes de publicarse."
    )


def test_impact_empty(client, admin_user):
    r = client.get("/metrics/impact", headers=_headers(admin_user))
    assert r.status_code == 200
    data = r.json()
    assert data["estudiantes_monitoreados"] == 0
    assert data["programas_activos"] == 0
    assert "definiciones" in data


def test_impact_counts(client, db, admin_user):
    db.add_all([
        Student(nombre="A", carrera="Educación Básica"),
        Student(nombre="B", carrera="Educación Básica"),
        Student(nombre="C", carrera="Contabilidad"),
        Student(nombre="D", carrera=None),
    ])
    db.commit()

    data = client.get("/metrics/impact", headers=_headers(admin_user)).json()
    assert data["estudiantes_monitoreados"] == 4
    # dos carreras distintas no nulas
    assert data["programas_activos"] == 2
    assert data["fuente"].startswith("GET /metrics/impact")
