"""
Endpoints de estudiantes — equivalente a la lógica de FichaEst.
Búsqueda por nombre/correo/cédula y vista de ficha completa.
"""
from typing import Optional
from collections import Counter
from pathlib import Path
import json
import time
import logging
import re
import unicodedata
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from pydantic import BaseModel
from datetime import datetime, date

logger = logging.getLogger(__name__)

from ..database import get_db
from ..models import Student, AvacAccess, TaskSubmission, Grade, Intervention, PracticaPreprofesional, EscuelaPractica, Enrollment
from ..models.course_config import CourseConfig
from ..auth.jwt import get_current_user
from ..models.user import User
from ..constants import EIB_GRUPO_SEDE_STR as SEDE_MAPPING

router = APIRouter(prefix="/students", tags=["students"])

# ── Caché en memoria para malla canónica por carrera (evita recalcular por cada estudiante) ──
# Estructura: { "CARRERA_UPPER": (timestamp, canonical_dict) }
_canonical_cache: dict[str, tuple[float, dict[str, int]]] = {}
_CANONICAL_CACHE_TTL = 600  # 10 minutos

# ── Directorio de mallas de referencia (JSONs oficiales) ──
_MALLAS_DIR = Path(__file__).resolve().parent.parent / "data" / "mallas"


