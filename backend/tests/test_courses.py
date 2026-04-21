"""
Tests for course configuration and semester management endpoints.

Covers CRUD operations on courses, bulk creation, deduplication,
and semester lifecycle (create, activate, set bloque, delete).
"""
import pytest
from .conftest import auth
from backend.models.course_config import CourseConfig, SemesterConfig


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_courses(db):
    courses = [
        CourseConfig(
            codigo_avac="100001", asignatura="MATEMATICAS",
            carrera="EDUCACION BASICA", docente="GARCIA JUAN",
            semestre="P68", activo=True,
        ),
        CourseConfig(
            codigo_avac="100002", asignatura="LENGUA",
            carrera="EDUCACION BASICA", docente="PEREZ ANA",
            semestre="P68", activo=True,
        ),
    ]
    db.add_all(courses)
    db.commit()
    return courses


@pytest.fixture
def semester_config(db):
    sc = SemesterConfig(semestre="P68", activo=True, bloque_actual="1")
    db.add(sc)
    db.commit()
    return sc


# ─── Course CRUD ─────────────────────────────────────────────────────────────


class TestListCourses:
    def test_list_returns_courses(self, client, admin_token, sample_courses):
        resp = client.get("/courses/", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        codigos = {c["codigo_avac"] for c in data}
        assert codigos == {"100001", "100002"}

    def test_filter_by_semestre(self, client, admin_token, db, sample_courses):
        extra = CourseConfig(
            codigo_avac="200001", asignatura="FISICA",
            carrera="INGENIERIA", semestre="P69", activo=True,
        )
        db.add(extra)
        db.commit()
        resp = client.get("/courses/?semestre=P68", headers=auth(admin_token))
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_filter_by_activo(self, client, admin_token, db, sample_courses):
        sample_courses[0].activo = False
        db.commit()
        resp = client.get("/courses/?activo=true", headers=auth(admin_token))
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["codigo_avac"] == "100002"

    def test_no_auth_returns_401(self, client):
        resp = client.get("/courses/")
        assert resp.status_code == 401


class TestCreateCourse:
    def test_create_valid(self, client, admin_token):
        payload = {
            "codigo_avac": "123456",
            "asignatura": "MATEMATICAS",
            "carrera": "EDUCACION",
            "docente": "GARCIA",
        }
        resp = client.post("/courses/", json=payload, headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["codigo_avac"] == "123456"
        assert data["asignatura"] == "MATEMATICAS"
        assert "id" in data

    def test_monitor_forbidden(self, client, monitor_token):
        payload = {"codigo_avac": "999999"}
        resp = client.post("/courses/", json=payload, headers=auth(monitor_token))
        assert resp.status_code == 403

    def test_no_auth_returns_401(self, client):
        resp = client.post("/courses/", json={"codigo_avac": "111111"})
        assert resp.status_code == 401


class TestBulkCreate:
    def test_bulk_create_new(self, client, admin_token):
        courses = [
            {"codigo_avac": "300001", "asignatura": "QUIMICA"},
            {"codigo_avac": "300002", "asignatura": "BIOLOGIA"},
        ]
        resp = client.post("/courses/bulk", json=courses, headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 2
        assert data["updated"] == 0
        assert data["total"] == 2

    def test_bulk_upsert_existing(self, client, admin_token, sample_courses):
        courses = [
            {"codigo_avac": "100001", "asignatura": "MATEMATICAS AVANZADAS"},
            {"codigo_avac": "400001", "asignatura": "HISTORIA"},
        ]
        resp = client.post("/courses/bulk", json=courses, headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 1
        assert data["updated"] == 1
        assert data["total"] == 2

    def test_bulk_monitor_forbidden(self, client, monitor_token):
        resp = client.post("/courses/bulk", json=[], headers=auth(monitor_token))
        assert resp.status_code == 403


class TestUpdateCourse:
    def test_update_valid(self, client, admin_token, sample_courses):
        cid = sample_courses[0].id
        resp = client.patch(
            f"/courses/{cid}",
            json={"asignatura": "ALGEBRA LINEAL"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["asignatura"] == "ALGEBRA LINEAL"

    def test_update_not_found(self, client, admin_token):
        resp = client.patch(
            "/courses/99999",
            json={"asignatura": "X"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 404

    def test_update_monitor_forbidden(self, client, monitor_token, sample_courses):
        cid = sample_courses[0].id
        resp = client.patch(
            f"/courses/{cid}",
            json={"asignatura": "NOPE"},
            headers=auth(monitor_token),
        )
        assert resp.status_code == 403


class TestDeleteCourse:
    def test_delete_valid(self, client, admin_token, sample_courses):
        cid = sample_courses[0].id
        resp = client.delete(f"/courses/{cid}", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_delete_not_found(self, client, admin_token):
        resp = client.delete("/courses/99999", headers=auth(admin_token))
        assert resp.status_code == 404


class TestDeduplicate:
    def test_deduplicate_with_duplicates(self, client, admin_token, db):
        for i in range(3):
            db.add(CourseConfig(codigo_avac="DUP001", asignatura=f"COURSE_{i}", semestre="P68"))
        db.add(CourseConfig(codigo_avac="UNIQUE", asignatura="UNICA", semestre="P68"))
        db.commit()
        resp = client.post("/courses/deduplicate", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["removed"] == 2
        assert data["total_remaining"] == 2  # 1 kept from DUP001 + UNIQUE

    def test_deduplicate_no_duplicates(self, client, admin_token, sample_courses):
        resp = client.post("/courses/deduplicate", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["removed"] == 0


# ─── Semester Endpoints ──────────────────────────────────────────────────────


class TestActiveSemester:
    def test_get_active_semester(self, client, admin_token, semester_config):
        resp = client.get("/courses/semester/active", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["semestre"] == "P68"
        assert data["activo"] is True

    def test_no_active_semester_returns_null(self, client, admin_token):
        resp = client.get("/courses/semester/active", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json() is None

    def test_no_auth_returns_401(self, client):
        resp = client.get("/courses/semester/active")
        assert resp.status_code == 401


class TestCreateSemester:
    def test_create_valid(self, client, admin_token):
        payload = {"semestre": "P69", "bloque_actual": "1"}
        resp = client.post("/courses/semester/", json=payload, headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["semestre"] == "P69"
        assert data["bloque_actual"] == "1"
        assert data["activo"] is False

    def test_create_monitor_forbidden(self, client, monitor_token):
        resp = client.post(
            "/courses/semester/",
            json={"semestre": "P70"},
            headers=auth(monitor_token),
        )
        assert resp.status_code == 403


class TestActivateSemester:
    def test_activate_valid(self, client, admin_token, db):
        s1 = SemesterConfig(semestre="P68", activo=True, bloque_actual="1")
        s2 = SemesterConfig(semestre="P69", activo=False, bloque_actual="1")
        db.add_all([s1, s2])
        db.commit()
        resp = client.post("/courses/semester/P69/activate", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["activated"] == "P69"
        # Verify old one is deactivated
        db.expire_all()
        assert db.query(SemesterConfig).filter_by(semestre="P68").first().activo is False
        assert db.query(SemesterConfig).filter_by(semestre="P69").first().activo is True

    def test_activate_not_found(self, client, admin_token):
        resp = client.post("/courses/semester/NOEXIST/activate", headers=auth(admin_token))
        assert resp.status_code == 404


class TestSetBloque:
    def test_set_bloque_valid(self, client, admin_token, semester_config):
        resp = client.post(
            "/courses/semester/P68/bloque",
            json={"bloque": "2"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["bloque_actual"] == "2"
        assert data["semestre"] == "P68"

    def test_set_bloque_not_found(self, client, admin_token):
        resp = client.post(
            "/courses/semester/NOEXIST/bloque",
            json={"bloque": "1"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 404


class TestDeleteSemester:
    def test_delete_active_returns_400(self, client, admin_token, semester_config):
        resp = client.delete("/courses/semester/P68", headers=auth(admin_token))
        assert resp.status_code == 400
        assert "activo" in resp.json()["detail"].lower()

    def test_delete_inactive_ok(self, client, admin_token, db):
        sc = SemesterConfig(semestre="P67", activo=False, bloque_actual="1")
        db.add(sc)
        db.commit()
        resp = client.delete("/courses/semester/P67", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["deleted"] == "P67"

    def test_delete_not_found(self, client, admin_token):
        resp = client.delete("/courses/semester/NOEXIST", headers=auth(admin_token))
        assert resp.status_code == 404
