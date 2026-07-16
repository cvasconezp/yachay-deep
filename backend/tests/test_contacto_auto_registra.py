"""Registrar la intervención al copiar el mensaje de contacto desde Alertas.

Antes, copiar la plantilla no dejaba rastro: el monitor contactaba al estudiante y ese
contacto no existía para el sistema. Sin registro no hay snapshot, y sin snapshot el
impacto no se puede medir nunca. Estos tests fijan que el alta desde Alertas capture
todo lo necesario.
"""
from backend.models.student import Student
from backend.models.intervention import Intervention
from backend.models.alert_event import AlertEvent
from backend.models.user import User, UserRole
from backend.auth.jwt import hash_password, create_access_token


def _admin(db):
    u = User(email="alertas@t.ec", nombre="Carlos Vásconez",
             hashed_password=hash_password("TestPassword123!"),
             role=UserRole.admin, is_active=True)
    db.add(u); db.commit(); db.refresh(u); return u


def _headers(u):
    return {"Authorization": f"Bearer {create_access_token({'sub': str(u.id)})}"}


def _est(db):
    s = Student(nombre="VEINTIMILLA MOCHA BRENDA", carrera="MARKETING",
                indice_compromiso=0.19, porcentaje_tareas=0.0, dias_sin_acceso=76,
                prob_desercion=0.9, prob_reprobacion=0.8, nivel_riesgo="Alto")
    db.add(s); db.commit(); db.refresh(s); return s


def _payload(sid, medio="WhatsApp"):
    return {
        "student_id": sid, "medio": medio, "motivo": "Inactividad en AVAC",
        "estado": "En riesgo", "requiere_seguimiento": "si",
        "observacion": "Mensaje de contacto enviado desde Alertas.",
    }


def test_el_contacto_queda_registrado_con_snapshot(db, client):
    """Lo esencial: sin snapshot no se puede medir impacto después."""
    a = _admin(db); s = _est(db)

    r = client.post("/interventions", json=_payload(s.id), headers=_headers(a))
    assert r.status_code in (200, 201), r.text

    inv = db.query(Intervention).filter(Intervention.student_id == s.id).first()
    assert inv is not None
    assert inv.medio == "WhatsApp"
    assert inv.snapshot_dias_sin_acceso == 76
    assert inv.snapshot_compromiso == 0.19
    assert inv.snapshot_nivel_riesgo == "Alto"
    assert inv.carrera == "MARKETING"
    assert inv.monitor_nombre == "Carlos Vásconez"


def test_queda_pendiente_no_resuelta(db, client):
    """Copiar el mensaje no significa que el estudiante haya respondido."""
    a = _admin(db); s = _est(db)
    client.post("/interventions", json=_payload(s.id), headers=_headers(a))

    inv = db.query(Intervention).filter(Intervention.student_id == s.id).first()
    assert not inv.resultado
    assert inv.estado_workflow in (None, "pendiente")
    assert inv.requiere_seguimiento == "si"


def test_medio_email_tambien(db, client):
    a = _admin(db); s = _est(db)
    client.post("/interventions", json=_payload(s.id, medio="Email"), headers=_headers(a))
    inv = db.query(Intervention).filter(Intervention.student_id == s.id).first()
    assert inv.medio == "Email"


def test_registrar_marca_las_alertas_como_leidas(db, client):
    """El alta ya limpiaba las alertas del estudiante: se mantiene desde Alertas."""
    a = _admin(db); s = _est(db)
    db.add(AlertEvent(student_id=s.id, tipo="inactividad", severidad="alto", leido=False))
    db.commit()

    client.post("/interventions", json=_payload(s.id), headers=_headers(a))
    alerta = db.query(AlertEvent).filter(AlertEvent.student_id == s.id).first()
    assert alerta.leido is True


def test_dos_contactos_generan_dos_registros(db, client):
    """WhatsApp y correo son contactos distintos; ambos deben constar."""
    a = _admin(db); s = _est(db)
    client.post("/interventions", json=_payload(s.id, "WhatsApp"), headers=_headers(a))
    client.post("/interventions", json=_payload(s.id, "Email"), headers=_headers(a))

    medios = {i.medio for i in db.query(Intervention).filter(Intervention.student_id == s.id).all()}
    assert medios == {"WhatsApp", "Email"}
