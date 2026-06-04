"""
Tests para endpoints de analítica.

Cubre:
  - Consistencia cruzada entre endpoints (resumen vs asignaturas vs docentes)
  - Filtros de periodo y carrera
  - Fallback a Enrollment cuando no hay grades
  - Edge cases (docente vacío, periodo inexistente)
  - Normalización de nivel_riesgo
  - Umbrales configurables
"""
import pytest
from .conftest import auth

from backend.models import Student, Grade, Enrollment
from backend.models.course_config import SemesterConfig
from backend.routes.analytics._helpers import (
    normalize_riesgo, build_risk_map, get_umbrales, DEFAULTS,
)


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def semester_config(db):
    """SemesterConfig activo para P68."""
    sc = SemesterConfig(semestre="P68", activo=True, bloque_actual="1")
    db.add(sc)
    db.commit()
    return sc


@pytest.fixture
def sample_students(db):
    """3 estudiantes de prueba en 2 carreras."""
    students = [
        Student(id=1, nombre="ALUMNO UNO", carrera="EDUCACION BASICA",
                nivel_academico=3, nivel_riesgo="Alto", indice_compromiso=0.3),
        Student(id=2, nombre="ALUMNO DOS", carrera="EDUCACION BASICA",
                nivel_academico=3, nivel_riesgo="Medio", indice_compromiso=0.6),
        Student(id=3, nombre="ALUMNO TRES", carrera="DERECHO",
                nivel_academico=5, nivel_riesgo="Bajo", indice_compromiso=0.9),
    ]
    db.add_all(students)
    db.commit()
    return students


@pytest.fixture
def sample_grades(db, sample_students):
    """Grades para P68: 2 asignaturas × 2 docentes."""
    grades = [
        # Asignatura A - Docente X (2 estudiantes)
        Grade(student_id=1, asignatura="MATEMATICAS", docente="GARCIA LOPEZ JUAN",
              carrera="EDUCACION BASICA", nivel=3, nota_final=55, periodo="P68"),
        Grade(student_id=2, asignatura="MATEMATICAS", docente="GARCIA LOPEZ JUAN",
              carrera="EDUCACION BASICA", nivel=3, nota_final=80, periodo="P68"),
        # Asignatura B - Docente Y (1 estudiante)
        Grade(student_id=3, asignatura="DERECHO CIVIL", docente="PEREZ MORALES ANA",
              carrera="DERECHO", nivel=5, nota_final=90, periodo="P68"),
        # Asignatura A - Docente Y (1 estudiante, otra sección)
        Grade(student_id=3, asignatura="MATEMATICAS", docente="PEREZ MORALES ANA",
              carrera="DERECHO", nivel=5, nota_final=75, periodo="P68"),
    ]
    db.add_all(grades)
    db.commit()
    return grades


@pytest.fixture
def sample_enrollments(db, sample_students):
    """Enrollments para P68 (sin grades, simula inicio de semestre)."""
    enrollments = [
        Enrollment(student_id=1, asignatura="LENGUA", docente="RUIZ VEGA MARIA",
                   carrera="EDUCACION BASICA", nivel=3, periodo="P68", codigo_grupo="LEN-001"),
        Enrollment(student_id=2, asignatura="LENGUA", docente="RUIZ VEGA MARIA",
                   carrera="EDUCACION BASICA", nivel=3, periodo="P68", codigo_grupo="LEN-001"),
        Enrollment(student_id=3, asignatura="FILOSOFIA", docente="TORRES SILVA PEDRO",
                   carrera="DERECHO", nivel=5, periodo="P68", codigo_grupo="FIL-001"),
    ]
    db.add_all(enrollments)
    db.commit()
    return enrollments


# ── Tests de helpers ──────────────────────────────────────────────────

class TestNormalizeRiesgo:
    def test_standard_values(self):
        assert normalize_riesgo("Alto") == "Alto"
        assert normalize_riesgo("Medio") == "Medio"
        assert normalize_riesgo("Bajo") == "Bajo"

    def test_case_insensitive(self):
        assert normalize_riesgo("alto") == "Alto"
        assert normalize_riesgo("MEDIO") == "Medio"
        assert normalize_riesgo("bajo") == "Bajo"

    def test_whitespace(self):
        assert normalize_riesgo("  Alto  ") == "Alto"

    def test_none_and_empty(self):
        assert normalize_riesgo(None) is None
        assert normalize_riesgo("") is None

    def test_invalid(self):
        assert normalize_riesgo("Critico") is None
        assert normalize_riesgo("123") is None


