"""El ETL debe descartar aulas donde el estudiante ya no está matriculado.

Caso TENESACA: marcado "99 días sin acceso" (RIESGO ALTO) cuando había entrado hacía 2
días. El 99 venía de un aula de PANADERÍA BÁSICA en la que ya no estaba (cambio de grupo).
Como el indicador del estudiante es el MÁXIMO entre aulas, esa aula muerta lo secuestraba.
"""
import pandas as pd

from backend.etl.transformers import filtrar_aulas_matriculadas, calcular_indicadores_estudiantes

CORREO = "ctenesacar@est.ups.edu.ec"


def _ingresos(filas):
    return pd.DataFrame(filas, columns=["correo", "codigo_curso", "dias_sin_acceso",
                                        "nombre_avac", "estado_avac"])


def _matriculas(pares):
    return pd.DataFrame(pares, columns=["correo_institucional", "codigo_grupo"])


def test_descarta_el_aula_fantasma(db):
    """409369 no está entre sus matrículas: fuera."""
    df = _ingresos([
        (CORREO, "409354", 2.0, "TENESACA", "Activo"),    # aula real
        (CORREO, "409369", 99.0, "TENESACA", "Activo"),   # fantasma
    ])
    out = filtrar_aulas_matriculadas(df, _matriculas([(CORREO, "409354")]))
    assert list(out["codigo_curso"]) == ["409354"]


def test_el_indicador_deja_de_estar_secuestrado(db):
    """El caso completo: de 99 días (falso) a 2 (real)."""
    df = _ingresos([
        (CORREO, "409354", 2.0, "TENESACA", "Activo"),
        (CORREO, "409369", 99.0, "TENESACA", "Activo"),
    ])
    master = calcular_indicadores_estudiantes(
        df, pd.DataFrame(), pd.DataFrame(), _matriculas([(CORREO, "409354")]),
    )
    assert master.iloc[0]["dias_sin_acceso_max"] == 2.0, "el aula abandonada ya no manda"


def test_sin_el_filtro_se_reproduce_el_bug(db):
    """Prueba de que el problema era ese: sin matrículas, vuelve el 99."""
    df = _ingresos([
        (CORREO, "409354", 2.0, "TENESACA", "Activo"),
        (CORREO, "409369", 99.0, "TENESACA", "Activo"),
    ])
    master = calcular_indicadores_estudiantes(df, pd.DataFrame(), pd.DataFrame())
    assert master.iloc[0]["dias_sin_acceso_max"] == 99.0


# ── el filtro debe ser conservador: nunca borrar a alguien del seguimiento ──
def test_estudiante_ausente_del_reporte_se_conserva(db):
    """Si no sabemos nada de sus matrículas, no se le toca. Una alerta de más es
    preferible a dejar de vigilar a alguien por un fallo de datos."""
    df = _ingresos([("otro@est.ups.edu.ec", "409369", 99.0, "OTRO", "Activo")])
    out = filtrar_aulas_matriculadas(df, _matriculas([(CORREO, "409354")]))
    assert len(out) == 1


def test_sin_matriculas_no_filtra_nada(db):
    df = _ingresos([(CORREO, "409369", 99.0, "T", "Activo")])
    assert len(filtrar_aulas_matriculadas(df, pd.DataFrame())) == 1
    assert len(filtrar_aulas_matriculadas(df, None)) == 1


def test_tolera_espacios_y_mayusculas_en_el_correo(db):
    df = _ingresos([(f"  {CORREO.upper()}  ", "409354", 2.0, "T", "Activo")])
    out = filtrar_aulas_matriculadas(df, _matriculas([(CORREO, "409354")]))
    assert len(out) == 1, "el cruce no debe fallar por formato del correo"


def test_conserva_todas_las_aulas_legitimas(db):
    df = _ingresos([
        (CORREO, "409354", 2.0, "T", "Activo"),
        (CORREO, "409373", 3.0, "T", "Activo"),
        (CORREO, "409381", 2.0, "T", "Activo"),
        (CORREO, "409369", 99.0, "T", "Activo"),     # única fantasma
    ])
    out = filtrar_aulas_matriculadas(
        df, _matriculas([(CORREO, "409354"), (CORREO, "409373"), (CORREO, "409381")]),
    )
    assert set(out["codigo_curso"]) == {"409354", "409373", "409381"}


def test_ingresos_vacio_no_revienta(db):
    vacio = pd.DataFrame(columns=["correo", "codigo_curso"])
    assert filtrar_aulas_matriculadas(vacio, _matriculas([(CORREO, "1")])).empty
