"""
ETL para reportes de Terceras Matrículas (Oyentes Condicionados).

Lee archivos Excel con la estructura del reporte de solicitudes de tercera matrícula
y los vincula con estudiantes y enrollments existentes en la base de datos.

Todos los estudiantes en el reporte son automáticamente de tercera matrícula.
"""
import logging
import re
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from ..models import Student, Enrollment
from ..models.alert_event import AlertEvent

logger = logging.getLogger(__name__)


def _clean(val) -> str:
    """Convierte a string limpio; '' si NaN/None."""
    s = str(val or "").strip()
    return "" if s.lower() in ("nan", "none", "null", "") else s


def _normalize_email(email: str) -> str:
    """Normaliza email a minúsculas y strip."""
    return email.strip().lower() if email else ""


def transform_terceras_matriculas(carpeta: str) -> pd.DataFrame:
    """
    Lee todos los archivos Excel en la carpeta de terceras matrículas
    y retorna un DataFrame unificado con las columnas relevantes.

    Columns esperadas del reporte:
        PERIODO, CARRERA, IDENTIFICACION_EST, ESTUDIANTE,
        COD_ASIGNATURA, NIVEL, ASIGNATURA, ESTADO_ACTUAL,
        PAGO_MATRICULA, COD_GRUPO, GRUPO, BLOQUE,
        CORREO_ESTUDIANTE, TIPO_APROBACION, DOCENTE, CORREO_DOCENTE
    """
    path = Path(carpeta)
    if not path.exists():
        logger.info("Carpeta de terceras matrículas no existe: %s", carpeta)
        return pd.DataFrame()

    frames = []
    for f in sorted(path.glob("*.xlsx")):
        if f.name.startswith("~"):  # ignorar archivos temporales de Excel
            continue
        try:
            df = pd.read_excel(f, engine="openpyxl")
            df.columns = [c.strip().upper().replace(" ", "_") for c in df.columns]
            frames.append(df)
            logger.info("Terceras matrículas: leído %s (%d filas)", f.name, len(df))
        except Exception as e:
            logger.error("Error leyendo %s: %s", f.name, e)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    return combined