def _strip_accents(text: str) -> str:
    """Elimina acentos/diacríticos de un string Unicode."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _normalize_asig(name: str) -> str:
    """Normaliza nombre de asignatura: upper, colapsa whitespace/newlines,
    elimina artefactos de Excel (_x000d_, _x000a_)."""
    clean = re.sub(r"_x[0-9a-fA-F]{4}_", " ", name)  # artefactos Excel
    clean = re.sub(r"[\r\n]+", " ", clean)              # newlines
    return re.sub(r"\s+", " ", clean.strip().upper())


def _career_to_filename(carrera_upper: str) -> str:
    """
    Convierte nombre de carrera a nombre de archivo JSON.
    Ej: 'EDUCACIÓN INTERCULTURAL BILINGÜE' -> 'EDUCACION_INTERCULTURAL_BILINGUE.json'
    """
    clean = _strip_accents(carrera_upper)
    clean = clean.replace(" ", "_")
    # Quitar caracteres que no sean alfanuméricos o guión bajo
    clean = "".join(c for c in clean if c.isalnum() or c == "_")
    return f"{clean}.json"


def _load_reference_malla(carrera_upper: str) -> dict[str, int] | None:
    """
    Intenta cargar la malla canónica desde un archivo JSON de referencia.
    Retorna dict {ASIGNATURA_UPPER: nivel_int} o None si no existe.
    """
    filename = _career_to_filename(carrera_upper)
    filepath = _MALLAS_DIR / filename
    if not filepath.exists():
        logger.debug("No hay malla de referencia para %s (buscado: %s)", carrera_upper, filepath)
        return None

    try:
        data = json.loads(filepath.read_text(encoding="utf-8"))
        niveles = data.get("niveles", {})
        canonical: dict[str, int] = {}
        for nivel_str, asignaturas in niveles.items():
            nivel_int = int(nivel_str)
            for asig in asignaturas:
                canonical[_normalize_asig(asig)] = nivel_int
        logger.info(
            "Malla de referencia cargada para %s: %d asignaturas desde %s",
            carrera_upper, len(canonical), filename,
        )
        return canonical
    except Exception as e:
        logger.error("Error cargando malla de referencia %s: %s", filepath, e)
        return None

def detectar_sede(course_configs: list, student_grupo: str = None) -> Optional[str]:
    """
    Determina la sede (centro de apoyo) del estudiante.

    Prioridad:
      1. Student.grupo (del reporte institucional — fuente de verdad)
      2. Votación mayoritaria de CourseConfig.grupo (AVAC, menos fiable)
    """
    # Prioridad 1: grupo del reporte institucional (fuente de verdad)
    if student_grupo:
        grupo_str = str(student_grupo).strip()
        if grupo_str and grupo_str.lower() not in ("nan", "none", ""):
            return SEDE_MAPPING.get(grupo_str, f"Grupo-{grupo_str}")

    # Prioridad 2: votación mayoritaria de CourseConfig.grupo
    grupos = [str(c.grupo).strip() for c in course_configs if c.grupo]
    if not grupos:
        return None
    mayoritario = Counter(grupos).most_common(1)[0][0]
    return SEDE_MAPPING.get(mayoritario, f"Grupo-{mayoritario}")


def detectar_nivel(course_configs: list) -> Optional[str]:
    """
    Detecta el semestre activo más frecuente y lo formatea como nivel académico.
    Se basa en la cantidad de asignaturas activas del estudiante.
    """
    NIVELES = {
        "1": "Primer nivel", "2": "Segundo nivel", "3": "Tercer nivel",
        "4": "Cuarto nivel", "5": "Quinto nivel", "6": "Sexto nivel",
        "7": "Séptimo nivel", "8": "Octavo nivel",
    }
    # Usar el campo 'bloque' para detectar si están en bloque 1 o 2
    bloques = [str(c.bloque).strip() for c in course_configs if c.bloque]
    if not bloques:
        return None
    bloque_mayoritario = Counter(bloques).most_common(1)[0][0]
    # Si solo hay datos de semestre, intentar extraer un nivel
    semestres = [str(c.semestre).strip() for c in course_configs if c.semestre]
    if semestres:
        return f"Semestre {Counter(semestres).most_common(1)[0][0]}"
    return None


# ─── Diagnóstico de riesgo académico (Framework_FichaEst §3.5) ───────────────
NOVEDADES_AUSENTISMO = frozenset([
    "no ingresa regularmente al avac",
    "incumplimiento de actividades",
    "ausencia avac",
    "inactividad",
])
NOVEDADES_NOTAS = frozenset([
    "bajas calificaciones",
    "nota cero",
    "calificaciones bajas",
])

def diagnosticar_riesgo(
    estado_matricula: Optional[str],
    indice_compromiso: Optional[float],
    intervenciones: list,
) -> str:
    """
    Árbol de decisión de riesgo según Framework_FichaEst §3.5:
    1. Pago matrícula → En riesgo
    2. Compromiso Bajo o novedades ausentismo → Riesgo de Deserción
    3. Compromiso Medio o novedades de notas → Riesgo Académico
    4. Compromiso Alto → Aprobación
    """
    # Prioridad 1: pago de matrícula
    pago_ok = bool(estado_matricula and "matriculad" in estado_matricula.lower())
    if not pago_ok:
        return "En riesgo"

    # Novedades del historial
    motivos = {(inv.motivo or "").lower() for inv in intervenciones}
    nov_ausent = bool(motivos & NOVEDADES_AUSENTISMO)
    nov_notas  = bool(motivos & NOVEDADES_NOTAS)

    # Sin datos de compromiso: solo novedades pueden determinar riesgo
    if indice_compromiso is None:
        if nov_ausent:
            return "Riesgo de Deserción"
        if nov_notas:
            return "Riesgo Académico"
        return "Datos insuficientes"

    # Clasificar índice de compromiso
    es_alto  = indice_compromiso >= 0.6
    es_medio = 0.3 <= indice_compromiso < 0.6
    es_bajo  = indice_compromiso < 0.3

    if es_bajo or nov_ausent:
        return "Riesgo de Deserción"
    if es_medio or nov_notas:
        return "Riesgo Académico"
    if es_alto:
        return "Aprobación"
    return "Datos insuficientes"


# ─── Schemas ─────────────────────────────────────────────────────────────────

class StudentSummary(BaseModel):
    id: int
    cedula: Optional[str] = None
    nombre: Optional[str] = None
    correo_institucional: Optional[str] = None
    carrera: Optional[str] = None
    nivel_riesgo: Optional[str] = None
    indice_compromiso: Optional[float] = None
    dias_sin_acceso: Optional[int] = None
    porcentaje_tareas: Optional[float] = None

    class Config:
        from_attributes = True


class TaskSubmissionOut(BaseModel):
    codigo_curso: str
    nombre_curso: Optional[str] = None   # enriquecido desde Course.nombre
    unidad: Optional[str] = None
    estado: Optional[str] = None
    calificacion: Optional[float] = None
    calificacion_maxima: Optional[float] = None
    calificacion_final: Optional[float] = None
    total_curso: Optional[float] = None  # nota total del curso (desde Tareas CSV "Total del Curso")
    entregada: bool = False
    calificada: bool = False
    retrasada: bool = False

    class Config:
        from_attributes = True


class AvacAccessOut(BaseModel):
    codigo_curso: str
    nombre_curso: Optional[str] = None   # enriquecido desde Course.nombre
    docente: Optional[str] = None         # enriquecido desde Course.docente
    nivel: Optional[int] = None           # nivel académico del curso (1-8) desde CourseConfig
    grupo: Optional[str] = None           # grupo/sección extraído de NOMBRE_GRUPO
    bloque: Optional[str] = None          # bloque del curso: "1", "2" o "ambos"
    ultimo_acceso_texto: Optional[str] = None
    dias_sin_acceso: Optional[float] = None
    estado_avac: Optional[str] = None
    fecha_extraccion: Optional[datetime] = None

    class Config:
        from_attributes = True


class GradeOut(BaseModel):
    asignatura: str
    nota_final: Optional[float] = None
    docente: Optional[str] = None
    grupo: Optional[str] = None
    periodo: Optional[str] = None   # None = semestre actual; "P60"–"P67" = histórico
    numero_repitencias: Optional[int] = None
    nivel: Optional[int] = None     # academic level of the subject (1-8)

    class Config:
        from_attributes = True


class EnrollmentOut(BaseModel):
    """Asignatura matriculada desde el reporte institucional."""
    codigo_grupo: str                           # CODIGO_GRUPO (AVAC course ID)
    codigo_asignatura: Optional[str] = None     # CODIGO_ASIGNATURA (plan de estudios)
    asignatura: str                             # nombre de la asignatura
    tipo_asignatura: Optional[str] = None       # COMUN/GENERICA/ESPECIFICA
    carrera: Optional[str] = None
    nivel: Optional[int] = None                 # nivel académico (1-8)
    nombre_grupo: Optional[str] = None          # NOMBRE_GRUPO completo
    bloque: Optional[int] = None                # bloque 1 o 2
    docente: Optional[str] = None
    correo_docente: Optional[str] = None
    numero_repitencias: Optional[int] = None
    pagado: Optional[str] = None                # SI/NO
    estado_matriculado: Optional[str] = None
    periodo: Optional[str] = None               # "68"
    fecha_matricula: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Schemas para Malla Curricular fija ────────────────────────────────────────

class MallaIntento(BaseModel):
    """Un intento de cursar una asignatura (un registro en un período)."""
    periodo: Optional[str] = None
    nota: Optional[float] = None
    estado: str  # aprobada | reprobada | cursando

class MallaAsignatura(BaseModel):
    """Una asignatura dentro de la malla canónica."""
    nombre: str
    nivel_canonico: int
    intentos: list[MallaIntento] = []
    nota_vigente: Optional[float] = None
    estado: str  # aprobada | reprobada | cursando | no_cursado
    es_repeticion: bool = False
    num_intentos: int = 0

class MallaSemestre(BaseModel):
    """Un semestre/nivel de la malla canónica."""
    numero: int
    asignaturas: list[MallaAsignatura] = []
    promedio: Optional[float] = None

class MallaCurricular(BaseModel):
    """Malla curricular completa del estudiante."""
    carrera: Optional[str] = None
    total_semestres: int = 0
    semestres: list[MallaSemestre] = []
    total_aprobadas: int = 0
    total_reprobadas: int = 0
    total_cursando: int = 0
    total_no_cursado: int = 0
    total_asignaturas_malla: int = 0


class PracticaOut(BaseModel):
    """Práctica preprofesional asignada a un estudiante."""
    id: int
    nombre_practica: Optional[str] = None
    nivel_practica: Optional[str] = None
    nivel_y_practica: Optional[str] = None
    centro_apoyo: Optional[str] = None
    en_mineduc: Optional[str] = None
    amie_escuela: Optional[str] = None
    nombre_escuela: Optional[str] = None
    distrito: Optional[str] = None
    sistema_educativo: Optional[str] = None
    ubicacion_escuela: Optional[str] = None   # Cantón, Parroquia, Dirección (cruzado desde SEIBE)
    jurisdiccion: Optional[str] = None        # Derivado del sistema educativo
    nombre_autoridad: Optional[str] = None
    cargo_autoridad: Optional[str] = None
    telefono_autoridad: Optional[str] = None
    periodo: Optional[str] = None

    class Config:
        from_attributes = True


class InterventionOut(BaseModel):
    id: int
    monitor_nombre: Optional[str] = None
    medio: Optional[str] = None
    motivo: Optional[str] = None
    estado: Optional[str] = None
    asignatura: Optional[str] = None
    observacion: Optional[str] = None
    resultado: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FichaEstudiante(BaseModel):
    # Datos del estudiante
    id: int
    cedula: Optional[str] = None
    nombre: Optional[str] = None
    correo_institucional: Optional[str] = None
    correo: Optional[str] = None
    telefono: Optional[str] = None
    whatsapp: Optional[str] = None           # número WhatsApp (DatosEspecificos o reporte)
    carrera: Optional[str] = None
    sede: Optional[str] = None               # sede almacenada en BD (puede ser vacía)
    sede_detectada: Optional[str] = None     # sede derivada por votación mayoritaria de grupos
    nivel_detectado: Optional[str] = None    # nivel/semestre activo detectado
    nivel_academico: Optional[int] = None    # nivel académico del estudiante (1-8), desde DatosEspecificos
    estado_matricula: Optional[str] = None

    # Datos demográficos (desde reporte institucional)
    fecha_nacimiento: Optional[date] = None
    genero: Optional[str] = None
    autoidentificacion_etnica: Optional[str] = None
    grupo_reporte: Optional[str] = None  # grupo del reporte institucional ("3", "2", etc.)

    # Residencia
    pais: Optional[str] = None
    provincia: Optional[str] = None
    ciudad: Optional[str] = None             # ciudad / cantón
    parroquia: Optional[str] = None          # parroquia (solo DatosEspecificos)
    barrio: Optional[str] = None             # barrio o comunidad

    # Indicadores de riesgo
    nivel_riesgo: Optional[str] = None
    indice_compromiso: Optional[float] = None
    dias_sin_acceso: Optional[int] = None
    porcentaje_tareas: Optional[float] = None
    promedio_calificaciones: Optional[float] = None
    diagnostico_riesgo: Optional[str] = None  # diagnóstico computado: Aprobación/Riesgo Académico/etc.

    # Predicciones ML (Fase 2)
    prob_desercion: Optional[float] = None
    prob_reprobacion: Optional[float] = None
    prediccion_updated_at: Optional[datetime] = None

    # Datos relacionados
    accesos_avac: list[AvacAccessOut] = []
    tareas: list[TaskSubmissionOut] = []
    calificaciones: list[GradeOut] = []          # semestre actual (periodo IS NULL)
    calificaciones_historicas: list[GradeOut] = []  # histórico (periodo IS NOT NULL), ordenado por periodo
    intervenciones: list[InterventionOut] = []
    malla_curricular: Optional[MallaCurricular] = None  # malla fija por niveles

    # Asignaturas matriculadas (desde reporte institucional)
    enrollments: list[EnrollmentOut] = []

    # Prácticas preprofesionales
    practicas_preprofesionales: list[PracticaOut] = []

    # Resumen
    total_intervenciones: int = 0
    ultima_intervencion: Optional[datetime] = None

    # Período consultado (para el selector de período en el frontend)
    periodo_consulta: Optional[str] = None      # e.g. "P68" — periodo que se está viendo
    periodo_es_actual: bool = True               # True si es el semestre activo

    class Config:
        from_attributes = True


# ─── Schemas paginación [PERF-01] ────────────────────────────────────────────

class PaginatedStudents(BaseModel):
    """Respuesta paginada de estudiantes."""
    items: list[StudentSummary]
    total: int
    page: int
    pages: int
    limit: int

    class Config:
        from_attributes = True


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/search", response_model=PaginatedStudents)
def search_students(
    q: str = Query("", description="Nombre, correo institucional, cédula o teléfono"),
    carrera: str = Query("", description="Filtrar por carrera (vacío = todas)"),
    nivel_riesgo: str = Query("", description="Filtrar por nivel de riesgo: Alto, Medio, Bajo"),
    page: int = Query(1, ge=1, description="Página (empieza en 1)"),
    limit: int = Query(50, ge=1, le=200, description="Resultados por página"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    [PERF-01] Búsqueda paginada de estudiantes.
    Búsqueda triple: nombre / correo / cédula.
    Si se pasa carrera, filtra por carrera (y permite q vacío para listar).
    """
    query = db.query(Student)

    # Filtro por carrera
    if carrera.strip():
        query = query.filter(func.lower(Student.carrera) == carrera.strip().lower())

    # Filtro por nivel de riesgo
    if nivel_riesgo.strip():
        query = query.filter(Student.nivel_riesgo == nivel_riesgo.strip())

    # Filtro de búsqueda textual
    q_lower = q.lower().strip()
    if q_lower and len(q_lower) >= 2:
        query = query.filter(
            or_(
                func.lower(Student.nombre).contains(q_lower),
                func.lower(Student.correo_institucional).contains(q_lower),
                Student.cedula == q.strip(),
                func.lower(Student.telefono).contains(q_lower),
            )
        )
    elif not carrera.strip() and not nivel_riesgo.strip():
        return PaginatedStudents(items=[], total=0, page=1, pages=0, limit=limit)

    # [PERF-01] Paginación server-side
    total = query.count()
    offset = (page - 1) * limit
    pages = (total + limit - 1) // limit  # ceil division

    results = query.order_by(Student.nombre).offset(offset).limit(limit).all()

    return PaginatedStudents(
        items=results, total=total, page=page, pages=pages, limit=limit,
    )


