"""Desenlace real (aprobó/reprobó/continuó) frente a la predicción del modelo."""
from datetime import datetime, timedelta, timezone

from backend.models.student import Student
from backend.models.grade import Grade
from backend.models.enrollment import Enrollment
from backend.models.intervention import Intervention
from backend.models.user import User, UserRole
from backend.auth.jwt import hash_password, create_access_token
from backend.services.outcomes import (
    resultados_academicos, continuidad, desenlaces_intervenidos, NOTA_APROBACION,
)


def _admin(db):
    u = User(email="des@t.ec", nombre="Admin", hashed_password=hash_password("TestPassword123!"),
             role=UserRole.admin, is_active=True)
    db.add(u); db.commit(); db.refresh(u); return u


def _h(u):
    return {"Authorization": f"Bearer {create_access_token({'sub': str(u.id)})}"}


def _est(db, nombre):
    s = Student(nombre=nombre, carrera="Educación", prob_reprobacion=0.9, prob_desercion=0.9)
    db.add(s); db.commit(); db.refresh(s); return s


def _nota(db, sid, valor, periodo="P68", asig="Matemática"):
    db.add(Grade(student_id=sid, asignatura=asig, periodo=periodo, nota_final=valor))
    db.commit()


def _inv(db, sid, uid):
    db.add(Intervention(student_id=sid, monitor_id=uid, periodo="P68", medio="WhatsApp",
                        motivo="Inactividad en AVAC",
                        created_at=datetime.now(timezone.utc) - timedelta(days=30)))
    db.commit()


# ── reprobación real ──
def test_reprobar_es_nota_menor_a_70(db):
    s = _est(db, "Ana")
    _nota(db, s.id, 65.0)
    r = resultados_academicos(db, "P68")[s.id]
    assert r["reprobo"] is True
    assert r["reprobadas"] == 1


def test_aprobar_con_70_justo(db):
    """70 aprueba: el umbral es < 70, no <= 70."""
    s = _est(db, "Beto")
    _nota(db, s.id, NOTA_APROBACION)
    assert resultados_academicos(db, "P68")[s.id]["reprobo"] is False


def test_basta_una_asignatura_reprobada(db):
    s = _est(db, "Caro")
    _nota(db, s.id, 90.0, asig="Lengua")
    _nota(db, s.id, 40.0, asig="Física")
    r = resultados_academicos(db, "P68")[s.id]
    assert r["asignaturas"] == 2 and r["reprobadas"] == 1 and r["reprobo"] is True


def test_sin_notas_no_aparece(db):
    """Si el período no cerró, no hay desenlace — no se inventa uno."""
    s = _est(db, "Dani")
    assert s.id not in resultados_academicos(db, "P68")


# ── continuidad real ──
def test_no_continuo_si_no_hay_rastro_en_el_siguiente(db):
    s = _est(db, "Eva")
    _nota(db, s.id, 80.0, periodo="P68")
    otro = _est(db, "Otro que sí siguió")     # P69 debe existir para poder medir
    _nota(db, otro.id, 70.0, periodo="P69")
    assert continuidad(db, "P68", [s.id, otro.id])[s.id] is False


def test_sin_periodo_siguiente_no_se_mide_continuidad(db):
    """Sin esto, "nadie aparece en P69" se leería como "todos desertaron": 100% falso."""
    s = _est(db, "Zoe")
    _nota(db, s.id, 80.0, periodo="P68")
    assert continuidad(db, "P68", [s.id]) == {}, (
        "si el período siguiente no ha empezado, la continuidad es inmedible, no 0%"
    )


def test_continuo_si_tiene_matricula_en_el_siguiente(db):
    s = _est(db, "Fabi")
    db.add(Enrollment(student_id=s.id, periodo="P69", asignatura="Matemática")); db.commit()
    assert continuidad(db, "P68", [s.id])[s.id] is True


def test_continuo_si_tiene_notas_en_el_siguiente(db):
    s = _est(db, "Gabo")
    _nota(db, s.id, 75.0, periodo="P69")
    assert continuidad(db, "P68", [s.id])[s.id] is True


# ── el informe ──
def test_compara_intervenidos_y_no_intervenidos(db, client):
    a = _admin(db)
    i1 = _est(db, "Intervenido reprobó"); _nota(db, i1.id, 50.0); _inv(db, i1.id, a.id)
    i2 = _est(db, "Intervenido aprobó");  _nota(db, i2.id, 85.0); _inv(db, i2.id, a.id)
    n1 = _est(db, "No intervenido");      _nota(db, n1.id, 90.0)

    d = client.get("/analytics/effectiveness/desenlaces?periodo=P68", headers=_h(a)).json()
    assert d["disponible"] is True
    assert d["intervenidos"]["total"] == 2
    assert d["intervenidos"]["reprobaron"] == 1
    assert d["intervenidos"]["tasa_reprobacion"] == 50.0
    assert d["no_intervenidos"]["reprobaron"] == 0


def test_dice_cuando_todavia_no_hay_datos(db, client):
    """Antes del cierre no hay nada que medir, y hay que decirlo — no rellenar."""
    a = _admin(db)
    s = _est(db, "Sin cerrar"); _inv(db, s.id, a.id)

    d = client.get("/analytics/effectiveness/desenlaces?periodo=P68", headers=_h(a)).json()
    assert d["disponible"] is False
    assert "cierre" in d["motivo_no_disponible"]


def test_incluye_la_advertencia_de_no_causalidad(db, client):
    a = _admin(db)
    s = _est(db, "X"); _nota(db, s.id, 50.0); _inv(db, s.id, a.id)
    d = client.get("/analytics/effectiveness/desenlaces?periodo=P68", headers=_h(a)).json()
    assert "NO es el efecto de intervenir" in d["advertencia"]
    assert d["periodo_siguiente"] == "P69"
