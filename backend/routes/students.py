"""
Endpoints de estudiantes — equivalente a la lógica de FichaEst.
Búsqueda por nombre/correo/cédula y vista de ficha completa.
"""
from typing import Optional
from collections import Counter
import time
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from pydantic import BaseModel
from datetime import datetime, date

logger = logging.getLogger(__name__)

from ..database import get_db
from ..models import Student, AvacAccess, TaskSubmission, Grade, Intervention
from ..models.course_config import CourseConfig
from ..auth.jwt import get_current_user
from ..models.user import User
from ..constants import EIB_GRUPO_SEDE_STR as SEDE_MAPPING

router = APIRouter(prefix="/students", tags=["students"])

# ── Caché en memoria para malla canónica por carrera (evita recalcular por cada estudiante) ──
# Estructura: { "CARRERA_UPPER": (timestamp, canonical_dict) }
_canonical_cache: dict[str, tuple[float, dict[str, int]]] = {}
_CANONICAL_CACHE_TTL = 600  # 10 minutos

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


# ── Schemas para Malla Curricular fija ────────────────────────────────────────

class MallaIntento(BaseModel):
    """Un intento de cursar una asignatura (un registro en un período)."""
    periodo: Optional[str] = None
    nota: Optional[float] = None
    estado: str  # aprobada | reprobada | en_proceso | cursando

class MallaAsignatura(BaseModel):
    """Una asignatura dentro de la malla canónica."""
    nombre: str
    nivel_canonico: int
    intentos: list[MallaIntento] = []
    nota_vigente: Optional[float] = None
    estado: str  # aprobada | reprobada | en_proceso | cursando | no_cursado
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

    # Resumen
    total_intervenciones: int = 0
    ultima_intervencion: Optional[datetime] = None

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

    logger.info("Calculando malla canónica para %s...", carrera_key)
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
        asig_upper = asig.strip().upper()
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
                asig_upper = asig.strip().upper()
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
                    asig_upper = asig.strip().upper()
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
                asig_upper = asig.strip().upper()
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
) -> tuple["MallaCurricular", dict[str, int]]:
    """
    Construye la malla curricular fija del estudiante.

    Retorna (MallaCurricular, canonical_dict) donde canonical_dict es
    {ASIGNATURA_UPPER: nivel_canonico} para reutilizar al normalizar
    el nivel de las calificaciones del semestre actual.
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
    student_grades_map: dict[str, list] = {}  # asig_upper → [Grade]
    for g in calificaciones_hist:
        key = g.asignatura.strip().upper()
        student_grades_map.setdefault(key, []).append(g)
    for g in calificaciones_actual:
        key = g.asignatura.strip().upper()
        student_grades_map.setdefault(key, []).append(g)

    # ── 4. Construir la respuesta ──
    semestres = []
    total_aprobadas = 0
    total_reprobadas = 0
    total_cursando = 0
    total_no_cursado = 0

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
                if g.periodo is None:
                    # Semestre actual → cursando
                    est = "cursando"
                elif nota is not None and nota >= 70:
                    est = "aprobada"
                elif nota is not None and nota >= 60:
                    est = "en_proceso"
                elif nota is not None:
                    est = "reprobada"
                else:
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
                elif estado_final in ("reprobada", "en_proceso"):
                    total_reprobadas += 1

            num_intentos = len(intentos)
            es_repeticion = num_intentos > 1

            # Nombre original (título) — buscar en las grades del estudiante
            nombre_display = asig_upper
            for g in grades:
                if g.asignatura.strip():
                    nombre_display = g.asignatura.strip()
                    break
            # Si no tiene grades propias, buscar el nombre de cualquier grade
            if not grades:
                sample = db.query(Grade.asignatura).filter(
                    func.upper(Grade.asignatura) == asig_upper,
                ).first()
                if sample:
                    nombre_display = sample[0].strip()

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retorna la ficha completa del estudiante con todos sus datos.
    Equivalente a la FichaEst del Excel pero para todos los cursos.
    Enriquece accesos_avac y tareas con nombre_curso, docente y grupo
    desde la tabla courses (codigo_avac == codigo_curso).
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")

    accesos = (
        db.query(AvacAccess)
        .filter(AvacAccess.student_id == student_id)
        .order_by(AvacAccess.dias_sin_acceso)
        .all()
    )

    tareas = (
        db.query(TaskSubmission)
        .filter(TaskSubmission.student_id == student_id)
        .order_by(TaskSubmission.codigo_curso, TaskSubmission.unidad)
        .all()
    )

    # Calificaciones del semestre actual (sin período asignado)
    calificaciones = (
        db.query(Grade)
        .filter(Grade.student_id == student_id, Grade.periodo.is_(None))
        .order_by(Grade.asignatura)
        .all()
    )

    # Calificaciones históricas (con período: P60, P61, … P67+)
    calificaciones_historicas = (
        db.query(Grade)
        .filter(Grade.student_id == student_id, Grade.periodo.isnot(None))
        .order_by(Grade.periodo, Grade.asignatura)
        .all()
    )

    intervenciones = (
        db.query(Intervention)
        .filter(Intervention.student_id == student_id)
        .order_by(Intervention.created_at.desc())
        .all()
    )

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

    # ── Construir malla curricular fija (con protección contra errores) ──
    try:
        malla, canonical_niveles = _build_malla_canonica(
            db, student, calificaciones_historicas, calificaciones,
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
        intervenciones=intervenciones,
        total_intervenciones=len(intervenciones),
        ultima_intervencion=ultima_intervencion,
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
