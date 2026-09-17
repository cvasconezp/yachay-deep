"""Tests del módulo Grupos: selector de fuente de la nota (mixta | final | avac)."""
import datetime as dt
import pytest

from backend.models import Student, Grade, Enrollment, TaskSubmission
from backend.models.course_config import SemesterConfig
from .conftest import auth


@pytest.fixture
def semester_config(db):
    sc = SemesterConfig(semestre="P68", activo=True, bloque_actual="1")
    db.add(sc)
    db.commit()
    return sc


@pytest.fixture
def grupo_data(db):
    """Un estudiante con nota final (Tableau)=25 y parcial AVAC (total_curso)=88."""
    s = Student(id=1, nombre="ALUMNO GRUPO", carrera="MARKETING E INTELIGENCIA DE MERCADOS",
                nivel_academico=1, nivel_riesgo="Alto")
    db.add(s)
    db.add(Enrollment(student_id=1, asignatura="MATEMATICAS",
                      carrera="MARKETING E INTELIGENCIA DE MERCADOS", nivel=1,
                      periodo="P68", codigo_grupo="MAT-1"))
    db.add(Grade(student_id=1, asignatura="MATEMATICAS",
                 carrera="MARKETING E INTELIGENCIA DE MERCADOS", nivel=1,
                 nota_final=25.0, periodo="P68"))
    db.add(TaskSubmission(student_id=1, codigo_curso="MAT-1", periodo="P68",
                          snapshot_date=dt.date.today(), total_curso=88.0,
                          unidad="1", entregada=True))
    db.commit()


def _nota(data):
    est = data["estudiantes"][0]
    # notas es un dict asignatura→nota
    return list(est["notas"].values())[0] if est.get("notas") else None


def test_fuente_final_usa_tableau(client, admin_token, semester_config, grupo_data):
    r = client.get("/analytics/grupos?periodo=P68&fuente_nota=final", headers=auth(admin_token))
    assert r.status_code == 200
    assert _nota(r.json()) == 25.0


def test_fuente_avac_usa_total_curso(client, admin_token, semester_config, grupo_data):
    r = client.get("/analytics/grupos?periodo=P68&fuente_nota=avac", headers=auth(admin_token))
    assert r.status_code == 200
    assert _nota(r.json()) == 88.0


def test_fuente_mixta_prefiere_final(client, admin_token, semester_config, grupo_data):
    r = client.get("/analytics/grupos?periodo=P68&fuente_nota=mixta", headers=auth(admin_token))
    assert r.status_code == 200
    assert _nota(r.json()) == 25.0


def test_fuente_invalida_cae_a_mixta(client, admin_token, semester_config, grupo_data):
    r = client.get("/analytics/grupos?periodo=P68&fuente_nota=xxx", headers=auth(admin_token))
    assert r.status_code == 200
    assert _nota(r.json()) == 25.0
