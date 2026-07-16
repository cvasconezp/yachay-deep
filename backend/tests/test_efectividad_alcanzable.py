"""La vista de Efectividad estaba condenada a salir vacía.

Filtraba por `estado_workflow in ("resuelto","cerrado")`, pero ese campo NO se escribe
desde ninguna pantalla (0 referencias en el frontend, ningún endpoint lo asignaba): se
quedaba en "pendiente" para siempre. El usuario marcaba `resultado="Resuelto"` — otro
campo — y la vista seguía vacía. Estos tests fijan las dos correcciones.
"""
from datetime import datetime, timedelta, timezone

from backend.models.student import Student
from backend.models.intervention import Intervention
from backend.models.user import User, UserRole
from backend.auth.jwt import hash_password, create_access_token


def _admin(db):
    u = User(email="ef-admin@t.ec", nombre="Admin", hashed_password=hash_password("TestPassword123!"),
             role=UserRole.admin, is_active=True)
    db.add(u); db.commit(); db.refresh(u); return u


def _headers(u):
    return {"Authorization": f"Bearer {create_access_token({'sub': str(u.id)})}"}


def _est(db, compromiso=0.6, tareas=70.0, dias=2):
    s = Student(nombre="Mayacela Salazar", carrera="Educación",
                indice_compromiso=compromiso, porcentaje_tareas=tareas,
                dias_sin_acceso=dias, prob_desercion=0.4)
    db.add(s); db.commit(); db.refresh(s); return s


def _intervencion(db, sid, dias_atras=30, uid=None, **kw):
    i = Intervention(
        student_id=sid, monitor_id=uid, periodo="P68", medio="Presencial",
        motivo="Bajas calificaciones", carrera="Educación",
        created_at=datetime.now(timezone.utc) - timedelta(days=dias_atras),
        snapshot_compromiso=0.48, snapshot_porcentaje_tareas=50.0,
        snapshot_dias_sin_acceso=7, snapshot_prob_desercion=0.5, **kw)
    db.add(i); db.commit(); db.refresh(i); return i


# ── el arreglo 1: medir sin exigir el trámite de cierre ──
def test_mide_sin_exigir_cierre(db, client):
    """El caso real: intervención antigua y con snapshot, pero nunca 'cerrada'."""
    a = _admin(db)
    s = _est(db)
    _intervencion(db, s.id, dias_atras=30, uid=a.id)   # estado_workflow = "pendiente"

    r = client.get("/analytics/effectiveness?periodo=P68", headers=_headers(a))
    assert r.status_code == 200
    assert r.json()["total_analizadas"] == 1, "antes salía 0 por no estar 'cerrada'"


def test_intervencion_reciente_no_se_mide(db, client):
    """Sin tiempo transcurrido no hay 'después' que comparar."""
    a = _admin(db); s = _est(db)
    _intervencion(db, s.id, dias_atras=1, uid=a.id)

    data = client.get("/analytics/effectiveness?periodo=P68", headers=_headers(a)).json()
    assert data["total_analizadas"] == 0
    assert "días de antigüedad" in data["motivo_vacio"]


def test_solo_cerradas_sigue_disponible(db, client):
    """Quien quiera el criterio estricto puede pedirlo."""
    a = _admin(db); s = _est(db)
    _intervencion(db, s.id, dias_atras=30, uid=a.id)

    d = client.get("/analytics/effectiveness?periodo=P68&solo_cerradas=true", headers=_headers(a)).json()
    assert d["total_analizadas"] == 0


# ── el arreglo 2: marcar "Resuelto" sincroniza el workflow ──
def test_marcar_resultado_resuelto_sincroniza_workflow(db, client):
    a = _admin(db); s = _est(db)
    i = _intervencion(db, s.id, dias_atras=30, uid=a.id)
    assert i.estado_workflow in (None, "pendiente")

    r = client.patch(f"/interventions/{i.id}", json={"resultado": "Resuelto"}, headers=_headers(a))
    assert r.status_code == 200

    db.refresh(i)
    assert i.estado_workflow == "resuelto", "marcar 'Resuelto' debe reflejarse en el workflow"
    assert i.fecha_resolucion is not None


def test_resultado_no_terminal_no_cierra(db, client):
    a = _admin(db); s = _est(db)
    i = _intervencion(db, s.id, dias_atras=30, uid=a.id)

    client.patch(f"/interventions/{i.id}", json={"resultado": "No contestó"}, headers=_headers(a))
    db.refresh(i)
    assert i.estado_workflow != "resuelto"


def test_tras_marcar_resuelto_aparece_en_solo_cerradas(db, client):
    """El flujo completo del usuario: marco Resuelto → ahora sí computa."""
    a = _admin(db); s = _est(db)
    i = _intervencion(db, s.id, dias_atras=30, uid=a.id)

    client.patch(f"/interventions/{i.id}", json={"resultado": "Resuelto"}, headers=_headers(a))
    d = client.get("/analytics/effectiveness?periodo=P68&solo_cerradas=true", headers=_headers(a)).json()
    assert d["total_analizadas"] == 1


# ── coherencia entre las 3 columnas que el usuario percibe como un estado ──
def test_marcar_resuelto_limpia_la_columna_seguimiento(db, client):
    """SEG. mostraba 'Pend.' aunque el caso estuviera resuelto: nadie limpiaba la bandera."""
    a = _admin(db); s = _est(db)
    i = _intervencion(db, s.id, dias_atras=30, uid=a.id, requiere_seguimiento="si")

    client.patch(f"/interventions/{i.id}", json={"resultado": "Resuelto"}, headers=_headers(a))
    db.refresh(i)
    assert i.requiere_seguimiento == "no", "un caso resuelto no puede seguir pendiente de seguimiento"


def test_seguimiento_explicito_gana(db, client):
    """Si el usuario pide seguimiento en la misma edición, se respeta."""
    a = _admin(db); s = _est(db)
    i = _intervencion(db, s.id, dias_atras=30, uid=a.id, requiere_seguimiento="si")

    client.patch(f"/interventions/{i.id}",
                 json={"resultado": "Resuelto", "requiere_seguimiento": "si"}, headers=_headers(a))
    db.refresh(i)
    assert i.requiere_seguimiento == "si"


def test_desmarcar_revierte_a_pendiente(db, client):
    a = _admin(db); s = _est(db)
    i = _intervencion(db, s.id, dias_atras=30, uid=a.id)

    client.patch(f"/interventions/{i.id}", json={"resultado": "Resuelto"}, headers=_headers(a))
    db.refresh(i)
    assert i.estado_workflow == "resuelto"

    client.patch(f"/interventions/{i.id}", json={"resultado": ""}, headers=_headers(a))
    db.refresh(i)
    assert i.estado_workflow == "pendiente"
    assert i.fecha_resolucion is None
