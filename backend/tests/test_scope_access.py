"""Control de acceso por carrera (IDOR): un usuario no-admin sin carreras
asignadas (denegar por defecto) no debe poder leer datos por student_id a través
de endpoints de exportación/predicción/intervención.

El fixture monitor_user no tiene `carreras`, así que carreras_de(monitor) == []
→ asegurar_acceso_carrera levanta 403 y filtrar_carrera devuelve vacío.
"""
import pytest

from backend.models import Student
from .conftest import auth


@pytest.fixture
def un_estudiante(db):
    s = Student(id=900, nombre="ESTUDIANTE X", carrera="DERECHO",
                estado_matricula="Matriculado")
    db.add(s)
    db.commit()
    return s


class TestAmbitoPorCarrera:
    def test_monitor_no_exporta_ficha_pdf_de_otra_carrera(self, client, monitor_token, un_estudiante):
        r = client.get("/export/ficha/900/pdf", headers=auth(monitor_token))
        assert r.status_code == 403

    def test_monitor_no_ve_prediccion_por_id(self, client, monitor_token, un_estudiante):
        r = client.get("/predictions/student/900", headers=auth(monitor_token))
        assert r.status_code == 403

    def test_monitor_no_crea_intervencion_fuera_de_ambito(self, client, monitor_token, un_estudiante):
        r = client.post("/interventions", headers=auth(monitor_token), json={
            "student_id": 900, "medio": "llamada", "motivo": "bajas calificaciones",
            "estado": "Pendiente",
        })
        assert r.status_code == 403

    def test_monitor_listado_no_incluye_estudiante_fuera_de_ambito(self, client, monitor_token, db):
        # Estudiante en riesgo alto; un admin lo vería, el monitor sin carreras no.
        from backend.models import Student
        s = Student(id=901, nombre="ALUMNO RIESGO", carrera="DERECHO",
                    nivel_riesgo="Alto", estado_matricula="Matriculado")
        db.add(s)
        db.commit()
        r = client.get("/analytics/resumen/estudiantes-listado?tipo=riesgo_alto&periodo=todos",
                       headers=auth(monitor_token))
        assert r.status_code == 200
        assert "ALUMNO RIESGO" not in r.text  # sin carreras → no ve a nadie
