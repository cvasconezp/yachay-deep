"""
Módulo: Analítica de Grupos.

Vista pivote de un grupo académico (período · carrera · nivel): una fila por
estudiante y una columna por asignatura, con la nota final (Grade.nota_final)
en cada celda.

Diseño robusto para datos reales (sigue convenciones del módulo Asignaturas y
replica el cruce asignatura↔nota de la Ficha del estudiante):
- La carrera se filtra vía Student (Grade.carrera suele venir vacío).
- El roster y las columnas del grupo se toman de Enrollment (matrícula
  institucional), que tiene nivel/carrera confiables.
- Las notas se RELLENAN desde Grade emparejando por nombre de asignatura
  NORMALIZADO igual que la Ficha (quita artefactos de Excel, colapsa espacios y
  tildes, mayúsculas) y, si no hay match exacto, por subcadena. Incluye grades
  con período NULL (semestre actual, como en la Ficha).
- Si el período no tiene matrículas (períodos antiguos), cae a un pivote directo
  desde Grade.
Solo accesible para el rol admin (require_admin).
"""
import re
import unicodedata
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ...database import get_db
from ...models import Student, Grade, Enrollment, TaskSubmission
from ...auth.jwt import require_admin
from ...models.user import User
from ._helpers import apply_periodo_filter, get_umbrales, normalize_riesgo

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _norm_asig(name: Optional[str]) -> str:
    """Normaliza el nombre de asignatura para emparejar Enrollment↔Grade.

    Igual que la Ficha (_normalize_asig en routes/students.py): elimina
    artefactos de Excel (_x000d_/_x000a_), colapsa saltos de línea y espacios,
    y pasa a mayúsculas; además quita tildes para tolerar diferencias de acentos.
    """
    if not name:
        return ""
    clean = re.sub(r"_x[0-9a-fA-F]{4}_", " ", name)   # artefactos Excel
    clean = re.sub(r"[\r\n]+", " ", clean)             # saltos de línea
    clean = re.sub(r"\s+", " ", clean).strip()
    nfkd = unicodedata.normalize("NFKD", clean)
    clean = "".join(c for c in nfkd if not unicodedata.combining(c))
    return clean.upper()


class GrupoEstudiante(BaseModel):
    student_id: int
    nombre: Optional[str] = None
    nivel_riesgo: Optional[str] = None
    grupo: Optional[str] = None           # paralelo (Student.grupo)
    es_tercera_matricula: bool = False   # condicionado (3ra matrícula)
    es_repitente: bool = False           # 2da matrícula (numero_repitencias > 1)
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
    fuente: Optional[str] = None          # "grades" | "enrollment" | "enrollment+grades"
    asignaturas: list[str] = []
    estudiantes: list[GrupoEstudiante] = []
    kpis: GrupoKPIs = GrupoKPIs()

    class Config:
        from_attributes = True


