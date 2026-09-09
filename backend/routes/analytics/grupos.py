"""
Módulo: Analítica de Grupos.

Pivotea la tabla de calificaciones (Grade) para presentar, dentro de un
grupo académico (período + carrera + nivel), una fila por estudiante y una
columna por asignatura, con la nota final (Grade.nota_final) en cada celda.

Reutiliza las convenciones del módulo Asignaturas (auth, prefijo /analytics,
apply_periodo_filter, umbrales configurables, normalización de riesgo).
Solo accesible para el rol admin (require_admin).
"""
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ...database import get_db
from ...models import Student, Grade
from ...auth.jwt import require_admin
from ...models.user import User
from ._helpers import apply_periodo_filter, get_umbrales, normalize_riesgo

router = APIRouter(prefix="/analytics", tags=["analytics"])


class GrupoEstudiante(BaseModel):
    student_id: int
    nombre: Optional[str] = None
    nivel_riesgo: Optional[str] = None
    # notas por asignatura: {asignatura: nota_final | None}
    notas: dict[str, Optional[float]] = {}
    promedio: Optional[float] = None


class GrupoKPIs(BaseModel):
    total_estudiantes: int = 0
    total_asignaturas: int = 0
    promedio_grupo: Optional[float] = None
    estudiantes_riesgo_alto: int = 0


class GrupoAnalytics(BaseModel):
    periodo: Optional[str] = None
    carrera: Optional[str] = None
    nivel: Optional[int] = None
    nota_aprobacion: float = 70.0
    asignaturas: list[str] = []          # orden de columnas (A-Z)
    estudiantes: list[GrupoEstudiante] = []
    kpis: GrupoKPIs = GrupoKPIs()

    class Config:
        from_attributes = True


@router.get("/grupos", response_model=GrupoAnalytics)
def get_grupos_analytics(
    periodo: Optional[str] = None,
    carrera: Optional[str] = None,
    nivel: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Vista pivote de un grupo académico.

    Filtra Grade por período (apply_periodo_filter), carrera (coincidencia
    parcial case-insensitive sobre Grade.carrera) y nivel (Grade.nivel).
    Devuelve una matriz estudiante × asignatura con la nota final en cada
    celda, más el promedio por estudiante y los KPIs del grupo.
    """
    umbrales = get_umbrales(db)
    nota_aprob = umbrales["nota_aprobacion"]

    query = db.query(
        Grade.student_id,
        Grade.asignatura,
        Grade.nota_final,
    )
    query, periodo_norm = apply_periodo_filter(query, periodo)

    if carrera:
        query = query.filter(func.lower(Grade.carrera).contains(carrera.lower()))
    if nivel is not None:
        query = query.filter(Grade.nivel == nivel)

    rows = query.all()

    # ── Pivote: (student_id, asignatura) → mejor nota_final ──────────────
    # Un estudiante puede tener varias filas por asignatura (repeticiones,
    # grupos/docentes distintos). Nos quedamos con la nota más alta no nula
    # para no ocultar una calificación real detrás de un NULL.
    asignaturas_set: set[str] = set()
    pivot: dict[int, dict[str, Optional[float]]] = {}
    for student_id, asignatura, nota in rows:
        if not asignatura:
            continue
        asignaturas_set.add(asignatura)
        est = pivot.setdefault(student_id, {})
        if asignatura not in est or est[asignatura] is None:
            est[asignatura] = nota
        elif nota is not None and nota > est[asignatura]:
            est[asignatura] = nota

    asignaturas = sorted(asignaturas_set)

    if not pivot:
        return GrupoAnalytics(
            periodo=periodo_norm, carrera=carrera, nivel=nivel,
            nota_aprobacion=nota_aprob, asignaturas=[], estudiantes=[],
            kpis=GrupoKPIs(),
        )

    # ── Datos de estudiantes (nombre + nivel de riesgo) ──────────────────
    student_ids = list(pivot.keys())
    students = db.query(
        Student.id, Student.nombre, Student.nivel_riesgo
    ).filter(Student.id.in_(student_ids)).all()
    student_map = {s.id: s for s in students}

    estudiantes: list[GrupoEstudiante] = []
    suma_promedios = 0.0
    n_con_promedio = 0
    riesgo_alto = 0

    for sid in student_ids:
        notas_est = pivot.get(sid, {})
        # Rellenar todas las columnas para una matriz consistente
        notas_full = {asig: notas_est.get(asig) for asig in asignaturas}
        valores = [v for v in notas_full.values() if v is not None]
        promedio = round(sum(valores) / len(valores), 1) if valores else None
        if promedio is not None:
            suma_promedios += promedio
            n_con_promedio += 1

        s = student_map.get(sid)
        nr = normalize_riesgo(s.nivel_riesgo) if s else None
        if nr == "Alto":
            riesgo_alto += 1

        estudiantes.append(GrupoEstudiante(
            student_id=sid,
            nombre=s.nombre if s else None,
            nivel_riesgo=nr,
            notas=notas_full,
            promedio=promedio,
        ))

    # Orden por defecto: alfabético por nombre (la tabla permite reordenar)
    estudiantes.sort(key=lambda e: (e.nombre or "").lower())

    promedio_grupo = round(suma_promedios / n_con_promedio, 1) if n_con_promedio else None

    kpis = GrupoKPIs(
        total_estudiantes=len(estudiantes),
        total_asignaturas=len(asignaturas),
        promedio_grupo=promedio_grupo,
        estudiantes_riesgo_alto=riesgo_alto,
    )

    return GrupoAnalytics(
        periodo=periodo_norm,
        carrera=carrera,
        nivel=nivel,
        nota_aprobacion=nota_aprob,
        asignaturas=asignaturas,
        estudiantes=estudiantes,
        kpis=kpis,
    )
