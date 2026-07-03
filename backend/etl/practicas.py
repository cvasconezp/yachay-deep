"""
ETL para Prácticas Preprofesionales.

Procesa dos fuentes de datos:
1. Formularios Practica P*.xlsx — datos del formulario (estudiante ↔ escuela asignada)
   Hojas: Formularios (principal), Estudiantes (catálogo), Escuelas (resumen)
2. Escuelas Bilingues SEIBE*.xlsx — catálogo de escuelas con ubicación geográfica

El cruce se hace por código AMIE: el formulario tiene el AMIE de la escuela asignada
y el catálogo SEIBE tiene la dirección completa (provincia, cantón, parroquia, dirección).
"""
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from ..models.practica_preprofesional import EscuelaPractica, PracticaPreprofesional
from ..models.student import Student
from ..crypto import blind_index

logger = logging.getLogger(__name__)


def _clean(val) -> str:
    """Limpia un valor: NaN/None → '', quita espacios extra."""
    s = str(val or "").strip()
    return "" if s.lower() in ("nan", "none", "null") else s


def _clean_phone(val) -> str:
    """Limpia un teléfono: quita .0, espacios, guiones."""
    s = _clean(val)
    s = re.sub(r"\.0$", "", s)
    s = re.sub(r"[^0-9+]", "", s)
    return s


def _clean_amie(val) -> str:
    """Limpia código AMIE: quita .0, espacios, convierte a uppercase."""
    s = _clean(val)
    s = re.sub(r"\.0$", "", s)
    return s.strip().upper()


def _clean_cedula(val) -> str:
    """Limpia cédula: quita .0, espacios y rellena con 0 a la izquierda hasta 10 dígitos."""
    s = _clean(val)
    s = re.sub(r"\.0$", "", s)
    s = s.strip()
    # Cédulas ecuatorianas tienen 10 dígitos; si Excel eliminó el 0 inicial, restaurarlo
    if s.isdigit() and len(s) == 9:
        s = s.zfill(10)
    return s


