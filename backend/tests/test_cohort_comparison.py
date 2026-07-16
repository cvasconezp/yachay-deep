"""Grupo de comparación (diferencias-en-diferencias).

La prueba que importa: si intervenidos y no intervenidos mejoran IGUAL (reversión a la
media pura), el efecto estimado debe salir ~0. Un método que en ese caso reporte efecto
positivo está fabricando resultados.
"""
from datetime import date, timedelta, datetime, timezone

from backend.models.student import Student
from backend.models.intervention import Intervention
from backend.models.avac_access import AvacAccess
from backend.models.task_submission import TaskSubmission
from backend.services.cohort_comparison import comparar_cohortes, indicadores_en_fecha

T0 = date(2026, 5, 1)
T1 = T0 + timedelta(days=30)
PER = "P68"


def _est(db, nombre, carrera="Educación"):
    s = Student(nombre=nombre, carrera=carrera)
    db.add(s); db.flush(); return s


def _acceso(db, sid, dias, snap):
    db.add(AvacAccess(student_id=sid, codigo_curso="C1", periodo=PER,
                      snapshot_date=snap, dias_sin_acceso=float(dias)))


def _tareas(db, sid, entregadas, total, snap):
    for i in range(total):
        db.add(TaskSubmission(student_id=sid, codigo_curso="C1", periodo=PER,
                              snapshot_date=snap, entregada=(i < entregadas)))


def _intervenir(db, sid):
    db.add(Intervention(student_id=sid, periodo=PER,
                        created_at=datetime(T0.year, T0.month, T0.day, 12, tzinfo=timezone.utc),
                        snapshot_dias_sin_acceso=10))


def _escenario(db, n_trat, n_ctrl, dias_antes, dias_desp_trat, dias_desp_ctrl):
    """Todos arrancan igual; cambia solo cuánto mejora cada grupo."""
    for i in range(n_trat):
        s = _est(db, f"T{i}")
        _acceso(db, s.id, dias_antes, T0);        _tareas(db, s.id, 5, 10, T0)
        _acceso(db, s.id, dias_desp_trat, T1);    _tareas(db, s.id, 5, 10, T1)
        _intervenir(db, s.id)
    for i in range(n_ctrl):
        s = _est(db, f"C{i}")
        _acceso(db, s.id, dias_antes, T0);        _tareas(db, s.id, 5, 10, T0)
        _acceso(db, s.id, dias_desp_ctrl, T1);    _tareas(db, s.id, 5, 10, T1)
    db.commit()


# ── reconstrucción del pasado ──
def test_reconstruye_indicadores_en_fecha_pasada(db):
    s = _est(db, "Ana")
    _acceso(db, s.id, 12, T0); _tareas(db, s.id, 3, 10, T0)
    _acceso(db, s.id, 2, T1);  _tareas(db, s.id, 9, 10, T1)
    db.commit()

    en_t0 = indicadores_en_fecha(db, T0, PER)[s.id]
    assert en_t0["dias_sin_acceso"] == 12
    assert en_t0["porcentaje_tareas"] == 30.0

    en_t1 = indicadores_en_fecha(db, T1, PER)[s.id]
    assert en_t1["dias_sin_acceso"] == 2
    assert en_t1["porcentaje_tareas"] == 90.0


def test_dias_sin_acceso_es_el_maximo_entre_cursos(db):
    """Debe replicar el ETL: max entre cursos, no promedio."""
    s = _est(db, "Beto")
    _acceso(db, s.id, 2, T0)
    db.add(AvacAccess(student_id=s.id, codigo_curso="C2", periodo=PER,
                      snapshot_date=T0, dias_sin_acceso=15.0))
    db.commit()
    assert indicadores_en_fecha(db, T0, PER)[s.id]["dias_sin_acceso"] == 15


# ── el corazón del asunto ──
def test_sin_efecto_real_el_estimado_es_cero(db):
    """Ambos grupos mejoran igual (de 10 a 4 días) → efecto ~0, NO 'mejoró un 60%'."""
    _escenario(db, n_trat=12, n_ctrl=40, dias_antes=10, dias_desp_trat=4, dias_desp_ctrl=4)
    r = comparar_cohortes(db, periodo=PER, dias_seguimiento=30)

    assert r["disponible"] is True
    assert r["dias_sin_acceso"]["intervenidos"] == -6.0     # mejoraron 6 días...
    assert r["dias_sin_acceso"]["no_intervenidos"] == -6.0  # ...igual que los que no
    assert r["dias_sin_acceso"]["efecto_estimado"] == 0.0   # efecto atribuible: ninguno


def test_efecto_real_se_detecta(db):
    """Intervenidos 10→2, controles 10→6 → efecto = 4 días extra de mejora."""
    _escenario(db, n_trat=12, n_ctrl=40, dias_antes=10, dias_desp_trat=2, dias_desp_ctrl=6)
    r = comparar_cohortes(db, periodo=PER, dias_seguimiento=30)

    assert r["dias_sin_acceso"]["intervenidos"] == -8.0
    assert r["dias_sin_acceso"]["no_intervenidos"] == -4.0
    assert r["dias_sin_acceso"]["efecto_estimado"] == -4.0
    assert r["dias_sin_acceso"]["favorable"] is True        # bajar días es bueno


def test_efecto_contraproducente_se_reporta_como_tal(db):
    """Si a los intervenidos les fue PEOR, no se disimula."""
    _escenario(db, n_trat=12, n_ctrl=40, dias_antes=10, dias_desp_trat=9, dias_desp_ctrl=4)
    r = comparar_cohortes(db, periodo=PER, dias_seguimiento=30)
    assert r["dias_sin_acceso"]["efecto_estimado"] > 0
    assert r["dias_sin_acceso"]["favorable"] is False


# ── negarse a responder cuando no hay datos ──
def test_muestra_insuficiente_no_reporta_efecto(db):
    """Con 3 parejas no se publica una cifra: se dice que no alcanza."""
    _escenario(db, n_trat=3, n_ctrl=40, dias_antes=10, dias_desp_trat=2, dias_desp_ctrl=6)
    r = comparar_cohortes(db, periodo=PER, dias_seguimiento=30)
    assert r["disponible"] is False
    assert "comparación válido" in r["motivo"] or "hacen falta" in r["motivo"]


def test_sin_controles_comparables_no_inventa(db):
    """Controles con baseline muy distinto (1 día vs 10) → no sirven como comparación."""
    _escenario(db, n_trat=12, n_ctrl=40, dias_antes=10, dias_desp_trat=2, dias_desp_ctrl=6)
    for s in db.query(Student).filter(Student.nombre.like("C%")).all():
        for a in db.query(AvacAccess).filter(AvacAccess.student_id == s.id).all():
            a.dias_sin_acceso = 1.0
    db.commit()
    r = comparar_cohortes(db, periodo=PER, dias_seguimiento=30)
    assert r["disponible"] is False
    assert r["descartadas_sin_control"] > 0


def test_sin_intervenciones_no_disponible(db):
    r = comparar_cohortes(db, periodo=PER, dias_seguimiento=30)
    assert r["disponible"] is False


def test_los_controles_nunca_son_intervenidos(db):
    """Un estudiante intervenido no puede ser su propio grupo de control."""
    _escenario(db, n_trat=12, n_ctrl=40, dias_antes=10, dias_desp_trat=2, dias_desp_ctrl=6)
    r = comparar_cohortes(db, periodo=PER, dias_seguimiento=30)
    assert r["controles_por_caso_promedio"] <= 40
