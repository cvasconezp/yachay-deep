"""Retiro congelado, reporte por indicador y matriz de transición de riesgo."""
from datetime import datetime, timedelta, timezone

from backend.models.student import Student
from backend.models.intervention import Intervention
from backend.models.alert_event import AlertEvent
from backend.models.user import User, UserRole
from backend.auth.jwt import hash_password, create_access_token
from backend.services.retiro import marcar_retirado, es_estado_de_retiro, filtrar_activos


def _admin(db):
    u = User(email="ret@t.ec", nombre="Admin", hashed_password=hash_password("TestPassword123!"),
             role=UserRole.admin, is_active=True)
    db.add(u); db.commit(); db.refresh(u); return u


def _h(u):
    return {"Authorization": f"Bearer {create_access_token({'sub': str(u.id)})}"}


def _est(db, nombre="Ana", riesgo="Alto", dias=70, comp=0.2, tar=10.0):
    s = Student(nombre=nombre, carrera="Educación", nivel_riesgo=riesgo,
                dias_sin_acceso=dias, indice_compromiso=comp, porcentaje_tareas=tar,
                prob_desercion=0.8, prob_reprobacion=0.7)
    db.add(s); db.commit(); db.refresh(s); return s


def _inv(db, sid, uid, dias_atras=30, **kw):
    i = Intervention(student_id=sid, monitor_id=uid, periodo="P68", medio="WhatsApp",
                     motivo="Inactividad en AVAC", carrera="Educación",
                     created_at=datetime.now(timezone.utc) - timedelta(days=dias_atras),
                     snapshot_compromiso=0.2, snapshot_porcentaje_tareas=10.0,
                     snapshot_dias_sin_acceso=70, snapshot_prob_desercion=0.8,
                     snapshot_nivel_riesgo="Alto", **kw)
    db.add(i); db.commit(); db.refresh(i); return i


# ── retiro ──
def test_marcar_retirado_congela_los_indicadores(db):
    s = _est(db, dias=70, comp=0.2)
    assert marcar_retirado(db, s, motivo="Cambio de ciudad") is True
    db.commit()
    assert s.retirado is True
    assert s.retiro_snapshot_dias_sin_acceso == 70
    assert s.retiro_snapshot_compromiso == 0.2
    assert s.retiro_snapshot_nivel_riesgo == "Alto"
    assert s.fecha_retiro is not None


def test_retirar_es_idempotente(db):
    s = _est(db)
    assert marcar_retirado(db, s) is True
    assert marcar_retirado(db, s) is False, "no debe repisar el retiro original"


def test_estado_de_retiro_reconoce_variantes(db):
    assert es_estado_de_retiro("Retirado")
    assert es_estado_de_retiro("  retiro ")
    assert not es_estado_de_retiro("Activo")
    assert not es_estado_de_retiro(None)


def test_registrar_retiro_en_intervencion_congela(db, client):
    """El flujo real: el monitor marca estado='Retirado' al registrar."""
    a = _admin(db); s = _est(db)
    r = client.post("/interventions", json={
        "student_id": s.id, "medio": "WhatsApp", "motivo": "Consulta del estudiante",
        "estado": "Retirado",
    }, headers=_h(a))
    assert r.status_code in (200, 201), r.text
    db.refresh(s)
    assert s.retirado is True
    assert s.retiro_snapshot_dias_sin_acceso == 70


def test_los_retirados_no_generan_alertas(db):
    activo = _est(db, nombre="Activo")
    ido = _est(db, nombre="Retirado")
    marcar_retirado(db, ido); db.commit()

    quedan = filtrar_activos(db.query(Student)).all()
    assert activo in quedan
    assert ido not in quedan


def test_retirado_no_cuenta_como_intervencion_fallida(db, client):
    """El retiro es un desenlace, no un fracaso: hundía la tasa sin motivo."""
    a = _admin(db)
    s_ok = _est(db, nombre="Sigue")
    s_ido = _est(db, nombre="Se fue")
    _inv(db, s_ok.id, a.id)
    _inv(db, s_ido.id, a.id)
    marcar_retirado(db, s_ido); db.commit()

    d = client.get("/analytics/effectiveness?periodo=P68", headers=_h(a)).json()
    assert d["retirados_excluidos"] == 1
    assert d["total_analizadas"] == 1, "el retirado no debe entrar al denominador"


