"""La migración no puede perder columnas en silencio.

INCIDENTE: el dict `new_columns` de upgrade_tables() tenía la clave "students" DOS veces.
Python conserva la última y descarta la primera sin avisar, así que 21 columnas nunca se
migraban. En producción eso aparece como "Error interno" en cualquier pantalla que las
toque (psycopg2: column does not exist), y solo se manifiesta al desplegar — los tests no
lo veían porque create_all() sí crea todas las columnas del modelo.
"""
import ast
import re
from pathlib import Path

from sqlalchemy import inspect

from backend.database import Base, engine
from backend.models.student import Student
from backend.models.user import User

FUENTE = Path(__file__).resolve().parents[1] / "database.py"


def _dict_de_migracion_crudo():
    """Devuelve los pares clave→valor SIN colapsar duplicados."""
    src = FUENTE.read_text(encoding="utf-8")
    m = re.search(r"new_columns: dict\[str, list\[tuple\[str, str\]\]\] = (\{.*?\n    \})\n", src, re.S)
    assert m, "no se encontró el literal new_columns"
    nodo = ast.parse("X = " + m.group(1)).body[0].value
    return [(k.value, v) for k, v in zip(nodo.keys, nodo.values)]


def test_migracion_sin_claves_duplicadas():
    """El bug exacto: una tabla repetida hace desaparecer columnas sin ruido."""
    claves = [k for k, _ in _dict_de_migracion_crudo()]
    duplicadas = {k for k in claves if claves.count(k) > 1}
    assert not duplicadas, (
        f"Tablas repetidas en new_columns: {duplicadas}. Python conserva solo la última "
        f"y descarta las anteriores en silencio: esas columnas no se migrarán y "
        f"producción fallará con 'column does not exist'. Fusiona los bloques."
    )


def _columnas_migradas(tabla):
    src = FUENTE.read_text(encoding="utf-8")
    m = re.search(r"new_columns: dict\[str, list\[tuple\[str, str\]\]\] = (\{.*?\n    \})\n", src, re.S)
    return {c for c, _ in ast.literal_eval(m.group(1))[tabla]}


def test_las_columnas_del_retiro_se_migran():
    """Regresión directa del incidente."""
    cols = _columnas_migradas("students")
    for c in ("retirado", "fecha_retiro", "motivo_retiro",
              "retiro_snapshot_dias_sin_acceso", "retiro_snapshot_compromiso",
              "retiro_snapshot_porcentaje_tareas", "retiro_snapshot_nivel_riesgo"):
        assert c in cols, f"'{c}' no se migraría; producción fallaría al consultarla"


def test_el_ambito_por_carrera_se_migra():
    assert "carreras" in _columnas_migradas("users")


def test_no_se_perdieron_columnas_al_fusionar():
    """Las que ya existían deben seguir estando tras juntar los bloques duplicados."""
    cols = _columnas_migradas("students")
    for c in ("whatsapp", "pais", "provincia", "genero", "es_tercera_matricula",
              "cedula_cif", "score_recuperabilidad", "nivel_academico"):
        assert c in cols, f"'{c}' se perdió al fusionar los bloques"
