"""
Tests para endpoints de resumen y entregas.

Cubre:
  - /analytics/periodos — períodos disponibles
  - /analytics/resumen — estadísticas globales con filtros
  - /analytics/resumen/estudiantes-listado — listados por tipo
  - /analytics/entregas-pendientes — actividades con entregas pendientes
  - /analytics/entregas-resumen — resumen compacto por curso
"""
import pytest
from datetime import date

from .conftest import auth
from backend.models import Student, Grade, Enrollment
from backend.models.course_config import SemesterConfig, CourseConfig
from backend.models.task_submission import TaskSubmission
from backend.models.avac_access import AvacAccess


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def semester_config(db):
    sc = SemesterConfig(semestre="P68", activo=True, bloque_actual="1")
    db.add(sc)
    db.commit()
    return sc


@pytest.fixture
def sample_students(db):
    students = [
        Student(id=1, nombre="ALUMNO UNO", carrera="EDUCACION BASICA",
                nivel_riesgo="Alto", indice_compromiso=0.2, estado_matricula="Matriculado"),
        Student(id=2, nombre="ALUMNO DOS", carrera="EDUCACION BASICA",
                nivel_riesgo="Bajo", indice_compromiso=0.8, estado_matricula="Matriculado"),
    ]
    db.add_all(students)
    db.commit()
    return students


@pytest.fixture
def sample_grades(db, sample_students, semester_config):
    grades = [
        Grade(student_id=1, asignatura="MATEMATICAS", docente="GARCIA JUAN",
              carrera="EDUCACION BASICA", nota_final=55, periodo="P68",
              numero_repitencias=2),
        Grade(student_id=2, asignatura="MATEMATICAS", docente="GARCIA JUAN",
              carrera="EDUCACION BASICA", nota_final=85, periodo="P68"),
    ]
    db.add_all(grades)
    db.commit()
    return grades


@pytest.fixture
def sample_tasks(db, sample_students, semester_config):
    cc = CourseConfig(
        codigo_avac="COURSE1", asignatura="MATEMATICAS",
        docente="GARCIA JUAN", carrera="EDUCACION BASICA",
        semestre="P68", bloque="1", activo=True,
    )
    db.add(cc)
    # Also add enrollment so bloque whitelist can find the course
    enr = Enrollment(
        student_id=1, asignatura="MATEMATICAS", docente="GARCIA JUAN",
        carrera="EDUCACION BASICA", periodo="P68", codigo_grupo="COURSE1",
        bloque=1,
    )
    db.add(enr)
    tasks = [
        TaskSubmission(student_id=1, codigo_curso="COURSE1", unidad="1",
                       entregada=False, calificada=False, periodo="P68",
                       snapshot_date=date.today()),
        TaskSubmission(student_id=2, codigo_curso="COURSE1", unidad="1",
                       entregada=True, calificada=True, periodo="P68",
                       snapshot_date=date.today()),
    ]
    db.add_all(tasks)
    db.commit()
    return tasks


# ── TestPeriodos ──────────────────────────────────────────────────────