# ── por indicador ──
def test_reporta_cada_indicador_por_separado(db, client):
    """El binario mentía: 45 de 47 mejoraban en algo y salía '6.4% de éxito'."""
    a = _admin(db)
    # mejora fuerte en días y tareas, pero el compromiso baja → el binario diría "fracaso"
    s = _est(db, dias=2, comp=0.10, tar=80.0)
    _inv(db, s.id, a.id)

    d = client.get("/analytics/effectiveness?periodo=P68", headers=_h(a)).json()
    pi = d["por_indicador"]
    assert pi["dias_sin_acceso"]["mejoraron"] == 1
    assert pi["porcentaje_tareas"]["mejoraron"] == 1
    assert pi["compromiso"]["empeoraron"] == 1
    assert d["exitosas"] == 0                 # el binario lo llama fracaso...
    assert d["con_alguna_mejora"] == 1        # ...pero mejoró en dos de tres


# ── matriz de transición ──
def test_matriz_de_transicion_alto_a_bajo(db, client):
    a = _admin(db)
    s = _est(db, riesgo="Bajo")          # ahora está en Bajo
    _inv(db, s.id, a.id)                 # el snapshot decía Alto

    t = client.get("/analytics/effectiveness?periodo=P68", headers=_h(a)).json()["transicion_riesgo"]
    assert t["matriz"]["Alto->Bajo"] == 1
    assert t["bajaron_de_nivel"] == 1
    assert t["subieron_de_nivel"] == 0


def test_matriz_cuenta_los_que_se_mantienen(db, client):
    a = _admin(db)
    s = _est(db, riesgo="Alto")
    _inv(db, s.id, a.id)

    t = client.get("/analytics/effectiveness?periodo=P68", headers=_h(a)).json()["transicion_riesgo"]
    assert t["matriz"]["Alto->Alto"] == 1
    assert t["se_mantuvieron"] == 1


def test_matriz_detecta_empeoramiento(db, client):
    a = _admin(db)
    s = _est(db, riesgo="Alto")
    i = _inv(db, s.id, a.id)
    i.snapshot_nivel_riesgo = "Medio"; db.commit()   # iba en Medio y cayó a Alto

    t = client.get("/analytics/effectiveness?periodo=P68", headers=_h(a)).json()["transicion_riesgo"]
    assert t["matriz"]["Medio->Alto"] == 1
    assert t["subieron_de_nivel"] == 1


def test_la_matriz_suma_lo_mismo_que_sus_partes(db, client):
    a = _admin(db)
    for riesgo in ("Alto", "Medio", "Bajo"):
        _inv(db, _est(db, riesgo=riesgo).id, a.id)

    t = client.get("/analytics/effectiveness?periodo=P68", headers=_h(a)).json()["transicion_riesgo"]
    assert t["bajaron_de_nivel"] + t["subieron_de_nivel"] + t["se_mantuvieron"] == t["total"]
    assert sum(t["matriz"].values()) == t["total"]


# ── lista de retiros y salida de las estadísticas ──
def test_lista_de_retiros_con_la_foto_del_momento(db, client):
    a = _admin(db)
    s = _est(db, nombre="Se fue", dias=45, comp=0.15, tar=20.0)
    marcar_retirado(db, s, motivo="Problemas económicos"); db.commit()

    r = client.get("/students/retirados", headers=_h(a))
    assert r.status_code == 200
    datos = r.json()
    assert len(datos) == 1
    assert datos[0]["nombre"] == "Se fue"
    assert datos[0]["motivo_retiro"] == "Problemas económicos"
    assert datos[0]["dias_sin_acceso_al_retirarse"] == 45
    assert datos[0]["nivel_riesgo_al_retirarse"] == "Alto"


def test_el_buscador_no_muestra_retirados(db, client):
    a = _admin(db)
    _est(db, nombre="Activo Uno")
    ido = _est(db, nombre="Retirado Uno")
    marcar_retirado(db, ido); db.commit()

    nombres = [x["nombre"] for x in
               client.get("/students/search?carrera=Educación", headers=_h(a)).json()["items"]]
    assert "Activo Uno" in nombres
    assert "Retirado Uno" not in nombres


def test_se_pueden_incluir_si_se_pide(db, client):
    a = _admin(db)
    ido = _est(db, nombre="Retirado Uno")
    marcar_retirado(db, ido); db.commit()

    nombres = [x["nombre"] for x in
               client.get("/students/search?carrera=Educación&incluir_retirados=true",
                          headers=_h(a)).json()["items"]]
    assert "Retirado Uno" in nombres


def test_reactivar_lo_devuelve_al_seguimiento(db, client):
    a = _admin(db)
    s = _est(db, nombre="Volvió")
    marcar_retirado(db, s); db.commit()

    r = client.post(f"/students/{s.id}/reactivar", headers=_h(a))
    assert r.status_code == 200
    db.refresh(s)
    assert s.retirado is False
    assert client.get("/students/retirados", headers=_h(a)).json() == []


def test_reactivar_a_quien_no_esta_retirado_falla(db, client):
    a = _admin(db); s = _est(db)
    assert client.post(f"/students/{s.id}/reactivar", headers=_h(a)).status_code == 400