def _parse_nivel_practica(nivel_y_practica: str) -> tuple[str, str]:
    """
    Parsea 'Nivel y Práctica' en (nivel, nombre_practica).
    Ej: '4to nivel - Practica de Modelos Pedagógicos' → ('4to nivel', 'Práctica de Modelos Pedagógicos')
    """
    if " - " in nivel_y_practica:
        parts = nivel_y_practica.split(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    return nivel_y_practica, ""


def load_escuelas_seibe(data_path: str) -> dict[str, dict]:
    """
    Carga el catálogo SEIBE de escuelas bilingües.
    Retorna dict {AMIE_CODE: {zona, provincia, canton, parroquia, direccion, nombre, nacionalidad, lengua}}.
    """
    path = Path(data_path)
    seibe_files = sorted(path.glob("Escuelas Bilingues SEIBE*.xlsx"))
    if not seibe_files:
        logger.warning("No se encontró archivo SEIBE en %s", data_path)
        return {}

    seibe_file = seibe_files[-1]  # Usar el más reciente
    logger.info("Cargando catálogo SEIBE desde: %s", seibe_file.name)

    try:
        df = pd.read_excel(seibe_file, engine="openpyxl")
    except Exception as e:
        logger.error("Error leyendo archivo SEIBE %s: %s", seibe_file, e)
        return {}

    # Normalizar headers
    df.columns = [c.strip().replace("\n", " ").upper() for c in df.columns]

    # Mapear columnas
    col_map = {}
    for c in df.columns:
        if "AMIE" in c or "CODIGO" in c:
            col_map["amie"] = c
        elif "ZONA" in c:
            col_map["zona"] = c
        elif "PROVINCIA" in c:
            col_map["provincia"] = c
        elif "CANTON" in c:
            col_map["canton"] = c
        elif "PARROQUIA" in c:
            col_map["parroquia"] = c
        elif "DIREC" in c:
            col_map["direccion"] = c
        elif "NOMBRE" in c and "INSTIT" in c:
            col_map["nombre"] = c
        elif "NACIONALIDAD" in c:
            col_map["nacionalidad"] = c
        elif "LENGUA" in c:
            col_map["lengua"] = c

    if "amie" not in col_map:
        logger.error("No se encontró columna AMIE en archivo SEIBE")
        return {}

    escuelas = {}
    for _, row in df.iterrows():
        amie = _clean_amie(row.get(col_map["amie"], ""))
        if not amie:
            continue
        escuelas[amie] = {
            "zona": _clean(row.get(col_map.get("zona", ""), "")),
            "provincia": _clean(row.get(col_map.get("provincia", ""), "")),
            "canton": _clean(row.get(col_map.get("canton", ""), "")),
            "parroquia": _clean(row.get(col_map.get("parroquia", ""), "")),
            "direccion": _clean(row.get(col_map.get("direccion", ""), "")),
            "nombre": _clean(row.get(col_map.get("nombre", ""), "")),
            "nacionalidad": _clean(row.get(col_map.get("nacionalidad", ""), "")),
            "lengua": _clean(row.get(col_map.get("lengua", ""), "")),
        }

    logger.info("Catálogo SEIBE: %d escuelas cargadas", len(escuelas))
    return escuelas


def load_formularios_practicas(data_path: str) -> pd.DataFrame:
    """
    Carga la hoja 'Formularios' del archivo de prácticas.
    Retorna DataFrame con columnas normalizadas.
    """
    path = Path(data_path)
    form_files = sorted(path.glob("Formularios Practica*.xlsx"))
    if not form_files:
        logger.warning("No se encontró archivo de formularios de prácticas en %s", data_path)
        return pd.DataFrame()

    form_file = form_files[-1]  # Usar el más reciente
    logger.info("Cargando formularios de prácticas desde: %s", form_file.name)

    # Extraer periodo del nombre (ej: "Formularios Practica P68.xlsx" → "P68")
    match = re.search(r"P(\d+)", form_file.name)
    periodo = f"P{match.group(1)}" if match else None

    try:
        df = pd.read_excel(form_file, sheet_name="Formularios", engine="openpyxl", dtype={"ID ESTUDIANTE": str})
    except Exception as e:
        logger.error("Error leyendo formularios de prácticas %s: %s", form_file, e)
        return pd.DataFrame()

    if df.empty:
        return df

    # Normalizar headers
    df.columns = [c.strip().upper() for c in df.columns]

    # Agregar periodo
    df["_PERIODO"] = periodo

    logger.info("Formularios de prácticas: %d registros cargados (periodo: %s)", len(df), periodo)
    return df


def run_practicas_etl(db: Session, data_path: str) -> dict:
    """
    ETL principal de prácticas preprofesionales.

    1. Carga catálogo SEIBE → upsert escuelas_practica
    2. Carga formularios → cruza con SEIBE → upsert practicas_preprofesionales

    Retorna dict con estadísticas: {escuelas_cargadas, practicas_cargadas, sin_estudiante, errores}
    """
    stats = {
        "escuelas_cargadas": 0,
        "practicas_cargadas": 0,
        "sin_estudiante": 0,
        "errores": [],
    }

    # 1. Cargar y upsert escuelas del catálogo SEIBE
    escuelas_seibe = load_escuelas_seibe(data_path)

    # También cargar escuelas del formulario (hoja Escuelas)
    escuelas_formulario = _load_escuelas_from_formulario(data_path)

    # Merge: SEIBE tiene ubicación, formulario tiene autoridad/sistema educativo
    all_amies = set(escuelas_seibe.keys()) | set(escuelas_formulario.keys())

    for amie in all_amies:
        seibe = escuelas_seibe.get(amie, {})
        form_esc = escuelas_formulario.get(amie, {})

        existing = db.query(EscuelaPractica).filter(EscuelaPractica.amie == amie).first()
        if not existing:
            existing = EscuelaPractica(amie=amie)
            db.add(existing)

        # Datos SEIBE (ubicación geográfica)
        if seibe:
            existing.zona = seibe.get("zona") or existing.zona
            existing.provincia = seibe.get("provincia") or existing.provincia
            existing.canton = seibe.get("canton") or existing.canton
            existing.parroquia = seibe.get("parroquia") or existing.parroquia
            existing.direccion = seibe.get("direccion") or existing.direccion
            existing.nacionalidad = seibe.get("nacionalidad") or existing.nacionalidad
            existing.lengua_predominante = seibe.get("lengua") or existing.lengua_predominante
            if seibe.get("nombre"):
                existing.nombre = seibe["nombre"]

        # Datos del formulario (autoridad, sistema educativo)
        if form_esc:
            existing.nombre = form_esc.get("nombre") or existing.nombre
            existing.distrito = form_esc.get("distrito") or existing.distrito
            existing.sistema_educativo = form_esc.get("sistema") or existing.sistema_educativo
            if form_esc.get("autoridad"):
                existing.nombre_autoridad = form_esc["autoridad"]
            if form_esc.get("cargo"):
                existing.cargo_autoridad = form_esc["cargo"]
            if form_esc.get("telefono"):
                existing.telefono_autoridad = form_esc["telefono"]

        # Derivar jurisdicción desde sistema educativo
        if existing.sistema_educativo:
            if "bilingüe" in existing.sistema_educativo.lower() or "bilingue" in existing.sistema_educativo.lower():
                existing.jurisdiccion = "Intercultural bilingüe"
            else:
                existing.jurisdiccion = "Intercultural (hispana)"

        stats["escuelas_cargadas"] += 1

    db.flush()
    logger.info("Escuelas upserted: %d", stats["escuelas_cargadas"])

    # 2. Cargar formularios y crear prácticas
    df_form = load_formularios_practicas(data_path)
    if df_form.empty:
        logger.warning("No hay formularios de prácticas para procesar")
        db.commit()
        return stats

    # Construir mapa cédula → student_id
    all_cedulas = set()
    for _, row in df_form.iterrows():
        ced = _clean_cedula(row.get("ID ESTUDIANTE", ""))
        if ced:
            all_cedulas.add(ced)

    cedula_to_student = {}
    if all_cedulas:
        _bidx = [blind_index(c) for c in all_cedulas if c]
        students = db.query(Student).filter(Student.cedula_bidx.in_(_bidx)).all()
        for s in students:
            if s.cedula:
                cedula_to_student[s.cedula] = s.id

    # Construir mapa AMIE → escuela_id
    amie_to_escuela = {}
    escuelas = db.query(EscuelaPractica).all()
    for e in escuelas:
        amie_to_escuela[e.amie] = e.id

    # Procesar cada formulario
    periodo = df_form["_PERIODO"].iloc[0] if "_PERIODO" in df_form.columns and len(df_form) > 0 else None

    for _, row in df_form.iterrows():
        cedula = _clean_cedula(row.get("ID ESTUDIANTE", ""))
        if not cedula:
            continue

        student_id = cedula_to_student.get(cedula)
        if not student_id:
            stats["sin_estudiante"] += 1
            continue

        amie = _clean_amie(row.get("AMIE ESCUELA", ""))
        escuela_id = amie_to_escuela.get(amie) if amie else None

        nivel_y_practica = _clean(row.get("NIVEL Y PRÁCTICA", "") or row.get("NIVEL Y PRACTICA", ""))
        nivel, nombre_practica = _parse_nivel_practica(nivel_y_practica)

        # Timestamp del formulario
        ts_raw = row.get("TIMESTAMP")
        timestamp = None
        if pd.notna(ts_raw):
            try:
                if isinstance(ts_raw, str):
                    timestamp = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                elif isinstance(ts_raw, datetime):
                    timestamp = ts_raw
            except Exception:
                pass

        # Buscar escuela para datos denormalizados
        seibe = escuelas_seibe.get(amie, {})
        ubicacion_parts = []
        for part in [seibe.get("canton"), seibe.get("parroquia"), seibe.get("direccion")]:
            if part:
                ubicacion_parts.append(part)
        ubicacion = ", ".join(ubicacion_parts) if ubicacion_parts else None

        # Upsert: por student_id + periodo + amie (una práctica por tipo por período)
        existing = (
            db.query(PracticaPreprofesional)
            .filter(
                PracticaPreprofesional.student_id == student_id,
                PracticaPreprofesional.periodo == periodo,
                PracticaPreprofesional.amie_escuela == amie,
            )
            .first()
        )

        if not existing:
            existing = PracticaPreprofesional(
                student_id=student_id,
                periodo=periodo,
                amie_escuela=amie,
            )
            db.add(existing)

        existing.escuela_id = escuela_id
        existing.nombre_practica = nombre_practica
        existing.nivel_practica = nivel
        existing.nivel_y_practica = nivel_y_practica
        existing.centro_apoyo = _clean(row.get("CENTRO DE APOYO", ""))
        existing.en_mineduc = _clean(row.get("MINEDUC", ""))
        existing.nombre_escuela = _clean(row.get("NOMBRE ESCUELA", ""))
        existing.distrito = _clean(row.get("DISTRITO", ""))
        existing.sistema_educativo = _clean(row.get("SISTEMA EDUCATIVO", ""))
        existing.ubicacion_escuela = ubicacion
        existing.nombre_autoridad = _clean(row.get("NOMBRE AUTORIDAD", ""))
        existing.cargo_autoridad = _clean(row.get("CARGO AUTORIDAD", ""))
        existing.telefono_autoridad = _clean_phone(row.get("TELÉFONO AUTORIDAD", "") or row.get("TELEFONO AUTORIDAD", ""))
        existing.timestamp_formulario = timestamp

        stats["practicas_cargadas"] += 1

    db.commit()
    logger.info(
        "Prácticas ETL completado: %d escuelas, %d prácticas, %d sin estudiante",
        stats["escuelas_cargadas"], stats["practicas_cargadas"], stats["sin_estudiante"],
    )
    return stats


def _load_escuelas_from_formulario(data_path: str) -> dict[str, dict]:
    """
    Carga la hoja 'Escuelas' del archivo de formularios.
    Retorna dict {AMIE: {nombre, distrito, sistema, autoridad, cargo, telefono}}.
    """
    path = Path(data_path)
    form_files = sorted(path.glob("Formularios Practica*.xlsx"))
    if not form_files:
        return {}

    try:
        df = pd.read_excel(form_files[-1], sheet_name="Escuelas", engine="openpyxl")
    except Exception:
        return {}

    if df.empty:
        return {}

    df.columns = [c.strip().upper() for c in df.columns]

    escuelas = {}
    for _, row in df.iterrows():
        amie = _clean_amie(row.get("AMIE", ""))
        if not amie:
            continue
        escuelas[amie] = {
            "nombre": _clean(row.get("NOMBRE", "")),
            "distrito": _clean(row.get("DISTRITO", "")),
            "sistema": _clean(row.get("SISTEMA", "")),
            "autoridad": _clean(row.get("AUTORIDAD", "")),
            "cargo": _clean(row.get("CARGO", "")),
            "telefono": _clean_phone(row.get("TELÉFONO", "") or row.get("TELEFONO", "")),
        }

    return escuelas
