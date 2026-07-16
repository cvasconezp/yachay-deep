"""Recalcular riesgo desde la BD sin volver a scrapear (~2h)."""
from datetime import date, datetime, timedelta, timezone
import json

from backend.models.student import Student
from backend.models.avac_access import AvacAccess
from backend.models.task_submission import TaskSubmission
from backend.models.enrollment import Enrollment
from backend.models.course_config import CourseConfig, SemesterConfig
from backend.models.user import User, UserRole
from backend.auth.jwt import hash_password, create_access_token
from backend.services.recalculo import recalcular_indicadores
from backend.services.retiro import marcar_retirado

HOY = datetime.now(timezone.utc)
SNAP = date.today()
PER = "P68"


def _admin(db):
    u = User(email="rec@t.ec", nombre="Admin", hashed_password=hash_password("TestPassword123!"),
             role=UserRole.admin, is_active=True)
    db.add(u); db.commit(); db.refresh(u); return u


def _h(u):
    return {"Authorization": f"Bearer {create_access_token({'sub': str(u.id)})}"}


def _semestre(db, con_calendario=False):
    cal = None
    if con_calendario:
        cal = json.dumps([
            {"fecha": (HOY - timedelta(days=20)).date().isoformat(), "tipo": "entrega"},
            {"fecha": (HOY + timedelta(days=20)).date().isoformat(), "tipo": "entrega"},
        ])
    sem = SemesterConfig(semestre=PER, activo=True, bloque_actual="2",
                         bloque2_inicio=HOY - timedelta(days=38),
                         bloque2_fin=HOY + timedelta(days=30),
                         calendario_academico=cal)
    db.add(sem); db.commit(); return sem


def _est(db, nombre="Cristopher"):
    s = Student(nombre=nombre, carrera="GASTRONOMÍA", estado_matricula="Matriculado",
                promedio_calificaciones=75.0, nivel_riesgo="Alto", dias_sin_acceso=99)
    db.add(s); db.commit(); db.refresh(s); return s


def _acceso(db, sid, cod, dias):
    db.add(AvacAccess(student_id=sid, codigo_curso=cod, periodo=PER,
                      snapshot_date=SNAP, dias_sin_acceso=float(dias)))


def _matricula(db, sid, cod):
    db.add(Enrollment(student_id=sid, codigo_grupo=cod, asignatura="X", periodo="68"))


def test_el_aula_fantasma_deja_de_mandar(db):
    """Caso TENESACA: 99 días venían de un aula sin matrícula."""
    _semestre(db)
    s = _est(db)
    _matricula(db, s.id, "409354")
    _acceso(db, s.id, "409354", 2)      # aula real
    _acceso(db, s.id, "409369", 99)     # fantasma
    db.commit()

    r = recalcular_indicadores(db)
    db.refresh(s)
    assert r["registros_descartados"]["aulas_fantasma"] == 1
    assert s.dias_sin_acceso == 2, "el aula sin matrícula ya no secuestra el indicador"
    assert s.dias_desde_ultimo_acceso == 2


def test_descarta_cursos_de_bloque_cerrado(db):
    """La materia de bloque 1 que terminó no debe contar."""
    _semestre(db)
    db.add(CourseConfig(codigo_avac="B1", asignatura="MATERIA Y", bloque="1", activo=True))
    s = _est(db)
    _matricula(db, s.id, "B1"); _matricula(db, s.id, "B2")
    _acceso(db, s.id, "B1", 56)     # bloque cerrado
    _acceso(db, s.id, "B2", 3)
    db.commit()

    r = recalcular_indicadores(db)
    db.refresh(s)
    assert r["registros_descartados"]["cursos_de_bloque_cerrado"] == 1
    assert s.dias_sin_acceso == 3


def test_acota_los_dias_a_la_vida_del_bloque(db):
    """Nadie puede llevar más días sin acceso que los que el bloque lleva abierto."""
    _semestre(db)
    s = _est(db)
    _matricula(db, s.id, "C1")
    _acceso(db, s.id, "C1", 200)
    db.commit()

    recalcular_indicadores(db)
    db.refresh(s)
    assert s.dias_sin_acceso <= 38