def _build_response(
    db: Session, rows, periodo_norm: Optional[str], carrera: Optional[str],
    nivel: Optional[int], nota_aprob: float, fuente: str,
    repitente_sids: Optional[set] = None,
) -> GrupoAnalytics:
    """Construye la matriz estudiante × asignatura desde filas
    (student_id, asignatura_display, nota|None). Dedup por (estudiante,
    asignatura) quedándose con la nota más alta no nula."""
    repitente_sids = repitente_sids or set()
    asignaturas_set: set[str] = set()
    pivot: dict[int, dict[str, Optional[float]]] = {}
    for student_id, asignatura, nota in rows:
        if not asignatura:
            continue
        asignaturas_set.add(asignatura)
        est = pivot.setdefault(student_id, {})
        if asignatura not in est or est[asignatura] is None:
            est[asignatura] = nota
        elif nota is not None and (est[asignatura] is None or nota > est[asignatura]):
            est[asignatura] = nota

    asignaturas = sorted(asignaturas_set)
    if not pivot:
        return GrupoAnalytics(
            periodo=periodo_norm, carrera=carrera, nivel=nivel,
            nota_aprobacion=nota_aprob, fuente=fuente,
            asignaturas=[], estudiantes=[], kpis=GrupoKPIs(),
        )

    student_ids = list(pivot.keys())
    students = db.query(
        Student.id, Student.nombre, Student.nivel_riesgo,
        Student.grupo, Student.es_tercera_matricula
    ).filter(Student.id.in_(student_ids)).all()
    student_map = {s.id: s for s in students}

    estudiantes: list[GrupoEstudiante] = []
    suma_promedios = 0.0
    n_con_promedio = 0
    riesgo_alto = 0
    hay_notas = False

    for sid in student_ids:
        notas_est = pivot.get(sid, {})
        notas_full = {asig: notas_est.get(asig) for asig in asignaturas}
        valores = [v for v in notas_full.values() if v is not None]
        if valores:
            hay_notas = True
        promedio = round(sum(valores) / len(valores), 1) if valores else None
        if promedio is not None:
            suma_promedios += promedio
            n_con_promedio += 1

        s = student_map.get(sid)
        nr = normalize_riesgo(s.nivel_riesgo) if s else None
        if nr == "Alto":
            riesgo_alto += 1

        es_tercera = bool(s.es_tercera_matricula) if s else False
        estudiantes.append(GrupoEstudiante(
            student_id=sid, nombre=s.nombre if s else None, nivel_riesgo=nr,
            grupo=(s.grupo if s else None),
            es_tercera_matricula=es_tercera,
            es_repitente=(sid in repitente_sids and not es_tercera),
            notas=notas_full, promedio=promedio,
        ))

    estudiantes.sort(key=lambda e: (e.nombre or "").lower())
    promedio_grupo = round(suma_promedios / n_con_promedio, 1) if n_con_promedio else None

    if fuente == "enrollment" and hay_notas:
        fuente = "enrollment+grades"

    kpis = GrupoKPIs(
        total_estudiantes=len(estudiantes),
        total_asignaturas=len(asignaturas),
        promedio_grupo=promedio_grupo,
        estudiantes_riesgo_alto=riesgo_alto,
    )
    return GrupoAnalytics(
        periodo=periodo_norm, carrera=carrera, nivel=nivel,
        nota_aprobacion=nota_aprob, fuente=fuente,
        asignaturas=asignaturas, estudiantes=estudiantes, kpis=kpis,
    )


def _grades_by_student(db: Session, roster_sids: list[int], periodo: Optional[str]) -> dict:
    """{student_id: {asignatura_normalizada: nota}} para el conjunto de
    estudiantes. Incluye grades con período NULL (semestre actual, como la
    Ficha) y guarda la mejor nota no nula por asignatura."""
    if not roster_sids:
        return {}
    gq = db.query(Grade.student_id, Grade.asignatura, Grade.nota_final)
    gq, _ = apply_periodo_filter(gq, periodo, include_null=True)
    gq = gq.filter(Grade.student_id.in_(roster_sids))
    out: dict[int, dict[str, Optional[float]]] = {}
    for sid, asig, nota in gq.all():
        key = _norm_asig(asig)
        if not key:
            continue
        d = out.setdefault(sid, {})
        cur = d.get(key)
        if key not in d or cur is None or (nota is not None and nota > cur):
            d[key] = nota
    return out


def _total_curso_map(db: Session, roster_sids: list[int], periodo: Optional[str]) -> dict:
    """{(student_id, codigo_curso): total_curso} desde TaskSubmission (nota
    "Total del Curso" del AVAC), la MISMA fuente de respaldo que usa la Ficha
    cuando aún no hay nota final en Grade. Toma el snapshot más reciente."""
    if not roster_sids:
        return {}
    tq = db.query(
        TaskSubmission.student_id, TaskSubmission.codigo_curso,
        TaskSubmission.total_curso, TaskSubmission.snapshot_date,
    )
    tq, _ = apply_periodo_filter(tq, periodo, column=TaskSubmission.periodo, include_null=True)
    tq = tq.filter(
        TaskSubmission.student_id.in_(roster_sids),
        TaskSubmission.total_curso.isnot(None),
        TaskSubmission.codigo_curso.isnot(None),
    )
    out: dict[tuple, float] = {}
    best_snap: dict[tuple, object] = {}
    for sid, codigo, total, snap in tq.all():
        key = (sid, str(codigo).strip())
        prev = best_snap.get(key)
        if key not in out or (snap is not None and (prev is None or snap > prev)):
            out[key] = total
            best_snap[key] = snap
    return out


