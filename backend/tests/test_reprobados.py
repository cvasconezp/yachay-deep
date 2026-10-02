"""Tests del módulo Reprobados: informe por período·carrera con indicadores."""
import datetime as dt
import pytest

from backend.models import Student, Grade, Enrollment, Intervention
from backend.models.course_config import SemesterConfig
from .conftest import auth


@pytest.fixture
def semester_config(db):
    sc = SemesterConfig(semestre="P68", activo=True, bloque_actual="1")
    db.add(sc)
    db.commit()
    return sc


@pytest.fixture
def data_reprobados(db):
    carrera = "MARKETING E INTELIGENCIA DE MERCADOS"
    # Reprobado + desconectado + sin intervención
    s1 = Student(id=1, nombre="ALUMNO UNO", carrera=carrera, nivel_academico=1,
                 nivel_riesgo="Alto", indice_compromiso=0.25,
                 dias_desde_ultimo_acceso=30, porcentaje_tareas=20.0,
                 estado_matricula="Matriculado", prob_reprobacion=0.8,
                 prob_desercion=0.7, score_recuperabilidad=30.0)
    # Reprobado pero conectado (académica)
    s2 = Student(id=2, nombre="ALUMNO DOS", carrera=carrera, nivel_academico=1,
                 nivel_riesgo="Medio", indice_compromiso=0.75,
                 dias_desde_ultimo_acceso=2, porcentaje_tareas=90.0,
                 estado_matricula="Matriculado")
    # Aprobado (NO debe salir)
    s3 = Student(id=3, nombre="ALUMNO TRES", carrera=carrera, nivel_academico=1,
                 indice_compromiso=0.9)
    db.add_all([s1, s2, s3])
    db.add_all([
        Grade(student_id=1, asignatura="MATEMATICAS", carrera=carrera, nivel=1,
              nota_final=40.0, periodo="P68"),
        Grade(student_id=1, asignatura="ETICA", carrera=carrera, nivel=1,
              nota_final=55.0, periodo="P68"),
        Grade(student_id=2, asignatura="MATEMATICAS", carrera=carrera, nivel=1,
              nota_final=60.0, periodo="P68"),
        Grade(student_id=2, asignatura="ETICA", carrera=carrera, nivel=1,
              nota_final=85.0, periodo="P68"),
        Grade(student_id=3, asignatura="MATEMATICAS", carrera=carrera, nivel=1,
              nota_final=90.0, periodo="P68"),
    ])
    db.add(Intervention(student_id=2, periodo="P68", resultado="Contactado",
                        requiere_seguimiento="no", created_at=dt.datetime(2026, 9, 1)))
    db.commit()


def test_lista_solo_reprobados(client, admin_token, semester_config, data_reprobados):
    r = client.get("/analytics/reprobados?periodo=P68&carrera=MARKETING", headers=auth(admin_token))
    assert r.status_code == 200
    body = r.json()
    ids = {e["student_id"] for e in body["estudiantes"]}
    assert ids == {1, 2}          # el aprobado (3) no aparece
    assert body["kpis"]["total_reprobados"] == 2
    assert body["kpis"]["total_asignaturas_reprobadas"] == 3   # s1: 2, s2: 1


def test_indicadores_y_causa(client, admin_token, semester_config, data_reprobados):
    r = client.get("/analytics/reprobados?periodo=P68&carrera=MARKETING", headers=auth(admin_token))
    body = r.json()
    e1 = next(e for e in body["estudiantes"] if e["student_id"] == 1)
    e2 = next(e for e in body["estudiantes"] if e["student_id"] == 2)
    assert e1["num_reprobadas"] == 2
    assert e1["causa_probable"] == "Desconexión"
    assert e1["sin_intervencion"] is True
    assert e1["prob_desercion"] == 0.7
    assert e2["num_reprobadas"] == 1
    assert e2["causa_probable"] == "Académica"
    assert e2["num_intervenciones"] == 1
    assert e2["sin_intervencion"] is False


def test_sin_resultados_carrera_inexistente(client, admin_token, semester_config, data_reprobados):
    r = client.get("/analytics/reprobados?periodo=P68&carrera=NOEXISTE", headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["estudiantes"] == []
