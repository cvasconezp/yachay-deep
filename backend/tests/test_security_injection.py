"""
T29: Tests de inyección SQL y validación de inputs.

Verifica que la API resiste:
  - SQL injection en parámetros de búsqueda
  - Path traversal en IDs
  - Payloads excesivamente largos
  - Caracteres especiales en filtros
"""
import pytest
from backend.tests.conftest import auth


# ── SQL Injection en búsqueda de estudiantes ──

class TestSQLInjection:
    """Intentos de SQL injection en endpoints de búsqueda."""

    SQL_PAYLOADS = [
        "' OR '1'='1",
        "'; DROP TABLE students; --",
        "1 UNION SELECT * FROM users --",
        "' OR 1=1 --",
        "admin'--",
        "1; UPDATE users SET role='admin' WHERE 1=1;--",
        "' UNION ALL SELECT NULL,NULL,email,hashed_password FROM users--",
    ]

    @pytest.mark.parametrize("payload", SQL_PAYLOADS)
    def test_search_students_resists_sqli(self, client, admin_token, payload):
        """La búsqueda de estudiantes no ejecuta SQL inyectado."""
        r = client.get(f"/students/search?q={payload}", headers=auth(admin_token))
        # Debe retornar 200 con resultados vacíos o 422 (validación),
        # nunca 500 (error de BD)
        assert r.status_code in (200, 422), f"SQL injection causó status {r.status_code}"
        if r.status_code == 200:
            data = r.json()
            assert isinstance(data.get("items", data), (list, dict))

    @pytest.mark.parametrize("payload", SQL_PAYLOADS)
    def test_dashboard_carrera_filter_resists_sqli(self, client, admin_token, payload):
        """El filtro de carrera en dashboard no ejecuta SQL inyectado."""
        r = client.get(f"/dashboard/risk?carrera={payload}", headers=auth(admin_token))
        assert r.status_code in (200, 422)

    @pytest.mark.parametrize("payload", SQL_PAYLOADS)
    def test_search_carrera_param_resists_sqli(self, client, admin_token, payload):
        """El parámetro carrera en búsqueda resiste inyección."""
        r = client.get(
            f"/students/search?q=test&carrera={payload}",
            headers=auth(admin_token),
        )
        assert r.status_code in (200, 422)


class TestInputValidation:
    """Validación de inputs malformados y límites."""

    def test_student_id_path_traversal(self, client, admin_token):
        """IDs no numéricos en path no causan crash."""
        for bad_id in ["../etc/passwd", "1;ls", "abc", "-1", "99999999999"]:
            r = client.get(f"/students/{bad_id}/ficha", headers=auth(admin_token))
            assert r.status_code in (404, 422, 400)

    def test_extremely_long_query(self, client, admin_token):
        """Query strings excesivamente largos son manejados."""
        long_q = "A" * 10000
        r = client.get(f"/students/search?q={long_q}", headers=auth(admin_token))
        assert r.status_code in (200, 422, 414)

    def test_null_bytes_in_search(self, client, admin_token):
        """Null bytes en búsqueda no causan crash."""
        r = client.get("/students/search?q=test%00malicious", headers=auth(admin_token))
        assert r.status_code in (200, 422)

    def test_unicode_control_chars_in_search(self, client, admin_token):
        """Caracteres de control Unicode no causan crash."""
        r = client.get("/students/search?q=test​‌‍", headers=auth(admin_token))
        assert r.status_code in (200, 422)

    def test_pagination_negative_page(self, client, admin_token):
        """Página negativa retorna error de validación."""
        r = client.get("/students/search?q=test&page=-1", headers=auth(admin_token))
        assert r.status_code == 422

    def test_pagination_excessive_limit(self, client, admin_token):
        """Límite mayor al máximo permitido es rechazado."""
        r = client.get("/students/search?q=test&limit=99999", headers=auth(admin_token))
        assert r.status_code == 422

    def test_empty_search_no_data_leak(self, client, admin_token):
        """Búsqueda vacía sin filtros no retorna todos los estudiantes."""
        r = client.get("/students/search?q=", headers=auth(admin_token))
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0

    def test_special_chars_in_periodo(self, client, admin_token):
        """Caracteres especiales en periodo no causan crash."""
        for bad in ["P67'; DROP TABLE--", "<script>", "../../etc"]:
            r = client.get(
                f"/students/1/ficha?periodo={bad}",
                headers=auth(admin_token),
            )
            assert r.status_code in (200, 404, 422)