def _match_nota(student_grades: dict, enr_key: str) -> Optional[float]:
    """Empareja la asignatura de matrícula (normalizada) con una nota del
    estudiante: match exacto y, si no, por subcadena (mayor solapamiento),
    igual que _find_canon_key de la Ficha."""
    if not student_grades or not enr_key:
        return None
    if enr_key in student_grades:
        return student_grades[enr_key]
    best_nota = None
    best_len = 0
    for gk, nota in student_grades.items():
        if gk and (gk in enr_key or enr_key in gk):
            overlap = min(len(gk), len(enr_key))
            if overlap > best_len:
                best_len = overlap
                best_nota = nota
    return best_nota


@router.get("/grupos", response_model=GrupoAnalytics)
def get_grupos_analytics(
    periodo: Optional[str] = None,
    carrera: Optional[str] = None,
    nivel: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Vista pivote de un grupo académico (período · carrera · nivel)."""
    umbrales = get_umbrales(db)
    nota_aprob = umbrales["nota_aprobacion"]

    carrera_sids: Optional[list[int]] = None
    if carrera:
        carrera_sids = [
            sid for (sid,) in db.query(Student.id).filter(
                func.lower(Student.carrera).contains(carrera.lower())
            ).all()
        ]
        if not carrera_sids:
            _, periodo_norm = apply_periodo_filter(db.query(Grade.id), periodo)
            return GrupoAnalytics(
                periodo=periodo_norm, carrera=carrera, nivel=nivel,
                nota_aprobacion=nota_aprob, fuente="enrollment",
            )

    # ── Roster + columnas desde Enrollment (nivel/carrera confiables) ────
    eq = db.query(
        Enrollment.student_id, Enrollment.asignatura, Enrollment.codigo_grupo,
        Enrollment.numero_repitencias,
    )
    eq, periodo_norm = apply_periodo_filter(eq, periodo, column=Enrollment.periodo)
    if carrera_sids is not None:
        eq = eq.filter(Enrollment.student_id.in_(carrera_sids))
    if nivel is not None:
        eq = eq.filter(Enrollment.nivel == nivel)
    enroll_rows_raw = eq.all()

    if enroll_rows_raw:
        roster_sids = list({r[0] for r in enroll_rows_raw})
        # Repitente = alguna matrícula del grupo con numero_repitencias > 1
        repitente_sids = {
            sid for sid, _, _, nrep in enroll_rows_raw if nrep and nrep > 1
        }
        grades_by_student = _grades_by_student(db, roster_sids, periodo)
        total_curso = _total_curso_map(db, roster_sids, periodo)
        rows = []
        for sid, asig, codigo, _nrep in enroll_rows_raw:
            # Igual que la Ficha: nota final de Grade y, si no hay, el
            # "Total del Curso" de las tareas (AVAC), enlazado por codigo_curso.
            nota = _match_nota(grades_by_student.get(sid, {}), _norm_asig(asig))
            if nota is None and codigo:
                nota = total_curso.get((sid, str(codigo).strip()))
            rows.append((sid, asig, nota))
        return _build_response(
            db, rows, periodo_norm, carrera, nivel, nota_aprob, "enrollment",
            repitente_sids=repitente_sids,
        )

    # ── Fallback: pivote directo desde Grade (períodos sin matrícula) ────
    gq = db.query(Grade.student_id, Grade.asignatura, Grade.nota_final)
    gq, periodo_norm = apply_periodo_filter(gq, periodo)
    if carrera_sids is not None:
        gq = gq.filter(Grade.student_id.in_(carrera_sids))
    if nivel is not None:
        gq = gq.filter(Grade.nivel == nivel)
    grade_rows = gq.all()

    return _build_response(
        db, grade_rows, periodo_norm, carrera, nivel, nota_aprob, "grades"
    )
