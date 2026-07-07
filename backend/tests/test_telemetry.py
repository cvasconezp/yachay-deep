"""Tests de la telemetria de uso pseudonimizada (chore/estandar-casa, punto 7)."""
from backend.services.telemetry import track, _actor_hash
from backend.models.usage_event import UsageEvent


def test_track_registra_evento_sin_pii(db):
    track(db, "ficha360_view", user_id=42, role="monitor", tenant="ups",
          props={"carrera": "Educacion", "correo": "no@debe.entrar", "nombre": "Juan"})
    ev = db.query(UsageEvent).one()
    assert ev.event == "ficha360_view"
    assert ev.role == "monitor"
    assert ev.tenant == "ups"
    assert ev.actor_hash == _actor_hash(42)
    assert ev.actor_hash != "42"
    assert "correo" not in ev.props and "nombre" not in ev.props
    assert ev.props["carrera"] == "Educacion"


def test_evento_no_permitido_se_ignora(db):
    track(db, "evento_inventado", user_id=1)
    assert db.query(UsageEvent).count() == 0


def test_login_genera_evento(client, db, admin_user):
    r = client.post("/auth/login", data={
        "username": "admin@test.yachay.edu.ec",
        "password": "TestPassword123!",
    })
    assert r.status_code == 200
    db.expire_all()
    assert db.query(UsageEvent).filter(UsageEvent.event == "login").count() >= 1
