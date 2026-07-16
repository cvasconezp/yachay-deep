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


# ── coherencia aritmética de las tarjetas ──
def test_los_numeros_cuadran_entre_si(db, client):
    """El bug visible: 'No exitosas' salía 45 con 48 analizadas y tasa 3/47.

    La tarjeta restaba sobre el total y la tasa dividía entre las concluyentes, así que
    la intervención sin datos contaba como fracaso en una y no existía en la otra.
    """
    a = _admin(db)
    # 3 medibles (con snapshot) + 1 sin datos suficientes
    for _ in range(3):
        _intervencion(db, _est(db).id, dias_atras=30, uid=a.id)
    s_sin = _est(db)
    i = _intervencion(db, s_sin.id, dias_atras=30, uid=a.id)
    i.snapshot_compromiso = None; i.snapshot_porcentaje_tareas = None
    i.snapshot_dias_sin_acceso = None; i.snapshot_prob_desercion = None
    db.commit()

    d = client.get("/analytics/effectiveness?periodo=P68", headers=_headers(a)).json()

    assert d["total_analizadas"] == 4
    assert d["analizadas_concluyentes"] == 3
    assert d["sin_datos_suficientes"] == 1
    # exitosas + no_exitosas debe sumar las CONCLUYENTES, no el total
    assert d["exitosas"] + d["no_exitosas"] == d["analizadas_concluyentes"]
    # y la tasa debe ser coherente con esos dos
    esperada = round(d["exitosas"] / d["analizadas_concluyentes"] * 100, 1)
    assert d["tasa_exito_global"] == esperada


def test_informa_de_las_excluidas_por_recientes(db, client):
    """70 en Intervenciones y 48 aquí: el usuario debe poder ver dónde fueron las otras."""
    a = _admin(db)
    _intervencion(db, _est(db).id, dias_atras=30, uid=a.id)   # se mide
    _intervencion(db, _est(db).id, dias_atras=2, uid=a.id)    # muy reciente

    d = client.get("/analytics/effectiveness?periodo=P68", headers=_headers(a)).json()
    assert d["total_periodo"] == 2
    assert d["total_analizadas"] == 1
    assert d["excluidas_por_recientes"] == 1


def test_desglose_explica_los_fracasos(db, client):
    """Distinguir 'el criterio es exigente' de 'no está funcionando'."""
    a = _admin(db)
    s = _est(db, compromiso=0.60, tareas=90.0, dias=1)   # mejora en todo
    _intervencion(db, s.id, dias_atras=30, uid=a.id)

    d = client.get("/analytics/effectiveness?periodo=P68", headers=_headers(a)).json()
    dg = d["desglose_no_exitosas"]
    assert set(dg) == {"mejoro_pero_empeoro_en_otro", "sin_cambios_significativos", "solo_empeoro"}
    assert sum(dg.values()) == d["no_exitosas"]


# ── el resultado manda: los otros dos campos se derivan ──
def test_no_contesto_deja_seguimiento_pendiente(db, client):
    a = _admin(db); s = _est(db)
    i = _intervencion(db, s.id, dias_atras=30, uid=a.id)

    client.patch(f"/interventions/{i.id}", json={"resultado": "No contestó"}, headers=_headers(a))
    db.refresh(i)
    assert i.estado_workflow == "sin_respuesta"
    assert i.requiere_seguimiento == "si", "si no contestó, hay que volver a intentarlo"
    assert i.fecha_resolucion is None


def test_contactado_no_resuelto_sigue_abierto(db, client):
    a = _admin(db); s = _est(db)
    i = _intervencion(db, s.id, dias_atras=30, uid=a.id)

    client.patch(f"/interventions/{i.id}",
                 json={"resultado": "Contactado - situación compleja"}, headers=_headers(a))
    db.refresh(i)
    assert i.estado_workflow == "contactado"
    assert i.requiere_seguimiento == "si"


def test_buzon_de_voz_requiere_seguimiento(db, client):
    a = _admin(db); s = _est(db)
    i = _intervencion(db, s.id, dias_atras=30, uid=a.id)
    client.patch(f"/interventions/{i.id}", json={"resultado": "Buzón de voz"}, headers=_headers(a))
    db.refresh(i)
    assert i.requiere_seguimiento == "si"


def test_cambiar_de_resuelto_a_no_contesto_reabre(db, client):
    """El desplegable permite corregirse: el caso debe reabrirse de verdad."""
    a = _admin(db); s = _est(db)
    i = _intervencion(db, s.id, dias_atras=30, uid=a.id)

    client.patch(f"/interventions/{i.id}", json={"resultado": "Resuelto"}, headers=_headers(a))
    db.refresh(i)
    assert i.fecha_resolucion is not None

    client.patch(f"/interventions/{i.id}", json={"resultado": "No contestó"}, headers=_headers(a))
    db.refresh(i)
    assert i.estado_workflow == "sin_respuesta"
    assert i.fecha_resolucion is None, "reabrir debe limpiar la fecha de resolución"
    assert i.requiere_seguimiento == "si"
