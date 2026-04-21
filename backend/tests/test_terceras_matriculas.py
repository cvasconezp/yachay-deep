"""
Tests for terceras matrículas (oyentes condicionados) feature.

Covers:
  - Analytics endpoints: list, resumen
  - Dashboard integration: filter, stats count
  - Alert generation for tercera matrícula students
  - ETL loader: load_terceras_matriculas
"""

import pytest
from .conftest import auth
from backend.models import Student, Enrollment, Grade
from backend.models.course_config import SemesterConfig
from backend.models.alert_event import AlertEvent


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def semester_config(db):
    sc = SemesterConfig(semestre="P68", activo=True, bloque_actual="1")
    db.add(sc)
    db.commit()
    return sc


@pytest.fixture
def tm_students(db):
    """Two students: one with tercera matrícula, one without."""
    s1 = Student(
        id=1, nombre="GARCIA JUAN", cedula="0101010101",
        correo_institucional="jgarcia@est.ups.edu.ec",
        carrera="CONTABILIDAD", nivel_riesgo="Alto",
        es_tercera_matricula=True,
    )
    s2 = Student(
        id=2, nombre="PEREZ ANA", cedula="0202020202",
        correo_institucional="aperez@est.ups.edu.ec",
        carrera="DERECHO", nivel_riesgo="Bajo",
        es_tercera_matricula=False,
    )
    db.add_all([s1, s2])
    db.commit()
    return [s1, s2]


@pytest.fixture
def tm_enrollments(db, tm_students):
    """Enrollments: 2 tercera matrícula for student 1, 1 normal for student 2."""
    enrollments = [
        Enrollment(
            student_id=1, codigo_grupo="G001", asignatura="MATEMATICAS",
            codigo_asignatura="MAT-101", carrera="CONTABILIDAD", nivel=3,
            docente="LOPEZ MARIA", pagado="SI", periodo="68",
            es_tercera_matricula=True, tipo_aprobacion="CONDICIONADO",
            estado_solicitud="Aprobado", numero_repitencias=3,
        ),
        Enrollment(
            student_id=1, codigo_grupo="G002", asignatura="ESTADISTICA",
            codigo_asignatura="EST-201", carrera="CONTABILIDAD", nivel=4,
            docente=None, pagado="NO", periodo="68",
            es_tercera_matricula=True, tipo_aprobacion=None,
            estado_solicitud="Trámite", numero_repitencias=3,
        ),
        Enrollment(
            student_id=2, codigo_grupo="G003", asignatura="DERECHO CIVIL",
            codigo_asignatura="DER-301", carrera="DERECHO", nivel=5,
            docente="TORRES CARLOS", pagado="SI", periodo="68",
            es_tercera_matricula=False, numero_repitencias=1,
        ),
    ]
    db.add_all(enrollments)
    db.commit()
    return enrollments


# ── Analytics: /analytics/terceras-matriculas ─────────────────────────────