class TestPeriodos:
    def test_includes_grade_periodo(self, client, admin_token, sample_grades):
        """Grades con periodo=P68 hace que P68 aparezca en la lista."""
        resp = client.get("/analytics/periodos", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        keys = [p["key"] for p in data["periodos"]]
        assert "P68" in keys

    def test_empty_db_returns_minimal(self, client, admin_token, semester_config):
        """Sin grades, solo aparece el semestre configurado."""
        resp = client.get("/analytics/periodos", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "periodos" in data
        assert "default" in data
        # Al menos el semestre activo debe aparecer
        keys = [p["key"] for p in data["periodos"]]
        assert "P68" in keys


# ── TestResumen ───────────────────────────────────────────────────────

class TestResumen:
    def test_with_sample_data(self, client, admin_token, sample_grades):
        """Con datos de muestra, devuelve estadísticas globales."""
        resp = client.get("/analytics/resumen?periodo=P68", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["tiene_datos_periodo"] is True
        g = data["global"]
        assert g["total_estudiantes"] == 2
        assert g["total_secciones"] >= 1
        assert g["promedio_calificaciones"] is not None

    def test_carrera_filter(self, client, admin_token, sample_grades):
        """Filtro de carrera limita los resultados."""
        resp = client.get(
            "/analytics/resumen?periodo=P68&carrera=EDUCACION",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tiene_datos_periodo"] is True
        assert data["global"]["total_estudiantes"] == 2

    def test_empty_db_no_data(self, client, admin_token, semester_config):
        """Sin grades ni enrollments, tiene_datos_periodo es false."""
        resp = client.get("/analytics/resumen?periodo=P68", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["tiene_datos_periodo"] is False

    def test_no_auth_returns_401(self, client):
        """Sin token, devuelve 401."""
        resp = client.get("/analytics/resumen?periodo=P68")
        assert resp.status_code in (401, 403)

    def test_repitentes_count(self, client, admin_token, sample_grades):
        """Cuenta correcta de repitentes (numero_repitencias > 1)."""
        resp = client.get("/analytics/resumen?periodo=P68", headers=auth(admin_token))
        data = resp.json()
        assert data["global"]["repitentes"] == 1

    def test_reprobados_count(self, client, admin_token, sample_grades):
        """Alumno con nota 55 < 70 (default) cuenta como reprobado."""
        resp = client.get("/analytics/resumen?periodo=P68", headers=auth(admin_token))
        data = resp.json()
        assert data["global"]["reprobados"] == 1


# ── TestEstudiantesListado ────────────────────────────────────────────

class TestEstudiantesListado:
    def test_repitentes(self, client, admin_token, sample_grades):
        """tipo=repitentes devuelve estudiantes con numero_repitencias > 1."""
        resp = client.get(
            "/analytics/resumen/estudiantes-listado?tipo=repitentes&periodo=P68",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tipo"] == "repitentes"
        assert data["total"] >= 1
        names = [e["nombre"] for e in data["estudiantes"]]
        assert "ALUMNO UNO" in names

    def test_riesgo_alto(self, client, admin_token, sample_grades):
        """tipo=riesgo_alto devuelve estudiantes con nivel_riesgo=Alto."""
        resp = client.get(
            "/analytics/resumen/estudiantes-listado?tipo=riesgo_alto&periodo=P68",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tipo"] == "riesgo_alto"
        assert data["total"] >= 1
        names = [e["nombre"] for e in data["estudiantes"]]
        assert "ALUMNO UNO" in names
        assert "ALUMNO DOS" not in names

    def test_invalid_tipo(self, client, admin_token, sample_grades):
        """tipo=invalid devuelve error message."""
        resp = client.get(
            "/analytics/resumen/estudiantes-listado?tipo=invalid&periodo=P68",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data
        assert data["total"] == 0

    def test_no_auth_returns_401(self, client):
        """Sin token, devuelve 401."""
        resp = client.get(
            "/analytics/resumen/estudiantes-listado?tipo=repitentes&periodo=P68"
        )
        assert resp.status_code in (401, 403)


# ── TestEntregasPendientes ────────────────────────────────────────────

class TestEntregasPendientes:
    def test_with_task_data(self, client, admin_token, sample_tasks):
        """Con TaskSubmission data, devuelve actividades con conteos."""
        resp = client.get(
            "/analytics/entregas-pendientes",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "actividades" in data
        assert "resumen" in data
        acts = data["actividades"]
        assert len(acts) >= 1
        act = acts[0]
        assert act["total_estudiantes"] == 2
        assert act["entregaron"] == 1
        assert act["no_entregaron"] == 1

    def test_no_data_returns_empty(self, client, admin_token, semester_config):
        """Sin datos de entregas, devuelve lista vacía."""
        resp = client.get(
            "/analytics/entregas-pendientes",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["actividades"] == []
        assert data["resumen"]["total_actividades"] == 0

    def test_no_auth_returns_401(self, client):
        """Sin token, devuelve 401."""
        resp = client.get("/analytics/entregas-pendientes")
        assert resp.status_code in (401, 403)


# ── TestEntregasResumen ───────────────────────────────────────────────

class TestEntregasResumen:
    def test_with_data(self, client, admin_token, sample_tasks):
        """Con datos, devuelve cursos con unidades."""
        resp = client.get(
            "/analytics/entregas-resumen",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "cursos" in data
        cursos = data["cursos"]
        assert len(cursos) >= 1
        curso = cursos[0]
        assert "unidades" in curso
        assert "1" in curso["unidades"]
        uni = curso["unidades"]["1"]
        assert uni["total"] == 2
        assert uni["entregadas"] == 1
        assert uni["pct"] == 50.0

    def test_no_data_returns_empty(self, client, admin_token, semester_config):
        """Sin datos, devuelve cursos vacío."""
        resp = client.get(
            "/analytics/entregas-resumen",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["cursos"] == []

    def test_no_auth_returns_401(self, client):
        """Sin token, devuelve 401."""
        resp = client.get("/analytics/entregas-resumen")
        assert resp.status_code in (401, 403)


# ── TestEdgeCases ─────────────────────────────────────────────────────

class TestEdgeCases:
    def test_resumen_unknown_periodo(self, client, admin_token, semester_config):
        """Periodo inexistente devuelve tiene_datos_periodo=false."""
        resp = client.get("/analytics/resumen?periodo=P99", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["tiene_datos_periodo"] is False

    def test_resumen_nonexistent_carrera(self, client, admin_token, sample_grades):
        """Carrera que no existe devuelve stats vacíos."""
        resp = client.get(
            "/analytics/resumen?periodo=P68&carrera=INEXISTENTE",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["global"] == {} or data["global"].get("total_estudiantes", 0) == 0

    def test_entregas_pendientes_bloque_filter(self, client, admin_token, sample_tasks):
        """Filtro de bloque=1 funciona sin error."""
        resp = client.get(
            "/analytics/entregas-pendientes?bloque=1",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200

    def test_entregas_pendientes_carrera_filter(self, client, admin_token, sample_tasks):
        """Filtro de carrera funciona."""
        resp = client.get(
            "/analytics/entregas-pendientes?carrera=EDUCACION",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["actividades"]) >= 1

    def test_listado_riesgo_bajo(self, client, admin_token, sample_grades):
        """tipo=riesgo_bajo devuelve solo estudiantes con riesgo Bajo."""
        resp = client.get(
            "/analytics/resumen/estudiantes-listado?tipo=riesgo_bajo&periodo=P68",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tipo"] == "riesgo_bajo"
        for est in data["estudiantes"]:
            assert est["nivel_riesgo"] == "Bajo"

    def test_entregas_resumen_carrera_filter(self, client, admin_token, sample_tasks):
        """Filtro de carrera en entregas-resumen funciona."""
        resp = client.get(
            "/analytics/entregas-resumen?carrera=EDUCACION",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert len(resp.json()["cursos"]) >= 1

    def test_entregas_resumen_wrong_carrera_empty(self, client, admin_token, sample_tasks):
        """Carrera inexistente en entregas-resumen devuelve vacío."""
        resp = client.get(
            "/analytics/entregas-resumen?carrera=INEXISTENTE",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["cursos"] == []