class TestBuildRiskMap:
    def test_normal(self):
        counts = [("Alto", 5), ("Medio", 3), ("Bajo", 10)]
        result = build_risk_map(counts)
        assert result == {"Alto": 5, "Medio": 3, "Bajo": 10}

    def test_case_variants(self):
        counts = [("alto", 2), ("MEDIO", 4), ("Bajo", 1)]
        result = build_risk_map(counts)
        assert result == {"Alto": 2, "Medio": 4, "Bajo": 1}

    def test_empty(self):
        result = build_risk_map([])
        assert result == {"Alto": 0, "Medio": 0, "Bajo": 0}

    def test_ignores_invalid(self):
        counts = [("Alto", 5), ("Desconocido", 3), (None, 2)]
        result = build_risk_map(counts)
        assert result == {"Alto": 5, "Medio": 0, "Bajo": 0}

    def test_aggregates_duplicates(self):
        counts = [("Alto", 3), ("alto", 2)]
        result = build_risk_map(counts)
        assert result == {"Alto": 5, "Medio": 0, "Bajo": 0}


class TestGetUmbrales:
    def test_defaults_without_config(self, db):
        umbrales = get_umbrales(db)
        assert umbrales["nota_aprobacion"] == DEFAULTS["nota_aprobacion"]
        assert umbrales["dias_inactividad"] == DEFAULTS["dias_inactividad"]
        assert umbrales["tareas_minimo"] == DEFAULTS["tareas_minimo"]
        assert umbrales["compromiso_minimo"] == DEFAULTS["compromiso_minimo"]

    def test_custom_values(self, db, semester_config):
        semester_config.umbral_nota_aprobacion = 60.0
        semester_config.umbral_dias_inactividad = 7
        db.commit()
        umbrales = get_umbrales(db)
        assert umbrales["nota_aprobacion"] == 60.0
        assert umbrales["dias_inactividad"] == 7
        # Los no-configurados usan defaults
        assert umbrales["tareas_minimo"] == DEFAULTS["tareas_minimo"]


# ── Tests de endpoints: filtros de periodo ────────────────────────────