class TestTercerasMatriculasList:

    def test_returns_only_tm_students(self, client, admin_token, tm_students, tm_enrollments):
        resp = client.get("/analytics/terceras-matriculas", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["student_id"] == 1
        assert data[0]["nombre"] == "GARCIA JUAN"
        assert data[0]["total_asignaturas"] == 2

    def test_asignaturas_detail(self, client, admin_token, tm_students, tm_enrollments):
        resp = client.get("/analytics/terceras-matriculas", headers=auth(admin_token))
        data = resp.json()
        asigs = data[0]["asignaturas"]
        assert len(asigs) == 2
        nombres = {a["asignatura"] for a in asigs}
        assert "MATEMATICAS" in nombres
        assert "ESTADISTICA" in nombres

    def test_pago_pendiente_flag(self, client, admin_token, tm_students, tm_enrollments):
        resp = client.get("/analytics/terceras-matriculas", headers=auth(admin_token))
        data = resp.json()
        # Student 1 has one enrollment with pagado="NO"
        assert data[0]["tiene_pago_pendiente"] is True

    def test_filter_by_carrera(self, client, admin_token, tm_students, tm_enrollments):
        resp = client.get(
            "/analytics/terceras-matriculas?carrera=DERECHO",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json() == []  # student 2 is not tercera matrícula

    def test_empty_returns_empty(self, client, admin_token):
        resp = client.get("/analytics/terceras-matriculas", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_no_auth_returns_401(self, client):
        resp = client.get("/analytics/terceras-matriculas")
        assert resp.status_code == 401


# ── Analytics: /analytics/terceras-matriculas/resumen ─────────────────────


class TestTercerasMatriculasResumen:

    def test_resumen_with_data(self, client, admin_token, tm_students, tm_enrollments):
        resp = client.get("/analytics/terceras-matriculas/resumen", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_estudiantes"] == 1
        assert data["total_asignaturas"] == 2
        assert len(data["por_carrera"]) >= 1
        assert data["por_carrera"][0]["carrera"] == "CONTABILIDAD"

    def test_pago_pendiente_count(self, client, admin_token, tm_students, tm_enrollments):
        resp = client.get("/analytics/terceras-matriculas/resumen", headers=auth(admin_token))
        data = resp.json()
        assert data["con_pago_pendiente"] >= 1

    def test_sin_docente_count(self, client, admin_token, tm_students, tm_enrollments):
        resp = client.get("/analytics/terceras-matriculas/resumen", headers=auth(admin_token))
        data = resp.json()
        # One enrollment has docente=None
        assert data["sin_docente_asignado"] >= 1

    def test_empty_returns_zeros(self, client, admin_token):
        resp = client.get("/analytics/terceras-matriculas/resumen", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_estudiantes"] == 0
        assert data["total_asignaturas"] == 0

    def test_no_auth_returns_401(self, client):
        resp = client.get("/analytics/terceras-matriculas/resumen")
        assert resp.status_code == 401


# ── Dashboard: tercera_matricula filter ──────────────────────────────────


class TestDashboardTMFilter:

    def test_filter_tercera_matricula_true(
        self, client, admin_token, tm_students, tm_enrollments, semester_config
    ):
        resp = client.get(
            "/dashboard/risk?periodo=P68&tercera_matricula=true",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        # Only student 1 (es_tercera_matricula=True, has grades in period via enrollments)
        for s in data:
            assert s["es_tercera_matricula"] is True

    def test_filter_tercera_matricula_false(
        self, client, admin_token, tm_students, tm_enrollments, semester_config
    ):
        resp = client.get(
            "/dashboard/risk?periodo=P68&tercera_matricula=false",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        for s in data:
            assert s["es_tercera_matricula"] is False

    def test_stats_includes_tm_count(
        self, client, admin_token, tm_students, tm_enrollments, semester_config
    ):
        resp = client.get("/dashboard/stats?periodo=P68", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "total_terceras_matriculas" in data
        assert data["total_terceras_matriculas"] >= 1


# ── Alert generation for tercera_matricula ───────────────────────────────


class TestTMAlerts:

    def test_generate_creates_tm_alerts(
        self, client, admin_token, db, tm_students, tm_enrollments, semester_config
    ):
        # Need grade data so _active_period_has_data returns True
        db.add(Grade(student_id=1, asignatura="MATEMATICAS", nota_final=50, periodo="P68"))
        db.commit()
        resp = client.post("/alerts/generate", headers=auth(admin_token))
        assert resp.status_code == 200

        # Check that a tercera_matricula alert was created for student 1
        from backend.models.alert_event import AlertEvent
        alerts = client.get("/alerts/pending", headers=auth(admin_token))
        assert alerts.status_code == 200
        tm_alerts = [a for a in alerts.json() if a["tipo"] == "tercera_matricula"]
        assert len(tm_alerts) >= 1
        assert tm_alerts[0]["severidad"] == "critico"
        assert "tercera matrícula" in tm_alerts[0]["mensaje"].lower()

    def test_no_tm_alert_for_normal_student(
        self, client, admin_token, db, tm_students, tm_enrollments, semester_config
    ):
        db.add(Grade(student_id=1, asignatura="MATEMATICAS", nota_final=50, periodo="P68"))
        db.commit()
        resp = client.post("/alerts/generate", headers=auth(admin_token))
        assert resp.status_code == 200

        alerts = client.get("/alerts/pending", headers=auth(admin_token))
        tm_alerts = [a for a in alerts.json() if a["tipo"] == "tercera_matricula"]
        student_ids = {a["student_id"] for a in tm_alerts}
        # Student 2 should NOT have tercera matrícula alert
        assert 2 not in student_ids


# ── ETL: load_terceras_matriculas ────────────────────────────────────────


class TestLoadTercerasMatriculas:

    def test_load_empty_folder(self, db, tmp_path):
        from backend.etl.terceras_matriculas import load_terceras_matriculas
        result = load_terceras_matriculas(db, str(tmp_path))
        assert result["matched"] == 0
        assert result["enrollments_created"] == 0

    def test_load_nonexistent_folder(self, db):
        from backend.etl.terceras_matriculas import load_terceras_matriculas
        result = load_terceras_matriculas(db, "/nonexistent/path")
        assert result["matched"] == 0

    def test_load_matches_by_cedula(self, db, tmp_path):
        import pandas as pd
        from backend.etl.terceras_matriculas import load_terceras_matriculas

        # Create a student
        s = Student(
            id=1, nombre="TEST STUDENT", cedula="1234567890",
            correo_institucional="test@est.ups.edu.ec",
            carrera="CONTABILIDAD",
        )
        db.add(s)
        db.commit()

        # Create Excel report
        df = pd.DataFrame([{
            "PERIODO": 68,
            "CARRERA": "CONTABILIDAD",
            "IDENTIFICACION_EST": "1234567890",
            "ESTUDIANTE": "TEST STUDENT",
            "COD_ASIGNATURA": "MAT-101",
            "NIVEL": 3,
            "ASIGNATURA": "MATEMATICAS",
            "ESTADO_ACTUAL": "Aprobado",
            "PAGO_MATRICULA": "SI",
            "TIPO_APROBACION": "CONDICIONADO",
            "CORREO_ESTUDIANTE": "test@est.ups.edu.ec",
        }])
        df.to_excel(tmp_path / "test_Reporte.xlsx", index=False)

        result = load_terceras_matriculas(db, str(tmp_path))

        assert result["matched"] == 1
        assert result["unmatched"] == 0
        assert result["enrollments_created"] == 1

        # Verify student is flagged
        db.refresh(s)
        assert s.es_tercera_matricula is True

        # Verify enrollment was created
        enrollment = db.query(Enrollment).filter(
            Enrollment.student_id == 1,
            Enrollment.es_tercera_matricula == True,
        ).first()
        assert enrollment is not None
        assert enrollment.asignatura == "MATEMATICAS"
        assert enrollment.tipo_aprobacion == "CONDICIONADO"
        assert enrollment.estado_solicitud == "Aprobado"
        assert enrollment.numero_repitencias == 3

    def test_load_matches_by_email(self, db, tmp_path):
        import pandas as pd
        from backend.etl.terceras_matriculas import load_terceras_matriculas

        s = Student(
            id=1, nombre="OTRO STUDENT",
            correo_institucional="otro@est.ups.edu.ec",
            carrera="DERECHO",
        )
        db.add(s)
        db.commit()

        df = pd.DataFrame([{
            "PERIODO": 68,
            "CARRERA": "DERECHO",
            "IDENTIFICACION_EST": "",
            "ESTUDIANTE": "OTRO STUDENT",
            "COD_ASIGNATURA": "DER-301",
            "ASIGNATURA": "DERECHO CIVIL",
            "ESTADO_ACTUAL": "Aprobado",
            "PAGO_MATRICULA": "NO",
            "CORREO_ESTUDIANTE": "otro@est.ups.edu.ec",
        }])
        df.to_excel(tmp_path / "reporte.xlsx", index=False)

        result = load_terceras_matriculas(db, str(tmp_path))
        assert result["matched"] == 1

    def test_unmatched_student(self, db, tmp_path):
        import pandas as pd
        from backend.etl.terceras_matriculas import load_terceras_matriculas

        df = pd.DataFrame([{
            "PERIODO": 68,
            "CARRERA": "CONTABILIDAD",
            "IDENTIFICACION_EST": "9999999999",
            "ESTUDIANTE": "NO EXISTE",
            "COD_ASIGNATURA": "MAT-101",
            "ASIGNATURA": "MATEMATICAS",
            "ESTADO_ACTUAL": "Aprobado",
            "CORREO_ESTUDIANTE": "noexiste@test.com",
        }])
        df.to_excel(tmp_path / "reporte.xlsx", index=False)

        result = load_terceras_matriculas(db, str(tmp_path))
        assert result["matched"] == 0
        assert result["unmatched"] == 1
        assert "NO EXISTE" in result["unmatched_names"]

    def test_updates_existing_enrollment(self, db, tmp_path):
        import pandas as pd
        from backend.etl.terceras_matriculas import load_terceras_matriculas

        s = Student(id=1, nombre="TEST", cedula="1111111111", carrera="CONTABILIDAD")
        db.add(s)

        # Pre-existing enrollment
        e = Enrollment(
            student_id=1, codigo_grupo="G001", codigo_asignatura="MAT-101",
            asignatura="MATEMATICAS", periodo="68", pagado="NO",
        )
        db.add(e)
        db.commit()

        df = pd.DataFrame([{
            "PERIODO": 68,
            "IDENTIFICACION_EST": "1111111111",
            "ESTUDIANTE": "TEST",
            "COD_ASIGNATURA": "MAT-101",
            "ASIGNATURA": "MATEMATICAS",
            "ESTADO_ACTUAL": "Aprobado",
            "PAGO_MATRICULA": "SI",
            "TIPO_APROBACION": "CONDICIONADO",
            "CORREO_ESTUDIANTE": "test@test.com",
        }])
        df.to_excel(tmp_path / "reporte.xlsx", index=False)

        result = load_terceras_matriculas(db, str(tmp_path))
        assert result["enrollments_updated"] == 1
        assert result["enrollments_created"] == 0

        db.refresh(e)
        assert e.es_tercera_matricula is True
        assert e.tipo_aprobacion == "CONDICIONADO"
        assert e.pagado == "SI"

    def test_generates_alerts(self, db, tmp_path):
        import pandas as pd
        from backend.etl.terceras_matriculas import load_terceras_matriculas

        s = Student(id=1, nombre="TEST", cedula="1111111111", carrera="CONTABILIDAD")
        db.add(s)
        db.commit()

        df = pd.DataFrame([{
            "PERIODO": 68,
            "IDENTIFICACION_EST": "1111111111",
            "ESTUDIANTE": "TEST",
            "COD_ASIGNATURA": "MAT-101",
            "ASIGNATURA": "MATEMATICAS",
            "ESTADO_ACTUAL": "Aprobado",
            "CORREO_ESTUDIANTE": "test@test.com",
        }])
        df.to_excel(tmp_path / "reporte.xlsx", index=False)

        result = load_terceras_matriculas(db, str(tmp_path))
        assert result["alerts_created"] >= 1

        alert = db.query(AlertEvent).filter(
            AlertEvent.student_id == 1,
            AlertEvent.tipo == "tercera_matricula",
        ).first()
        assert alert is not None
        assert alert.severidad == "critico"
