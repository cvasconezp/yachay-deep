"""Caso TENESACA: asignaturas duplicadas y "99 días sin acceso" falsos.

El estudiante aparecía como RIESGO ALTO por "99 días sin acceso" cuando había entrado al
aula hace 2 días. El 99 venía de un aula fantasma (409369, PANADERÍA BÁSICA) que ni
siquiera está en su ficha — probablemente un cambio de grupo: AVAC lo sigue listando en el
aula vieja, que nunca volvió a pisar. Y esa misma asignatura salía DOS VECES en el
dashboard porque se deduplicaba por código de curso, no por asignatura.
"""
from datetime import date

from backend.models.student import Student
from backend.models.avac_access import AvacAccess
from backend.models.course_config import CourseConfig, SemesterConfig
from backend.models.user import User, UserRole
from backend.auth.jwt import hash_password, create_access_token

SNAP = date(2026, 7, 16)
PER = "P68"


def _admin(db):
    u = User(email="fant@t.ec", nombre="Admin", hashed_password=hash_password("TestPassword123!"),
             role=UserRole.admin, is_active=True)
    db.add(u); db.commit(); db.refresh(u); return u


def _h(u):
    return {"Authorization": f"Bearer {create_access_token({'sub': str(u.id)})}"}


def _curso(db, codigo, asignatura):
    db.add(CourseConfig(codigo_avac=codigo, asignatura=asignatura, activo=True, semestre=PER))


def _acceso(db, sid, codigo, dias, texto=None):
    db.add(AvacAccess(student_id=sid, codigo_curso=codigo, periodo=PER, snapshot_date=SNAP,
                      dias_sin_acceso=float(dias), ultimo_acceso_texto=texto or f"{dias} días"))


def _escenario_tenesaca(db):
    """Dos aulas de PANADERÍA BÁSICA: la real (2d) y la fantasma (99d)."""
    db.add(SemesterConfig(semestre=PER, activo=True))
    s = Student(nombre="TENESACA RIOS CRISTOPHER JAVIER", carrera="GASTRONOMÍA")
    db.add(s); db.commit(); db.refresh(s)

    _curso(db, "409369", "PANADERÍA BÁSICA")          # aula fantasma
    _curso(db, "409354", "PANADERÍA BÁSICA")          # aula real
    _curso(db, "409373", "TÉCNICAS APLICADAS I")
    _curso(db, "409374", "TÉCNICAS APLICADAS I")
    _acceso(db, s.id, "409369", 99, "99 días 3 horas")
    _acceso(db, s.id, "409354", 2, "2 días 4 horas")
    _acceso(db, s.id, "409373", 3, "2 días 23 horas")
    _acceso(db, s.id, "409374", 2, "2 días 4 horas")
    db.commit()
    return s


def test_la_asignatura_no_sale_duplicada(db, client):
    """Salían PANADERÍA BÁSICA y TÉCNICAS APLICADAS I dos veces cada una."""
    a = _admin(db); s = _escenario_tenesaca(db)

    r = client.get(f"/dashboard/risk/{s.id}/inactividad?periodo={PER}", headers=_h(a))
    assert r.status_code == 200, r.text
    asignaturas = [x["asignatura"] for x in r.json()]
    assert len(asignaturas) == len(set(asignaturas)), f"asignaturas repetidas: {asignaturas}"


def test_gana_el_acceso_mas_reciente_no_el_aula_abandonada(db, client):
    """Si entró hace 2 días a esa asignatura, decir 99 es sencillamente falso."""
    a = _admin(db); s = _escenario_tenesaca(db)

    filas = client.get(f"/dashboard/risk/{s.id}/inactividad?periodo={PER}", headers=_h(a)).json()
    pan = next(x for x in filas if x["asignatura"] == "PANADERÍA BÁSICA")
    assert pan["dias_sin_acceso"] == 2, "debe reflejar el aula real, no la fantasma"
    assert pan["codigo_curso"] == "409354"


def test_dias_y_texto_de_la_misma_fila_son_coherentes(db, client):
    """En la captura, una fila decía '38d' y a la vez 'último acceso: 99 días 3 horas'."""
    a = _admin(db); s = _escenario_tenesaca(db)

    for fila in client.get(f"/dashboard/risk/{s.id}/inactividad?periodo={PER}", headers=_h(a)).json():
        texto = fila["ultimo_acceso_texto"] or ""
        if "días" in texto:
            dias_texto = int(texto.split()[0])
            assert abs(dias_texto - fila["dias_sin_acceso"]) <= 1, (
                f"{fila['asignatura']}: dice {fila['dias_sin_acceso']}d pero el texto dice '{texto}'"
            )


def test_ordenadas_por_gravedad(db, client):
    a = _admin(db); s = _escenario_tenesaca(db)
    dias = [x["dias_sin_acceso"] for x in
            client.get(f"/dashboard/risk/{s.id}/inactividad?periodo={PER}", headers=_h(a)).json()]
    assert dias == sorted(dias, reverse=True)


def test_el_modelo_distingue_maximo_de_ultimo_acceso(db):
    """Los dos campos tienen semánticas distintas y no deben confundirse."""
    s = Student(nombre="X", carrera="Y", dias_sin_acceso=99, dias_desde_ultimo_acceso=2)
    db.add(s); db.commit(); db.refresh(s)
    assert s.dias_sin_acceso == 99            # asignatura más descuidada
    assert s.dias_desde_ultimo_acceso == 2    # pisó AVAC hace 2 días
