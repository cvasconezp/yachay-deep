"""
Módulo de Analítica de Prácticas Preprofesionales.
Endpoint para resumen agregado: sistema educativo, distritos, escuelas, estudiantes.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from ...database import get_db
from ...models.practica_preprofesional import PracticaPreprofesional
from ...models import Student
from ...auth.jwt import get_current_user
from ...models.user import User
from ._helpers import apply_periodo_filter

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/practicas-resumen")
def get_practicas_resumen(
    periodo: Optional[str] = None,
    sistema_educativo: Optional[str] = None,
    distrito: Optional[str] = None,
    centro_apoyo: Optional[str] = None,
    nivel_practica: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resumen agregado de prácticas preprofesionales.

    Devuelve totales, filtros disponibles, y desglose jerárquico:
    sistema_educativo → distrito → escuela → estudiantes.
    """
    # --- Base query ---
    q = db.query(PracticaPreprofesional).join(
        Student, PracticaPreprofesional.student_id == Student.id
    )

    # Apply periodo filter
    if periodo and periodo not in ("todos",):
        variants = [periodo]
        if periodo.startswith("P"):
            variants.append(periodo[1:])
        else:
            variants.append(f"P{periodo}")
        q = q.filter(PracticaPreprofesional.periodo.in_(variants))

    if sistema_educativo:
        q = q.filter(PracticaPreprofesional.sistema_educativo == sistema_educativo)
    if distrito:
        q = q.filter(PracticaPreprofesional.distrito == distrito)
    if centro_apoyo:
        q = q.filter(PracticaPreprofesional.centro_apoyo == centro_apoyo)
    if nivel_practica:
        q = q.filter(PracticaPreprofesional.nivel_y_practica == nivel_practica)

    rows = q.all()

    # --- Pre-load all students in one query (avoid N+1) ---
    student_ids = list(set(r.student_id for r in rows))
    students_map = {}
    if student_ids:
        students = db.query(Student).filter(Student.id.in_(student_ids)).all()
        students_map = {s.id: s for s in students}

    # --- Gather unique filter options (before filtering, for dropdowns) ---
    all_q = db.query(PracticaPreprofesional)
    if periodo and periodo not in ("todos",):
        variants = [periodo]
        if periodo.startswith("P"):
            variants.append(periodo[1:])
        else:
            variants.append(f"P{periodo}")
        all_q = all_q.filter(PracticaPreprofesional.periodo.in_(variants))

    all_rows = all_q.all()

    sistemas = sorted(set(r.sistema_educativo for r in all_rows if r.sistema_educativo))
    distritos_all = sorted(set(r.distrito for r in all_rows if r.distrito))
    centros = sorted(set(r.centro_apoyo for r in all_rows if r.centro_apoyo))
    niveles = sorted(set(r.nivel_y_practica for r in all_rows if r.nivel_y_practica))

    # --- Build hierarchical data: sistema → distrito → escuela → estudiantes ---
    # Group by distrito → escuela
    escuelas_map = {}  # (distrito, amie) → { info, estudiantes }
    for r in rows:
        dist = r.distrito or "Sin distrito"
        amie = r.amie_escuela or "SIN_AMIE"
        key = (dist, amie)
        if key not in escuelas_map:
            escuelas_map[key] = {
                "amie": r.amie_escuela or "",
                "nombre_escuela": r.nombre_escuela or "",
                "distrito": dist,
                "sistema_educativo": r.sistema_educativo or "",
                "nombre_autoridad": r.nombre_autoridad or "",
                "cargo_autoridad": r.cargo_autoridad or "",
                "telefono_autoridad": r.telefono_autoridad or "",
                "estudiantes": [],
            }
        student = students_map.get(r.student_id)
        escuelas_map[key]["estudiantes"].append({
            "student_id": r.student_id,
            "nombre": student.nombre if student else "",
            "cedula": student.cedula if student else "",
            "correo": student.correo_personal if student else "",
            "telefono": student.telefono if student else "",
            "centro_apoyo": r.centro_apoyo or "",
            "nivel_practica": r.nivel_y_practica or "",
            "en_mineduc": r.en_mineduc or "",
        })

    # Group escuelas by distrito
    distritos_map = {}
    for (dist, amie), esc_data in escuelas_map.items():
        if dist not in distritos_map:
            distritos_map[dist] = {"distrito": dist, "escuelas": [], "total_estudiantes": 0}
        distritos_map[dist]["escuelas"].append({
            **{k: v for k, v in esc_data.items() if k != "estudiantes"},
            "total_estudiantes": len(esc_data["estudiantes"]),
            "estudiantes": esc_data["estudiantes"],
        })
        distritos_map[dist]["total_estudiantes"] += len(esc_data["estudiantes"])

    # Sort
    distritos_list = sorted(distritos_map.values(), key=lambda d: d["distrito"])
    for d in distritos_list:
        d["escuelas"] = sorted(d["escuelas"], key=lambda e: e["nombre_escuela"])
        d["total_escuelas"] = len(d["escuelas"])

    # --- KPI totals ---
    total_estudiantes = len(rows)
    total_escuelas = len(set((r.amie_escuela or "") for r in rows if r.amie_escuela))
    total_distritos = len(set((r.distrito or "") for r in rows if r.distrito))
    en_mineduc_count = sum(1 for r in rows if r.en_mineduc and r.en_mineduc.lower() == "sí")

    # por sistema educativo
    por_sistema = {}
    for r in rows:
        se = r.sistema_educativo or "Sin dato"
        por_sistema[se] = por_sistema.get(se, 0) + 1
    por_sistema_list = [{"sistema": k, "total": v} for k, v in sorted(por_sistema.items())]

    # por nivel de práctica
    por_nivel = {}
    for r in rows:
        nv = r.nivel_y_practica or "Sin dato"
        por_nivel[nv] = por_nivel.get(nv, 0) + 1
    por_nivel_list = [{"nivel": k, "total": v} for k, v in sorted(por_nivel.items())]

    # por centro de apoyo
    por_centro = {}
    for r in rows:
        ca = r.centro_apoyo or "Sin dato"
        por_centro[ca] = por_centro.get(ca, 0) + 1
    por_centro_list = [{"centro": k, "total": v} for k, v in sorted(por_centro.items())]

    return {
        "total_estudiantes": total_estudiantes,
        "total_escuelas": total_escuelas,
        "total_distritos": total_distritos,
        "en_mineduc": en_mineduc_count,
        "por_sistema": por_sistema_list,
        "por_nivel": por_nivel_list,
        "por_centro": por_centro_list,
        "distritos": distritos_list,
        "filtros": {
            "sistemas_educativos": sistemas,
            "distritos": distritos_all,
            "centros_apoyo": centros,
            "niveles_practica": niveles,
        },
    }