# ── Construcción de Malla Curricular Canónica ─────────────────────────────────

def _get_canonical_for_career(db: Session, carrera: str) -> dict[str, int]:
    """
    Obtiene el diccionario canónico {ASIGNATURA_UPPER: nivel} para una carrera.
    Usa caché en memoria con TTL de 10 minutos para evitar recalcular
    en cada request (la malla canónica no cambia frecuentemente).
    """
    carrera_key = carrera.upper()
    now = time.time()

    # Verificar caché
    if carrera_key in _canonical_cache:
        ts, cached = _canonical_cache[carrera_key]
        if now - ts < _CANONICAL_CACHE_TTL:
            logger.debug("Malla canónica para %s: caché hit", carrera_key)
            return cached

    # ── Prioridad 1: Malla de referencia (JSON oficial) ──
    ref = _load_reference_malla(carrera_key)
    if ref is not None:
        _canonical_cache[carrera_key] = (now, ref)
        return ref

    # ── Prioridad 2: Inferencia desde datos (fallback) ──
    logger.info("Calculando malla canónica por inferencia para %s...", carrera_key)
    t0 = time.time()

    # Usar subquery en lugar de IN con lista enorme de IDs
    career_subq = (
        db.query(Student.id)
        .filter(func.upper(Student.carrera) == carrera_key)
        .subquery()
    )

    # Filtro estricto: SOLO grades cuya carrera coincida explícitamente.
    # NO permitimos Grade.carrera=NULL porque grades huérfanas de otras
    # carreras (ej. estudiantes que cambiaron de carrera) contaminarían
    # la malla canónica con asignaturas que no corresponden.
    _career_grade_filter = func.upper(Grade.carrera) == carrera_key

    # ── Estrategia A: nivel explícito ──
    all_career_grades_with_nivel = (
        db.query(Grade.asignatura, Grade.nivel)
        .filter(
            Grade.student_id.in_(db.query(career_subq.c.id)),
            _career_grade_filter,
            Grade.nivel.isnot(None),
            Grade.nivel >= 1,
            Grade.nivel <= 12,
        )
        .all()
    )

    asig_nivel_counts: dict[str, Counter] = {}
    for asig, nivel in all_career_grades_with_nivel:
        asig_upper = _normalize_asig(asig)
        if asig_upper not in asig_nivel_counts:
            asig_nivel_counts[asig_upper] = Counter()
        asig_nivel_counts[asig_upper][nivel] += 1

    canonical: dict[str, int] = {}
    for asig_upper, counter in asig_nivel_counts.items():
        canonical[asig_upper] = counter.most_common(1)[0][0]

    # ── Estrategia B: inferir nivel usando "estudiantes modelo" ──
    all_career_grades_hist = (
        db.query(Grade.student_id, Grade.asignatura, Grade.periodo)
        .filter(
            Grade.student_id.in_(db.query(career_subq.c.id)),
            _career_grade_filter,
            Grade.periodo.isnot(None),
        )
        .all()
    )

    if all_career_grades_hist:
        student_grades_grouped: dict[int, list] = {}
        for sid, asig, periodo in all_career_grades_hist:
            student_grades_grouped.setdefault(sid, []).append((asig, periodo))

        model_student_ids = []
        for sid, grades_list in student_grades_grouped.items():
            periodos_unicos = set(p for _, p in grades_list)
            if len(periodos_unicos) < 4:
                continue
            asig_periodos: dict[str, set] = {}
            for asig, periodo in grades_list:
                asig_upper = _normalize_asig(asig)
                asig_periodos.setdefault(asig_upper, set()).add(periodo)
            has_retake = any(len(ps) > 1 for ps in asig_periodos.values())
            if not has_retake:
                model_student_ids.append((sid, len(periodos_unicos)))

        model_student_ids.sort(key=lambda x: -x[1])
        top_models = [sid for sid, _ in model_student_ids[:30]]

        if len(top_models) < 5:
            model_set = {s for s, _ in model_student_ids}
            for sid, grades_list in student_grades_grouped.items():
                if sid in model_set:
                    continue
                periodos_unicos = set(p for _, p in grades_list)
                if len(periodos_unicos) < 3:
                    continue
                asig_periodos_r: dict[str, set] = {}
                for asig, periodo in grades_list:
                    asig_upper = _normalize_asig(asig)
                    asig_periodos_r.setdefault(asig_upper, set()).add(periodo)
                retake_count = sum(1 for ps in asig_periodos_r.values() if len(ps) > 1)
                if retake_count <= 1:
                    top_models.append(sid)
                if len(top_models) >= 15:
                    break

        inferred_counts: dict[str, Counter] = {}
        for sid in top_models:
            grades_list = student_grades_grouped[sid]
            periodos_unicos = sorted(set(p for _, p in grades_list))
            periodo_to_nivel = {p: (i + 1) for i, p in enumerate(periodos_unicos)}

            asig_primer_periodo: dict[str, str] = {}
            for asig, periodo in sorted(grades_list, key=lambda x: x[1]):
                asig_upper = _normalize_asig(asig)
                if asig_upper not in asig_primer_periodo:
                    asig_primer_periodo[asig_upper] = periodo

            for asig_upper, primer_periodo in asig_primer_periodo.items():
                nivel_inferido = periodo_to_nivel[primer_periodo]
                if asig_upper not in inferred_counts:
                    inferred_counts[asig_upper] = Counter()
                inferred_counts[asig_upper][nivel_inferido] += 1

        min_apariciones = 2 if len(top_models) >= 5 else 1
        for asig_upper, counter in inferred_counts.items():
            total_apariciones = sum(counter.values())
            if total_apariciones >= min_apariciones and asig_upper not in canonical:
                canonical[asig_upper] = counter.most_common(1)[0][0]

    # ── Prioridad 3: Inferencia desde Enrollments (matrícula sin grades) ──
    # Para carreras nuevas o estudiantes sin histórico, usar asignaturas
    # matriculadas como fuente de la malla canónica.
    if not canonical:
        from ..models import Enrollment as EnrollmentModel
        enrollment_asigs = (
            db.query(EnrollmentModel.asignatura, EnrollmentModel.nivel)
            .filter(
                func.upper(EnrollmentModel.carrera) == carrera_key,
                EnrollmentModel.nivel.isnot(None),
                EnrollmentModel.nivel >= 1,
            )
            .distinct()
            .all()
        )
        if enrollment_asigs:
            enr_nivel_counts: dict[str, Counter] = {}
            for asig, nivel in enrollment_asigs:
                asig_upper = _normalize_asig(asig)
                # Filtrar PRÁCTICA duplicadas
                if "PRÁCTICA" in asig_upper or "PRACTICA" in asig_upper:
                    continue
                if asig_upper not in enr_nivel_counts:
                    enr_nivel_counts[asig_upper] = Counter()
                enr_nivel_counts[asig_upper][nivel] += 1
            for asig_upper, counter in enr_nivel_counts.items():
                if asig_upper not in canonical:
                    canonical[asig_upper] = counter.most_common(1)[0][0]
            logger.info("Malla desde enrollments para %s: +%d asignaturas", carrera_key, len(canonical))

    elapsed = time.time() - t0
    logger.info("Malla canónica para %s: %d asignaturas en %.2fs", carrera_key, len(canonical), elapsed)

    # Guardar en caché
    _canonical_cache[carrera_key] = (now, canonical)
    return canonical