def load_terceras_matriculas(db: Session, carpeta: str) -> dict:
    """
    Carga el reporte de terceras matrículas en la base de datos.

    1. Lee el Excel y normaliza columnas
    2. Vincula cada fila con Student existente por cédula o correo institucional
    3. Marca Student.es_tercera_matricula = True
    4. Crea/actualiza Enrollment con es_tercera_matricula=True, tipo_aprobacion, estado_solicitud
    5. Genera alertas automáticas para estos estudiantes

    Returns dict con estadísticas: matched, unmatched, enrollments_created, alerts_created
    """
    df = transform_terceras_matriculas(carpeta)
    if df.empty:
        return {"matched": 0, "unmatched": 0, "enrollments_created": 0, "alerts_created": 0}

    stats = {
        "matched": 0,
        "unmatched": 0,
        "unmatched_names": [],
        "enrollments_created": 0,
        "enrollments_updated": 0,
        "alerts_created": 0,
    }

    # Pre-cargar mapas de estudiantes para lookup rápido
    all_students = db.query(Student).all()
    cedula_map = {}
    email_map = {}
    for s in all_students:
        if s.cedula:
            cedula_map[s.cedula.strip()] = s
        if s.correo_institucional:
            email_map[_normalize_email(s.correo_institucional)] = s
        if s.correo:
            email_map[_normalize_email(s.correo)] = s

    for _, row in df.iterrows():
        cedula = _clean(row.get("IDENTIFICACION_EST", ""))
        correo = _normalize_email(_clean(row.get("CORREO_ESTUDIANTE", "")))
        nombre = _clean(row.get("ESTUDIANTE", ""))

        # Buscar estudiante por cédula primero, luego por correo
        student = None
        if cedula:
            student = cedula_map.get(cedula)
        if not student and correo:
            student = email_map.get(correo)

        if not student:
            stats["unmatched"] += 1
            if nombre:
                stats["unmatched_names"].append(nombre)
            logger.warning(
                "Tercera matrícula: no se encontró estudiante para %s (cédula=%s, correo=%s)",
                nombre, cedula, correo,
            )
            continue

        stats["matched"] += 1

        # Marcar estudiante como tercera matrícula
        if not student.es_tercera_matricula:
            student.es_tercera_matricula = True

        # Datos de la asignatura
        cod_asignatura = _clean(row.get("COD_ASIGNATURA", ""))
        asignatura = _clean(row.get("ASIGNATURA", ""))
        cod_grupo = _clean(row.get("COD_GRUPO", ""))
        grupo = _clean(row.get("GRUPO", ""))
        carrera = _clean(row.get("CARRERA", ""))
        docente = _clean(row.get("DOCENTE", ""))
        correo_docente = _clean(row.get("CORREO_DOCENTE", ""))
        pago = _clean(row.get("PAGO_MATRICULA", ""))
        estado = _clean(row.get("ESTADO_ACTUAL", ""))
        tipo_aprobacion = _clean(row.get("TIPO_APROBACION", "")) or None
        bloque_raw = row.get("BLOQUE")
        nivel_raw = row.get("NIVEL")

        # Parse periodo
        periodo_raw = row.get("PERIODO")
        periodo = None
        if pd.notna(periodo_raw):
            try:
                periodo = str(int(periodo_raw))
            except (ValueError, TypeError):
                periodo = _clean(str(periodo_raw))

        # Parse nivel y bloque
        nivel = None
        if pd.notna(nivel_raw):
            try:
                nivel = int(nivel_raw)
            except (ValueError, TypeError):
                pass

        bloque = None
        if pd.notna(bloque_raw):
            try:
                bloque = int(bloque_raw)
            except (ValueError, TypeError):
                pass

        # Buscar enrollment existente o crear uno nuevo
        # Buscar por student_id + codigo_asignatura + periodo
        enrollment = None
        if cod_asignatura and periodo:
            enrollment = db.query(Enrollment).filter(
                Enrollment.student_id == student.id,
                Enrollment.codigo_asignatura == cod_asignatura,
                Enrollment.periodo == periodo,
            ).first()

        if not enrollment and cod_grupo and periodo:
            enrollment = db.query(Enrollment).filter(
                Enrollment.student_id == student.id,
                Enrollment.codigo_grupo == cod_grupo,
                Enrollment.periodo == periodo,
            ).first()

        if enrollment:
            # Actualizar enrollment existente
            enrollment.es_tercera_matricula = True
            enrollment.tipo_aprobacion = tipo_aprobacion
            enrollment.estado_solicitud = estado
            if docente and not enrollment.docente:
                enrollment.docente = docente
            if correo_docente and not enrollment.correo_docente:
                enrollment.correo_docente = correo_docente
            if pago:
                enrollment.pagado = pago
            stats["enrollments_updated"] += 1
        else:
            # Crear enrollment nuevo
            new_enrollment = Enrollment(
                student_id=student.id,
                codigo_grupo=cod_grupo or f"3M-{cod_asignatura or 'SIN'}",
                codigo_asignatura=cod_asignatura or None,
                asignatura=asignatura or "Sin asignatura",
                carrera=carrera or student.carrera,
                nivel=nivel,
                nombre_grupo=grupo or None,
                bloque=bloque,
                docente=docente or None,
                correo_docente=correo_docente or None,
                numero_repitencias=3,  # es tercera matrícula
                pagado=pago or None,
                estado_matriculado=estado,
                periodo=periodo,
                es_tercera_matricula=True,
                tipo_aprobacion=tipo_aprobacion,
                estado_solicitud=estado,
            )
            db.add(new_enrollment)
            stats["enrollments_created"] += 1

    db.flush()

    # Generar alertas automáticas para estudiantes de tercera matrícula
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    threshold_date = now - timedelta(days=7)

    # Obtener IDs de estudiantes marcados
    tm_students = db.query(Student).filter(Student.es_tercera_matricula == True).all()

    for student in tm_students:
        # Verificar si ya existe alerta reciente
        existing = db.query(AlertEvent).filter(
            AlertEvent.student_id == student.id,
            AlertEvent.tipo == "tercera_matricula",
            AlertEvent.created_at >= threshold_date,
        ).first()

        if not existing:
            # Contar asignaturas de tercera matrícula
            n_asig = db.query(Enrollment).filter(
                Enrollment.student_id == student.id,
                Enrollment.es_tercera_matricula == True,
            ).count()

            # Verificar si tiene pago pendiente
            sin_pago = db.query(Enrollment).filter(
                Enrollment.student_id == student.id,
                Enrollment.es_tercera_matricula == True,
                Enrollment.pagado.in_(["NO", "no", ""]),
            ).count()

            severidad = "critico"  # tercera matrícula siempre es crítico
            msg_parts = [f"Estudiante con {n_asig} asignatura(s) en tercera matrícula"]
            if sin_pago:
                msg_parts.append(f"{sin_pago} sin pago registrado")

            db.add(AlertEvent(
                student_id=student.id,
                tipo="tercera_matricula",
                severidad=severidad,
                mensaje=" — ".join(msg_parts),
            ))
            stats["alerts_created"] += 1

    db.commit()

    return stats
