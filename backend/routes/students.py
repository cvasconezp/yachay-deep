"""
Endpoints de estudiantes — equivalente a la lógica de FichaEst.
Búsqueda por nombre/correo/cédula y vista de ficha completa.
"""
from typing import Optional
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from pydantic import BaseModel
from datetime import datetime

from ..database import get_db
from ..models import Student, AvacAccess, TaskSubmission, Grade, Intervention
from ..models.course_config import CourseConfig
from ..auth.jwt import get_current_user
from ..models.user import User

router = APIRouter(prefix="/students", tags=["students"])

# ─── Detección de sede por grupo mayoritario (Framework_FichaEst §3.3) ────────
# Grupo-N → nombre de la sede física (EIB / UPS)
SEDE_MAPPING: dict[str, str] = {
    "1": "Latacunga",
    "2": "Cayambe",
    "3": "Otavalo",
    "4": "Riobamba",
    "5": "Cayambe-Amazonía",
    "6": "Wasakentsa",
}

def detectar_sede(course_configs: list) -> Optional[str]:
    """
    Votación mayoritaria del campo 'grupo' en los CourseConfig del estudiante.
    El grupo con más apariciones determina la sede.
    """
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

    # Clasificar índice de compromiso
    es_alto  = indice_compromiso is not None and indice_compromiso >= 0.6
    es_medio = indice_compromiso is not None and 0.3 <= indice_compromiso < 0.6
    es_bajo  = indice_compromiso is None or indice_compromiso < 0.3

    # Novedades del historial
    motivos = {(inv.motivo or "").lower() for inv in intervenciones}
    nov_ausent = bool(motivos & NOVEDADES_AUSENTISMO)
    nov_notas  = bool(motivos & NOVEDADES_NOTAS)

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

    # Datos relacionados
    accesos_avac: list[AvacAccessOut] = []
    tareas: list[TaskSubmissionOut] = []
    calificaciones: list[GradeOut] = []          # semestre actual (periodo IS NULL)
    calificaciones_historicas: list[GradeOut] = []  # histórico (periodo IS NOT NULL), ordenado por periodo
    intervenciones: list[InterventionOut] = []

    # Resumen
    total_intervenciones: int = 0
    ultima_intervencion: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/search", response_model=list[StudentSummary])
def search_students(
    q: str = Query(..., min_length=2, description="Nombre, correo institucional, cédula o teléfono"),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Búsqueda triple: nombre / correo / cédula.
    Replica el LET(resultado, UNIQUE(FILTER(...))) de FichaEst.
    """
    q_lower = q.lower().strip()
    results = (
        db.query(Student)
        .filter(
            or_(
                func.lower(Student.nombre).contains(q_lower),
                func.lower(Student.correo_institucional).contains(q_lower),
                Student.cedula == q.strip(),
                func.lower(Student.telefono).contains(q_lower),
            )
        )
        .limit(limit)
        .all()
    )
    return results


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
    sede_detectada = detectar_sede(all_courses)
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
            entregada=t.entregada or False,
            calificada=t.calificada or False,
            retrasada=t.retrasada or False,
        )
        for t in tareas
    ]

    ultima_intervencion = intervenciones[0].created_at if intervenciones else None

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
        accesos_avac=accesos_out,
        tareas=tareas_out,
        calificaciones=calificaciones,
        calificaciones_historicas=calificaciones_historicas,
        intervenciones=intervenciones,
        total_intervenciones=len(intervenciones),
        ultima_intervencion=ultima_intervencion,
    )