def _build_malla_canonica(
    db: Session,
    student: "Student",
    calificaciones_hist: list["Grade"],
    calificaciones_actual: list["Grade"],
    enrollments: list["Enrollment"] | None = None,
) -> tuple["MallaCurricular", dict[str, int]]:
    """
    Construye la malla curricular fija del estudiante.

    Retorna (MallaCurricular, canonical_dict) donde canonical_dict es
    {ASIGNATURA_UPPER: nivel_canonico} para reutilizar al normalizar
    el nivel de las calificaciones del semestre actual.

    Si hay enrollments (asignaturas matriculadas del reporte) sin Grade
    correspondiente, se registran como "cursando" en la malla.
    """
    carrera = student.carrera
    if not carrera:
        return MallaCurricular(), {}

    # ── 1. Obtener malla canónica (con caché) ──
    canonical = _get_canonical_for_career(db, carrera)

    if not canonical:
        return MallaCurricular(carrera=carrera), {}

    # ── 2. Construir estructura de semestres ──
    # Agrupar asignaturas canónicas por nivel
    niveles_asigs: dict[int, list[str]] = {}
    for asig_upper, niv in canonical.items():
        if niv not in niveles_asigs:
            niveles_asigs[niv] = []
        niveles_asigs[niv].append(asig_upper)

    # Ordenar asignaturas dentro de cada nivel alfabéticamente
    for niv in niveles_asigs:
        niveles_asigs[niv].sort()

    max_nivel = max(niveles_asigs.keys()) if niveles_asigs else 0

    # ── 3. Recopilar calificaciones del estudiante indexadas por asignatura ──
    # Todas las calificaciones (hist + actuales) agrupadas por asignatura
    student_grades_map: dict[str, list] = {}  # asig_normalized → [Grade]
    for g in calificaciones_hist:
        key = _normalize_asig(g.asignatura)
        student_grades_map.setdefault(key, []).append(g)
    for g in calificaciones_actual:
        key = _normalize_asig(g.asignatura)
        student_grades_map.setdefault(key, []).append(g)

    # ── 3b. Inyectar enrollments como "cursando" si no tienen Grade ──
    if enrollments:
        # Deduplicar enrollments por asignatura (filtrar PRÁCTICA)
        seen_enr: dict[str, "Enrollment"] = {}
        for enr in enrollments:
            key_enr = _normalize_asig(enr.asignatura)
            is_practica = "PRÁCTICA" in (enr.nombre_grupo or "").upper() or \
                          "PRACTICA" in (enr.nombre_grupo or "").upper()
            if key_enr not in seen_enr:
                seen_enr[key_enr] = enr
            elif is_practica:
                pass  # keep existing non-práctica entry
            else:
                seen_enr[key_enr] = enr  # replace práctica with main group

        # Para cada enrollment, si no hay Grade, crear entrada sintética "cursando"
        class _SyntheticGrade:
            """Objeto ligero que imita Grade para inyectar cursando."""
            def __init__(self, asignatura: str, periodo: str):
                self.asignatura = asignatura
                self.periodo = periodo
                self.nota_final = None

        def _find_canon_key(enr_key: str) -> str | None:
            """Busca la clave canónica que mejor corresponde a un enrollment."""
            if enr_key in canonical:
                return enr_key
            # Match por contenido: la clave más larga que sea substring o viceversa
            best = None
            best_len = 0
            for ck in canonical:
                # Comparar: si uno contiene al otro (tolerante a nombres largos del reporte)
                if ck in enr_key or enr_key in ck:
                    overlap = min(len(ck), len(enr_key))
                    if overlap > best_len:
                        best = ck
                        best_len = overlap
            return best

        for key_enr, enr in seen_enr.items():
            # Buscar si ya tiene grade (exacta o por clave canónica)
            canon_match = _find_canon_key(key_enr)
            target_key = canon_match or key_enr

            if target_key not in student_grades_map:
                student_grades_map[target_key] = [
                    _SyntheticGrade(enr.asignatura, enr.periodo or "actual")
                ]

    # ── 4. Construir la respuesta ──
    semestres = []
    total_aprobadas = 0
    total_reprobadas = 0
    total_cursando = 0
    total_no_cursado = 0

    # ── PERF: pre-cargar nombres display para asignaturas canónicas sin Grade ──
    # Antes hacíamos un query por cada asignatura faltante (N+1 → ~50 queries
    # con func.upper() que no usa índice). Ahora una sola query batched.
    missing_asigs: set[str] = set()
    for niv in range(1, max_nivel + 1):
        for asig_upper in niveles_asigs.get(niv, []):
            if not student_grades_map.get(asig_upper):
                missing_asigs.add(asig_upper)

    display_names: dict[str, str] = {}
    if missing_asigs:
        try:
            # Buscar una muestra del nombre original (primera coincidencia normalizada)
            # Usamos ILIKE con upper para compatibilidad postgres/sqlite sin índice funcional.
            samples = (
                db.query(Grade.asignatura)
                .filter(func.upper(Grade.asignatura).in_(list(missing_asigs)))
                .distinct()
                .all()
            )
            for (asig,) in samples:
                if not asig:
                    continue
                key = _normalize_asig(asig)
                if key in missing_asigs and key not in display_names:
                    display_names[key] = asig.strip()
        except Exception as exc:  # pragma: no cover — fallback a asig_upper
            logger.warning("No se pudo pre-cargar nombres de asignaturas: %s", exc)

    for niv in range(1, max_nivel + 1):
        asigs_en_nivel = niveles_asigs.get(niv, [])
        malla_asigs = []
        notas_nivel = []

        for asig_upper in asigs_en_nivel:
            grades = student_grades_map.get(asig_upper, [])

            # Construir intentos ordenados por período
            intentos = []
            for g in sorted(grades, key=lambda x: x.periodo or "Z999"):
                nota = g.nota_final
                if nota is not None and nota >= 70:
                    est = "aprobada"
                elif nota is not None:
                    est = "reprobada"
                else:
                    # Matriculado pero sin nota aún → cursando
                    est = "cursando"
                intentos.append(MallaIntento(
                    periodo=g.periodo,
                    nota=nota,
                    estado=est,
                ))

            # Determinar estado final y nota vigente
            if not intentos:
                estado_final = "no_cursado"
                nota_vigente = None
                total_no_cursado += 1
            else:
                ultimo = intentos[-1]
                nota_vigente = ultimo.nota
                estado_final = ultimo.estado
                if estado_final == "aprobada":
                    total_aprobadas += 1
                elif estado_final == "cursando":
                    total_cursando += 1
                elif estado_final == "reprobada":
                    total_reprobadas += 1

            num_intentos = len(intentos)
            es_repeticion = num_intentos > 1

            # Nombre original (título) — buscar en las grades del estudiante
            nombre_display = asig_upper
            for g in grades:
                if g.asignatura and g.asignatura.strip():
                    nombre_display = g.asignatura.strip()
                    break
            # Si no tiene grades propias, usar el nombre pre-cargado (batched)
            if not grades and asig_upper in display_names:
                nombre_display = display_names[asig_upper]

            malla_asigs.append(MallaAsignatura(
                nombre=nombre_display,
                nivel_canonico=niv,
                intentos=intentos,
                nota_vigente=nota_vigente,
                estado=estado_final,
                es_repeticion=es_repeticion,
                num_intentos=num_intentos,
            ))

            if nota_vigente is not None:
                notas_nivel.append(nota_vigente)

        promedio = round(sum(notas_nivel) / len(notas_nivel), 1) if notas_nivel else None

        semestres.append(MallaSemestre(
            numero=niv,
            asignaturas=malla_asigs,
            promedio=promedio,
        ))

    total_asig = sum(len(s.asignaturas) for s in semestres)

    return MallaCurricular(
        carrera=carrera,
        total_semestres=len(semestres),
        semestres=semestres,
        total_aprobadas=total_aprobadas,
        total_reprobadas=total_reprobadas,
        total_cursando=total_cursando,
        total_no_cursado=total_no_cursado,
        total_asignaturas_malla=total_asig,
    ), canonical