def test_solo_cuenta_las_tareas_vencidas(db):
    """Entregó la unidad vencida y no la futura: es 100%, no 50%."""
    _semestre(db, con_calendario=True)
    s = _est(db)
    _matricula(db, s.id, "C1")
    _acceso(db, s.id, "C1", 1)
    db.add_all([
        TaskSubmission(student_id=s.id, codigo_curso="C1", periodo=PER, snapshot_date=SNAP,
                       unidad="1", entregada=True),
        TaskSubmission(student_id=s.id, codigo_curso="C1", periodo=PER, snapshot_date=SNAP,
                       unidad="2", entregada=False),
    ])
    db.commit()

    r = recalcular_indicadores(db)
    db.refresh(s)
    assert r["registros_descartados"]["tareas_aun_no_vencidas"] == 1
    assert s.porcentaje_tareas == 100.0


def test_un_buen_estudiante_deja_de_estar_en_riesgo_alto(db):
    """El efecto conjunto: con los datos limpios, quien va bien sale bien."""
    _semestre(db, con_calendario=True)
    s = _est(db)
    _matricula(db, s.id, "C1")
    _acceso(db, s.id, "C1", 1)                # entró ayer
    _acceso(db, s.id, "FANTASMA", 99)         # aula sin matrícula
    db.add(TaskSubmission(student_id=s.id, codigo_curso="C1", periodo=PER, snapshot_date=SNAP,
                          unidad="1", entregada=True))
    db.commit()
    assert s.nivel_riesgo == "Alto"

    recalcular_indicadores(db)
    db.refresh(s)
    assert s.nivel_riesgo in ("Bajo", "Sin riesgo"), (
        f"debería salir del riesgo alto, quedó {s.nivel_riesgo}"
    )


def test_los_retirados_no_se_recalculan(db):
    _semestre(db)
    s = _est(db); marcar_retirado(db, s)
    _matricula(db, s.id, "C1"); _acceso(db, s.id, "C1", 2)
    db.commit()

    recalcular_indicadores(db)
    db.refresh(s)
    assert s.dias_sin_acceso == 99, "su foto quedó congelada al retirarse"


def test_sin_semestre_activo_no_hace_nada(db):
    assert recalcular_indicadores(db)["ok"] is False


def test_el_endpoint_responde_y_regenera_alertas(db, client):
    _semestre(db)
    a = _admin(db); s = _est(db)
    _matricula(db, s.id, "C1"); _acceso(db, s.id, "C1", 2)
    db.commit()

    r = client.post("/admin/recalcular-indicadores", headers=_h(a))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] is True
    assert "alertas" in d
    assert d["estudiantes_actualizados"] >= 1


def test_las_tareas_del_bloque_cerrado_no_hunden_el_porcentaje(db):
    """EL BUG: el primer recálculo bajó las tareas de 31% a 20% porque contaba como "no
    entregadas" las de las 620 aulas del bloque ya cerrado."""
    _semestre(db)
    s = _est(db)
    _matricula(db, s.id, "B2")
    _acceso(db, s.id, "B2", 2)
    # El bloque 1 está cerrado: sus tareas no cuentan
    db.add(Enrollment(student_id=s.id, codigo_grupo="B1_VIEJA", asignatura="Vieja",
                      bloque=1, periodo="68"))
    db.add_all([
        TaskSubmission(student_id=s.id, codigo_curso="B2", periodo=PER, snapshot_date=SNAP,
                       unidad="1", entregada=True),
        TaskSubmission(student_id=s.id, codigo_curso="B1_VIEJA", periodo=PER, snapshot_date=SNAP,
                       unidad="1", entregada=False),
    ])
    db.commit()

    r = recalcular_indicadores(db)
    db.refresh(s)
    assert r["registros_descartados"]["tareas_de_bloque_cerrado"] == 1
    assert s.porcentaje_tareas == 100.0, "solo cuenta la tarea del bloque en curso"
