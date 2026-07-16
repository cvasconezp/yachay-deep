"""Ámbito por carrera: el admin lo ve todo, el resto solo lo asignado."""
import pytest
from fastapi import HTTPException

from backend.models.user import User, UserRole
from backend.models.student import Student
from backend.auth.jwt import hash_password
from backend.services.scope import (
    carreras_de, puede_ver_carrera, filtrar_carrera, asegurar_acceso_carrera, es_admin,
)

EDU, CONTA, ING = "Educación Básica", "Contabilidad", "Ingeniería"


def _user(db, rol, carreras=None, email=None):
    u = User(email=email or f"{rol}-{carreras}@t.ec", nombre=rol,
             hashed_password=hash_password("TestPassword123!"),
             role=UserRole(rol), is_active=True, carreras=carreras)
    db.add(u); db.commit(); db.refresh(u); return u


@pytest.fixture
def estudiantes(db):
    db.add_all([
        Student(nombre="Ana", carrera=EDU), Student(nombre="Beto", carrera=EDU),
        Student(nombre="Caro", carrera=CONTA), Student(nombre="Dani", carrera=ING),
    ])
    db.commit()


# ── admin ──
def test_admin_ve_todo_aunque_tenga_carreras(db, estudiantes):
    a = _user(db, "admin", carreras=[EDU])       # el campo debe ignorarse
    assert es_admin(a) and carreras_de(a) is None
    assert filtrar_carrera(db.query(Student), a).count() == 4


# ── denegar por defecto ──
def test_monitor_sin_carreras_no_ve_nada(db, estudiantes):
    """La decisión de diseño: sin asignar = ninguna, NO todas."""
    m = _user(db, "monitor", carreras=None)
    assert carreras_de(m) == []
    assert filtrar_carrera(db.query(Student), m).count() == 0


def test_lista_vacia_tampoco_ve_nada(db, estudiantes):
    m = _user(db, "monitor", carreras=[])
    assert filtrar_carrera(db.query(Student), m).count() == 0


# ── filtrado real ──
def test_monitor_ve_solo_su_carrera(db, estudiantes):
    m = _user(db, "monitor", carreras=[EDU])
    res = filtrar_carrera(db.query(Student), m).all()
    assert len(res) == 2
    assert {s.carrera for s in res} == {EDU}


def test_varias_carreras(db, estudiantes):
    c = _user(db, "coordinador", carreras=[EDU, ING])
    res = filtrar_carrera(db.query(Student), c).all()
    assert {s.carrera for s in res} == {EDU, ING}
    assert len(res) == 3


def test_docente_tambien_queda_acotado(db, estudiantes):
    d = _user(db, "docente", carreras=[CONTA])
    assert filtrar_carrera(db.query(Student), d).count() == 1


# ── permisos puntuales ──
def test_puede_ver_carrera(db):
    m = _user(db, "monitor", carreras=[EDU])
    assert puede_ver_carrera(m, EDU) is True
    assert puede_ver_carrera(m, CONTA) is False
    assert puede_ver_carrera(_user(db, "admin", email="a2@t.ec"), CONTA) is True


def test_asegurar_acceso_lanza_403(db):
    m = _user(db, "monitor", carreras=[EDU])
    asegurar_acceso_carrera(m, EDU)                  # no lanza
    with pytest.raises(HTTPException) as e:
        asegurar_acceso_carrera(m, CONTA)
    assert e.value.status_code == 403


def test_admin_nunca_recibe_403(db):
    a = _user(db, "admin", email="a3@t.ec")
    asegurar_acceso_carrera(a, "Cualquier Carrera")


def test_no_se_filtra_por_coincidencia_parcial(db, estudiantes):
    """'Educación' no debe arrastrar 'Educación Básica' por accidente."""
    m = _user(db, "monitor", carreras=["Educación"])
    assert filtrar_carrera(db.query(Student), m).count() == 0