@router.get("/{student_id}/ficha", response_model=FichaEstudiante)
def get_ficha(
    student_id: int,
    periodo: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retorna la ficha completa del estudiante con todos sus datos.
    Equivalente a la FichaEst del Excel pero para todos los cursos.
    Enriquece accesos_avac y tareas con nombre_curso, docente y grupo
    desde la tabla courses (codigo_avac == codigo_curso).

    El parámetro 'periodo' permite ver datos de un período específico:
    - Si coincide con el semestre activo (o no se envía): comportamiento actual
    - Si es un período histórico (ej. P67): muestra calificaciones de ese período
      como principales, y los demás como históricos. AVAC (accesos/tareas) solo
      existen para el período actual.
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")

    # ── Determinar si el periodo solicitado es el activo ──
    from ..models.course_config import SemesterConfig as _SC
    active_sc = db.query(_SC).filter(_SC.activo == True).first()  # noqa: E712
    active_periodo = active_sc.semestre.strip() if active_sc and active_sc.semestre else None

    def _norm_p(val):
        """Normaliza a formato 'P##'."""
        if not val:
            return None
        v = str(val).strip()
        return v if v.startswith("P") else f"P{v}"

    req_periodo = _norm_p(periodo) if periodo else _norm_p(active_periodo)
    active_norm = _norm_p(active_periodo)
    is_current = (not periodo) or (req_periodo == active_norm)

    def _periodo_match(col, pval):
        """Dual-format filter: P68 OR 68."""
        if not pval:
            return col.is_(None)
        raw = pval[1:] if pval.startswith("P") else pval
        return or_(col == pval, col == raw)

    # ── AVAC: filtrar por período + solo último snapshot ──
    def _avac_periodo_filter(periodo_col):
        match_expr = _periodo_match(periodo_col, req_periodo)
        if is_current:
            return or_(match_expr, periodo_col.is_(None))
        return match_expr

    # Obtener la fecha del snapshot más reciente para este estudiante+periodo
    latest_avac_snap = (
        db.query(func.max(AvacAccess.snapshot_date))
        .filter(AvacAccess.student_id == student_id, _avac_periodo_filter(AvacAccess.periodo))
        .scalar()
    )
    avac_snap_filter = (
        or_(AvacAccess.snapshot_date == latest_avac_snap, AvacAccess.snapshot_date.is_(None))
        if latest_avac_snap else AvacAccess.snapshot_date.is_(None)  # legacy: NULL snapshot_date
    )
    accesos = (
        db.query(AvacAccess)
        .filter(AvacAccess.student_id == student_id, _avac_periodo_filter(AvacAccess.periodo), avac_snap_filter)
        .order_by(AvacAccess.dias_sin_acceso)
        .all()
    )

    latest_task_snap = (
        db.query(func.max(TaskSubmission.snapshot_date))
        .filter(TaskSubmission.student_id == student_id, _avac_periodo_filter(TaskSubmission.periodo))
        .scalar()
    )
    task_snap_filter = (
        or_(TaskSubmission.snapshot_date == latest_task_snap, TaskSubmission.snapshot_date.is_(None))
        if latest_task_snap else TaskSubmission.snapshot_date.is_(None)
    )
    tareas = (
        db.query(TaskSubmission)
        .filter(TaskSubmission.student_id == student_id, _avac_periodo_filter(TaskSubmission.periodo), task_snap_filter)
        .order_by(TaskSubmission.codigo_curso, TaskSubmission.unidad)
        .all()
    )

    # ── Calificaciones ──
    if is_current:
        # Semestre activo: calificaciones sin periodo = actuales
        calificaciones = (
            db.query(Grade)
            .filter(Grade.student_id == student_id, Grade.periodo.is_(None))
            .order_by(Grade.asignatura)
            .all()
        )
        calificaciones_historicas = (
            db.query(Grade)
            .filter(Grade.student_id == student_id, Grade.periodo.isnot(None))
            .order_by(Grade.periodo, Grade.asignatura)
            .all()
        )
    else:
        # Período histórico: calificaciones de ese periodo = principales
        calificaciones = (
            db.query(Grade)
            .filter(Grade.student_id == student_id, _periodo_match(Grade.periodo, req_periodo))
            .order_by(Grade.asignatura)
            .all()
        )
        # Históricas: todos los demás periodos (incluye NULL y otros)
        raw_p = req_periodo[1:] if req_periodo.startswith("P") else req_periodo
        calificaciones_historicas = (
            db.query(Grade)
            .filter(
                Grade.student_id == student_id,
                Grade.periodo.isnot(None),
                ~Grade.periodo.in_([req_periodo, raw_p]),
            )
            .order_by(Grade.periodo, Grade.asignatura)
            .all()
        )

    # ── Intervenciones: filtrar por periodo si es histórico ──
    if is_current:
        intervenciones = (
            db.query(Intervention)
            .filter(Intervention.student_id == student_id)
            .order_by(Intervention.created_at.desc())
            .all()
        )
    else:
        intervenciones = (
            db.query(Intervention)
            .filter(
                Intervention.student_id == student_id,
                _periodo_match(Intervention.periodo, req_periodo),
            )
            .order_by(Intervention.created_at.desc())
            .all()
        )

    # Prácticas preprofesionales (filtrar por periodo si es histórico)
    prac_q = db.query(PracticaPreprofesional).filter(PracticaPreprofesional.student_id == student_id)
    if not is_current:
        prac_q = prac_q.filter(_periodo_match(PracticaPreprofesional.periodo, req_periodo))
    practicas_raw = prac_q.order_by(PracticaPreprofesional.periodo.desc()).all()

    # Enriquecer con datos de la escuela (jurisdicción, ubicación completa)
    practicas_out = []
    for p in practicas_raw:
        jurisdiccion = None
        ubicacion = p.ubicacion_escuela
        if p.escuela_id:
            escuela = db.query(EscuelaPractica).filter(EscuelaPractica.id == p.escuela_id).first()
            if escuela:
                jurisdiccion = escuela.jurisdiccion
                # Si la ubicación no estaba en el formulario, usar SEIBE
                if not ubicacion:
                    parts = [escuela.canton, escuela.parroquia, escuela.direccion]
                    ubicacion = ", ".join(pt for pt in parts if pt)
        practicas_out.append(PracticaOut(
            id=p.id,
            nombre_practica=p.nombre_practica,
            nivel_practica=p.nivel_practica,
            nivel_y_practica=p.nivel_y_practica,
            centro_apoyo=p.centro_apoyo,
            en_mineduc=p.en_mineduc,
            amie_escuela=p.amie_escuela,
            nombre_escuela=p.nombre_escuela,
            distrito=p.distrito,
            sistema_educativo=p.sistema_educativo,
            ubicacion_escuela=ubicacion,
            jurisdiccion=jurisdiccion or p.sistema_educativo,
            nombre_autoridad=p.nombre_autoridad,
            cargo_autoridad=p.cargo_autoridad,
            telefono_autoridad=p.telefono_autoridad,
            periodo=p.periodo,
        ))

    # ── Construir mapa codigo_avac → CourseConfig para enriquecer accesos y tareas ──
    all_codigos = set(
        [a.codigo_curso for a in accesos] + [t.codigo_curso for t in tareas]
    )
    course_map: dict[str, CourseConfig] = {}
    all_courses: list[CourseConfig] = []
    if all_codigos:
        all_courses = (
            db.query(CourseConfig)
            .filter(CourseConfig.codigo_avac.in_(all_codigos))
            .all()
        )
        # Si hay varias entradas por codigo_avac (distintos semestres),
        # se queda con la de mayor id (más reciente)
        for c in sorted(all_courses, key=lambda x: x.id):
            course_map[c.codigo_avac] = c

    # ── Detectar sede y nivel por votación mayoritaria (Framework_FichaEst §3.3) ──
    # sede_detectada solo aplica para carrera EIB (el SEDE_MAPPING es exclusivo de EIB/UPS)
    is_eib = bool(student.carrera and "INTERCULTURAL" in student.carrera.upper())
    sede_detectada = detectar_sede(all_courses, student_grupo=student.grupo) if is_eib else None
    nivel_detectado = detectar_nivel(all_courses)

    # ── Diagnóstico de riesgo computado (Framework_FichaEst §3.5) ──
    diagnostico = diagnosticar_riesgo(
        estado_matricula=student.estado_matricula,
        indice_compromiso=student.indice_compromiso,
        intervenciones=intervenciones,
    )

    # Serializar accesos enriquecidos
    accesos_out = [
        AvacAccessOut(
            codigo_curso=a.codigo_curso,
            nombre_curso=course_map[a.codigo_curso].asignatura if a.codigo_curso in course_map else None,
            docente=course_map[a.codigo_curso].docente if a.codigo_curso in course_map else None,
            nivel=course_map[a.codigo_curso].nivel if a.codigo_curso in course_map else None,
            grupo=course_map[a.codigo_curso].grupo if a.codigo_curso in course_map else None,
            bloque=course_map[a.codigo_curso].bloque if a.codigo_curso in course_map else None,
            ultimo_acceso_texto=a.ultimo_acceso_texto,
            dias_sin_acceso=a.dias_sin_acceso,
            estado_avac=a.estado_avac,
            fecha_extraccion=a.fecha_extraccion,
        )
        for a in accesos
    ]

    # Serializar tareas enriquecidas
    tareas_out = [
        TaskSubmissionOut(
            codigo_curso=t.codigo_curso,
            nombre_curso=course_map[t.codigo_curso].asignatura if t.codigo_curso in course_map else None,
            unidad=t.unidad,
            estado=t.estado,
            calificacion=t.calificacion,
            calificacion_maxima=t.calificacion_maxima,
            calificacion_final=t.calificacion_final,
            total_curso=t.total_curso,
            entregada=t.entregada or False,
            calificada=t.calificada or False,
            retrasada=t.retrasada or False,
        )
        for t in tareas
    ]

    ultima_intervencion = intervenciones[0].created_at if intervenciones else None

    # ── Asignaturas matriculadas desde el reporte institucional ──
    enroll_q = db.query(Enrollment).filter(Enrollment.student_id == student_id)
    if not is_current:
        enroll_q = enroll_q.filter(_periodo_match(Enrollment.periodo, req_periodo))
    enrollments_raw = enroll_q.order_by(Enrollment.nivel, Enrollment.asignatura).all()
    enrollments_out = [
        EnrollmentOut(
            codigo_grupo=e.codigo_grupo,
            codigo_asignatura=e.codigo_asignatura,
            asignatura=e.asignatura,
            tipo_asignatura=e.tipo_asignatura,
            carrera=e.carrera,
            nivel=e.nivel,
            nombre_grupo=e.nombre_grupo,
            bloque=e.bloque,
            docente=e.docente,
            correo_docente=e.correo_docente,
            numero_repitencias=e.numero_repitencias,
            pagado=e.pagado,
            estado_matriculado=e.estado_matriculado,
            periodo=e.periodo,
            fecha_matricula=e.fecha_matricula,
        )
        for e in enrollments_raw
    ]

    # ── Construir malla curricular fija (con protección contra errores) ──
    try:
        malla, canonical_niveles = _build_malla_canonica(
            db, student, calificaciones_historicas, calificaciones,
            enrollments=enrollments_raw,
        )
    except Exception as e:
        logger.error("Error construyendo malla para estudiante %s (carrera: %s): %s",
                      student.id, student.carrera, e, exc_info=True)
        malla = MallaCurricular(carrera=student.carrera)
        canonical_niveles = {}

    # ── Normalizar nivel de calificaciones actuales con la malla canónica ──
    # Esto garantiza que el módulo "semestre actual" muestre el mismo nivel
    # que la malla curricular (evita desajustes por datos inconsistentes).
    calificaciones_out = []
    for g in calificaciones:
        nivel_canon = canonical_niveles.get(g.asignatura.strip().upper())
        calificaciones_out.append(GradeOut(
            asignatura=g.asignatura,
            nota_final=g.nota_final,
            docente=g.docente,
            grupo=g.grupo,
            periodo=g.periodo,
            numero_repitencias=g.numero_repitencias,
            nivel=nivel_canon if nivel_canon is not None else g.nivel,
        ))

    return FichaEstudiante(
        id=student.id,
        cedula=student.cedula,
        nombre=student.nombre,
        correo_institucional=student.correo_institucional,
        correo=student.correo,
        telefono=student.telefono,
        whatsapp=student.whatsapp,
        carrera=student.carrera,
        sede=student.sede,
        sede_detectada=sede_detectada,
        nivel_detectado=nivel_detectado,
        nivel_academico=student.nivel_academico,
        estado_matricula=student.estado_matricula,
        fecha_nacimiento=student.fecha_nacimiento,
        genero=student.genero,
        autoidentificacion_etnica=student.autoidentificacion_etnica,
        grupo_reporte=student.grupo,
        pais=student.pais,
        provincia=student.provincia,
        ciudad=student.ciudad,
        parroquia=student.parroquia,
        barrio=student.barrio,
        nivel_riesgo=student.nivel_riesgo,
        indice_compromiso=student.indice_compromiso,
        dias_sin_acceso=student.dias_sin_acceso,
        porcentaje_tareas=student.porcentaje_tareas,
        promedio_calificaciones=student.promedio_calificaciones,
        diagnostico_riesgo=diagnostico,
        prob_desercion=student.prob_desercion,
        prob_reprobacion=student.prob_reprobacion,
        prediccion_updated_at=student.prediccion_updated_at,
        accesos_avac=accesos_out,
        tareas=tareas_out,
        calificaciones=calificaciones_out,
        calificaciones_historicas=calificaciones_historicas,
        malla_curricular=malla,
        enrollments=enrollments_out,
        intervenciones=intervenciones,
        practicas_preprofesionales=practicas_out,
        total_intervenciones=len(intervenciones),
        ultima_intervencion=ultima_intervencion,
        periodo_consulta=req_periodo,
        periodo_es_actual=is_current,
    )


# ── Tendencias AVAC: snapshots históricos de acceso y tareas ──────────────────

class AvacSnapshotItem(BaseModel):
    snapshot_date: str
    cursos: int = 0
    promedio_dias_sin_acceso: Optional[float] = None
    max_dias_sin_acceso: Optional[float] = None
    total_tareas: int = 0
    tareas_entregadas: int = 0
    tareas_calificadas: int = 0
    tareas_retrasadas: int = 0
    pct_entregadas: Optional[float] = None
    pct_calificadas: Optional[float] = None

class DocenteGradingItem(BaseModel):
    docente: Optional[str] = None
    codigo_curso: str
    asignatura: Optional[str] = None
    total_tareas: int = 0
    calificadas: int = 0
    pendientes: int = 0
    pct_calificadas: Optional[float] = None
    snapshot_date: Optional[str] = None

class TrendResponse(BaseModel):
    student_id: int
    periodo: str
    snapshots: list[AvacSnapshotItem] = []
    docente_grading: list[DocenteGradingItem] = []


@router.get("/{student_id}/tendencias")
def get_student_trends(
    student_id: int,
    periodo: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Devuelve snapshots históricos de acceso AVAC y tareas para un estudiante.

    Permite analizar la evolución del compromiso del estudiante a lo largo del
    semestre, y el estado de calificación por docente.
    """
    from ..models.course_config import SemesterConfig, CourseConfig

    # Determinar periodo
    active_sem = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()
    active_periodo = active_sem.semestre if active_sem else None

    def _norm_p(val):
        if not val:
            return None
        v = str(val).strip()
        return v if v.startswith("P") else f"P{v}"

    req_periodo = _norm_p(periodo) if periodo else _norm_p(active_periodo)
    if not req_periodo:
        return TrendResponse(student_id=student_id, periodo="", snapshots=[], docente_grading=[])

    raw_p = req_periodo[1:] if req_periodo.startswith("P") else req_periodo

    # ── Snapshots de acceso AVAC ──
    accesos_all = (
        db.query(AvacAccess)
        .filter(
            AvacAccess.student_id == student_id,
            or_(AvacAccess.periodo == req_periodo, AvacAccess.periodo == raw_p),
        )
        .order_by(AvacAccess.snapshot_date)
        .all()
    )

    # Agrupar por snapshot_date
    from collections import defaultdict
    snap_accesos = defaultdict(list)
    for a in accesos_all:
        key = str(a.snapshot_date) if a.snapshot_date else "legacy"
        snap_accesos[key].append(a)

    # ── Snapshots de tareas ──
    tareas_all = (
        db.query(TaskSubmission)
        .filter(
            TaskSubmission.student_id == student_id,
            or_(TaskSubmission.periodo == req_periodo, TaskSubmission.periodo == raw_p),
        )
        .order_by(TaskSubmission.snapshot_date)
        .all()
    )
    snap_tareas = defaultdict(list)
    for t in tareas_all:
        key = str(t.snapshot_date) if t.snapshot_date else "legacy"
        snap_tareas[key].append(t)

    # Combinar fechas de snapshots
    all_dates = sorted(set(list(snap_accesos.keys()) + list(snap_tareas.keys())))

    snapshots = []
    for d in all_dates:
        acc_list = snap_accesos.get(d, [])
        tar_list = snap_tareas.get(d, [])
        dias_vals = [a.dias_sin_acceso for a in acc_list if a.dias_sin_acceso is not None]
        total_t = len(tar_list)
        entregadas = sum(1 for t in tar_list if t.entregada)
        calificadas = sum(1 for t in tar_list if t.calificada)
        retrasadas = sum(1 for t in tar_list if t.retrasada)

        snapshots.append(AvacSnapshotItem(
            snapshot_date=d,
            cursos=len(set(a.codigo_curso for a in acc_list)),
            promedio_dias_sin_acceso=round(sum(dias_vals) / len(dias_vals), 1) if dias_vals else None,
            max_dias_sin_acceso=max(dias_vals) if dias_vals else None,
            total_tareas=total_t,
            tareas_entregadas=entregadas,
            tareas_calificadas=calificadas,
            tareas_retrasadas=retrasadas,
            pct_entregadas=round(entregadas / total_t * 100, 1) if total_t else None,
            pct_calificadas=round(calificadas / total_t * 100, 1) if total_t else None,
        ))

    # ── Seguimiento docente: tareas pendientes de calificación (último snapshot) ──
    latest_snap = all_dates[-1] if all_dates else None
    docente_grading = []
    if latest_snap:
        latest_tareas = snap_tareas.get(latest_snap, [])
        # Agrupar por codigo_curso
        curso_tareas = defaultdict(list)
        for t in latest_tareas:
            curso_tareas[t.codigo_curso].append(t)

        # Buscar docente y asignatura desde CourseConfig
        for codigo, tasks in curso_tareas.items():
            cc = db.query(CourseConfig).filter(CourseConfig.codigo_avac == codigo).first()
            total = len(tasks)
            calificadas = sum(1 for t in tasks if t.calificada)
            pendientes = total - calificadas

            docente_grading.append(DocenteGradingItem(
                docente=cc.docente if cc else None,
                codigo_curso=codigo,
                asignatura=cc.asignatura if cc else None,
                total_tareas=total,
                calificadas=calificadas,
                pendientes=pendientes,
                pct_calificadas=round(calificadas / total * 100, 1) if total else None,
                snapshot_date=latest_snap,
            ))

    return TrendResponse(
        student_id=student_id,
        periodo=req_periodo,
        snapshots=snapshots,
        docente_grading=docente_grading,
    )


# ── Análisis Comparativo: estudiante vs compañeros de misma asignatura/carrera ──

class PeerComparisonItem(BaseModel):
    asignatura: str
    nota_estudiante: Optional[float] = None
    promedio_grupo: Optional[float] = None
    nota_maxima: Optional[float] = None
    nota_minima: Optional[float] = None
    percentil: Optional[float] = None
    total_estudiantes: int = 0
    posicion: Optional[int] = None
    docente: Optional[str] = None
    nivel: Optional[int] = None

class PeerComparisonResponse(BaseModel):
    student_id: int
    student_nombre: Optional[str] = None
    carrera: Optional[str] = None
    promedio_estudiante: Optional[float] = None
    promedio_carrera: Optional[float] = None
    percentil_general: Optional[float] = None
    asignaturas: list[PeerComparisonItem] = []


@router.get("/{student_id}/comparativa", response_model=PeerComparisonResponse)
def get_student_comparative(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Análisis comparativo: rendimiento del estudiante vs compañeros
    que cursan las mismas asignaturas en la misma carrera.
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")

    # Calificaciones actuales del estudiante
    student_grades = (
        db.query(Grade)
        .filter(Grade.student_id == student_id, Grade.periodo.is_(None))
        .all()
    )

    if not student_grades:
        return PeerComparisonResponse(
            student_id=student_id,
            student_nombre=student.nombre,
            carrera=student.carrera,
            asignaturas=[],
        )

    asignaturas_result = []
    all_student_notas = []

    for sg in student_grades:
        if sg.nota_final is None:
            continue

        # Obtener notas de todos los estudiantes en la misma asignatura
        # filtrados por misma carrera si aplica
        peer_query = db.query(Grade.nota_final).filter(
            Grade.asignatura == sg.asignatura,
            Grade.periodo.is_(None),
            Grade.nota_final.isnot(None),
        )
        if student.carrera:
            peer_sids = [s_id for (s_id,) in db.query(Student.id).filter(
                func.lower(Student.carrera) == func.lower(student.carrera)
            ).all()]
            if peer_sids:
                peer_query = peer_query.filter(Grade.student_id.in_(peer_sids))

        peer_notas = sorted([n for (n,) in peer_query.all() if n is not None])
        total = len(peer_notas)

        if total == 0:
            continue

        promedio_grupo = round(sum(peer_notas) / total, 1)
        nota_max = max(peer_notas)
        nota_min = min(peer_notas)

        # Calcular percentil del estudiante
        below = sum(1 for n in peer_notas if n < sg.nota_final)
        percentil = round(below / total * 100, 1) if total > 0 else None

        # Posición (1 = mejor)
        sorted_desc = sorted(peer_notas, reverse=True)
        posicion = sorted_desc.index(sg.nota_final) + 1 if sg.nota_final in sorted_desc else None

        all_student_notas.append(sg.nota_final)

        asignaturas_result.append(PeerComparisonItem(
            asignatura=sg.asignatura,
            nota_estudiante=sg.nota_final,
            promedio_grupo=promedio_grupo,
            nota_maxima=nota_max,
            nota_minima=nota_min,
            percentil=percentil,
            total_estudiantes=total,
            posicion=posicion,
            docente=sg.docente,
            nivel=sg.nivel,
        ))

    # Promedio general del estudiante
    promedio_est = round(sum(all_student_notas) / len(all_student_notas), 1) if all_student_notas else None

    # Promedio general de la carrera
    promedio_carrera = None
    percentil_general = None
    if student.carrera:
        career_sids = [s_id for (s_id,) in db.query(Student.id).filter(
            func.lower(Student.carrera) == func.lower(student.carrera)
        ).all()]
        if career_sids:
            career_grades = db.query(Grade.student_id, func.avg(Grade.nota_final)).filter(
                Grade.student_id.in_(career_sids),
                Grade.periodo.is_(None),
                Grade.nota_final.isnot(None),
            ).group_by(Grade.student_id).all()
            if career_grades:
                promedios = [float(avg) for _, avg in career_grades]
                promedio_carrera = round(sum(promedios) / len(promedios), 1)
                if promedio_est is not None:
                    below = sum(1 for p in promedios if p < promedio_est)
                    percentil_general = round(below / len(promedios) * 100, 1)

    return PeerComparisonResponse(
        student_id=student_id,
        student_nombre=student.nombre,
        carrera=student.carrera,
        promedio_estudiante=promedio_est,
        promedio_carrera=promedio_carrera,
        percentil_general=percentil_general,
        asignaturas=sorted(asignaturas_result, key=lambda x: x.asignatura),
    )