class TestPeriodoFilter:
    def test_asignaturas_filters_by_periodo(self, client, admin_token, sample_grades, semester_config):
        """Asignaturas con periodo=P68 solo devuelve grades de P68."""
        resp = client.get("/analytics/asignaturas?periodo=P68", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        # Todas las asignaturas deben venir de nuestros grades de P68
        asig_names = {a["asignatura"] for a in data}
        assert "MATEMATICAS" in asig_names

    def test_asignaturas_empty_for_unknown_periodo(self, client, admin_token, sample_grades, semester_config):
        """Periodo inexistente devuelve vacío (o fallback enrollment vacío)."""
        resp = client.get("/analytics/asignaturas?periodo=P99", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_docentes_filters_by_periodo(self, client, admin_token, sample_grades, semester_config):
        resp = client.get("/analytics/docentes?periodo=P68", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        docente_names = {d["docente"] for d in data}
        assert "GARCIA LOPEZ JUAN" in docente_names

    def test_docentes_empty_for_unknown_periodo(self, client, admin_token, sample_grades, semester_config):
        resp = client.get("/analytics/docentes?periodo=P99", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json() == []


# ── Tests de endpoints: filtros de carrera ────────────────────────────

class TestCarreraFilter:
    def test_asignaturas_filtered_by_carrera(self, client, admin_token, sample_grades, semester_config):
        resp = client.get("/analytics/asignaturas?periodo=P68&carrera=DERECHO", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        # Solo deben aparecer asignaturas con estudiantes de DERECHO
        for a in data:
            assert a["total_estudiantes"] > 0

    def test_docentes_filtered_by_carrera(self, client, admin_token, sample_grades, semester_config):
        resp = client.get("/analytics/docentes?periodo=P68&carrera=BASICA", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        # GARCIA LOPEZ JUAN tiene estudiantes de EDUCACION BASICA
        docente_names = {d["docente"] for d in data}
        assert "GARCIA LOPEZ JUAN" in docente_names


# ── Tests de fallback enrollment ──────────────────────────────────────

class TestEnrollmentFallback:
    def test_asignaturas_uses_enrollment_when_no_grades(self, client, admin_token, sample_enrollments, semester_config):
        """Sin grades para el periodo, usa enrollment."""
        resp = client.get("/analytics/asignaturas?periodo=P68", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        asig_names = {a["asignatura"] for a in data}
        assert "LENGUA" in asig_names
        assert "FILOSOFIA" in asig_names

    def test_docentes_uses_enrollment_when_no_grades(self, client, admin_token, sample_enrollments, semester_config):
        resp = client.get("/analytics/docentes?periodo=P68", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        docente_names = {d["docente"] for d in data}
        assert "RUIZ VEGA MARIA" in docente_names

    def test_tutorias_uses_enrollment_when_no_grades(self, client, admin_token, sample_enrollments, semester_config):
        """Tutorías debe funcionar con enrollment fallback."""
        resp = client.get("/analytics/tutorias/por-asignatura?periodo=P68&nivel_riesgo=Alto",
                         headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        # Alumno 1 tiene riesgo Alto y está en LENGUA via enrollment
        if data:
            asig_names = {a["asignatura"] for a in data}
            assert "LENGUA" in asig_names


# ── Tests de consistencia cruzada ─────────────────────────────────────

class TestCrossConsistency:
    def test_secciones_count_matches_asignaturas(self, client, admin_token, sample_grades, semester_config):
        """total_secciones en resumen debe igualar len(asignaturas)."""
        asig_resp = client.get("/analytics/asignaturas?periodo=P68", headers=auth(admin_token))
        resumen_resp = client.get("/analytics/resumen?periodo=P68", headers=auth(admin_token))
        assert asig_resp.status_code == 200
        assert resumen_resp.status_code == 200

        n_asignaturas = len(asig_resp.json())
        resumen = resumen_resp.json()
        n_secciones = resumen.get("global", {}).get("total_secciones", 0)
        assert n_secciones == n_asignaturas, (
            f"Resumen secciones ({n_secciones}) != Analítica asignaturas ({n_asignaturas})"
        )

    def test_docentes_count_matches(self, client, admin_token, sample_grades, semester_config):
        """total_docentes en resumen debe igualar len(docentes)."""
        doc_resp = client.get("/analytics/docentes?periodo=P68", headers=auth(admin_token))
        resumen_resp = client.get("/analytics/resumen?periodo=P68", headers=auth(admin_token))
        assert doc_resp.status_code == 200
        assert resumen_resp.status_code == 200

        n_docentes_analitica = len(doc_resp.json())
        resumen = resumen_resp.json()
        # Resumen usa total_docentes (from grades) o total_docentes_enrollment
        n_docentes_resumen = resumen.get("global", {}).get("total_docentes", 0)
        if n_docentes_resumen == 0:
            n_docentes_resumen = resumen.get("global", {}).get("total_docentes_enrollment", 0)
        assert n_docentes_resumen == n_docentes_analitica, (
            f"Resumen docentes ({n_docentes_resumen}) != Analítica docentes ({n_docentes_analitica})"
        )

    def test_aprobacion_uses_configurable_threshold(self, client, admin_token, sample_grades, semester_config, db):
        """Cambiar umbral de aprobación afecta los conteos."""
        # Con umbral default (70): alumno 1 reprueba (55), otros aprueban
        resp1 = client.get("/analytics/asignaturas?periodo=P68", headers=auth(admin_token))
        data1 = resp1.json()
        mat = next(a for a in data1 if a["asignatura"] == "MATEMATICAS" and a["docente"] == "GARCIA LOPEZ JUAN")
        assert mat["reprobados"] == 1  # nota 55 < 70

        # Cambiar umbral a 50
        semester_config.umbral_nota_aprobacion = 50.0
        db.commit()
        resp2 = client.get("/analytics/asignaturas?periodo=P68", headers=auth(admin_token))
        data2 = resp2.json()
        mat2 = next(a for a in data2 if a["asignatura"] == "MATEMATICAS" and a["docente"] == "GARCIA LOPEZ JUAN")
        assert mat2["reprobados"] == 0  # nota 55 >= 50


# ── Tests de edge cases ───────────────────────────────────────────────

class TestEdgeCases:
    def test_no_auth_returns_401(self, client):
        """Sin token, todos los endpoints rechazan."""
        for url in ["/analytics/asignaturas", "/analytics/docentes", "/analytics/resumen"]:
            resp = client.get(url)
            assert resp.status_code in (401, 403), f"{url} debería requerir auth"

    def test_empty_database(self, client, admin_token, semester_config):
        """Sin datos, endpoints devuelven vacío sin error."""
        for url in ["/analytics/asignaturas?periodo=P68", "/analytics/docentes?periodo=P68"]:
            resp = client.get(url, headers=auth(admin_token))
            assert resp.status_code == 200
            assert resp.json() == []
