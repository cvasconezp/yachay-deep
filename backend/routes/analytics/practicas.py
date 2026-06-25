"""
Módulo de Analítica de Prácticas Preprofesionales.
Endpoint para resumen agregado: sistema educativo, distritos, escuelas, estudiantes.
"""
import re
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


# ── Data normalisation helpers ──────────────────────────────────────
_SISTEMA_MAP = {
    "intercultural":          "Intercultural",
    "intercultural (hispana)": "Intercultural",
    "intercultural bilingüe": "Intercultural Bilingüe",
    "intercultural bilingue": "Intercultural Bilingüe",
}

def _norm_sistema(raw: str | None) -> str:
    if not raw:
        return "Sin dato"
    return _SISTEMA_MAP.get(raw.strip().lower(), raw.strip())

def _norm_distrito(raw: str | None) -> str:
    if not raw:
        return "Sin distrito"
    d = raw.strip()
    # "Distrito Distrito 10D02" → "Distrito 10D02"
    d = re.sub(r"(?i)^distrito\s+distrito\s+", "Distrito ", d)
    # Ensure trailing spaces are removed
    return d.strip()


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
    # --- Check table exists (graceful fallback) ---
    from sqlalchemy import inspect as sa_inspect
    inspector = sa_inspect(db.bind)
    if "practicas_preprofesionales" not in inspector.get_table_names():
        return _empty_response()

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

    rows = q.all()

    # --- Pre-load all students in one query (avoid N+1) ---
    student_ids = list(set(r.student_id for r in rows))
    students_map = {}
    if student_ids:
        students = db.query(Student).filter(Student.id.in_(student_ids)).all()
        students_map = {s.id: s for s in students}

    # --- Normalise each row into a lightweight dict ---
    normalised = []
    for r in rows:
        normalised.append({
            "student_id": r.student_id,
            "sistema": _norm_sistema(r.sistema_educativo),
            "distrito": _norm_distrito(r.distrito),
            "centro_apoyo": (r.centro_apoyo or "").strip() or "Sin dato",
            "nivel_practica": (r.nivel_y_practica or "").strip() or "Sin dato",
            "amie": (r.amie_escuela or "").strip(),
            "nombre_escuela": (r.nombre_escuela or "").strip(),
            "nombre_autoridad": (r.nombre_autoridad or "").strip(),
            "cargo_autoridad": (r.cargo_autoridad or "").strip(),
            "telefono_autoridad": (r.telefono_autoridad or "").strip(),
            "en_mineduc": (r.en_mineduc or "").strip(),
        })

    # --- Apply post-normalisation filters ---
    if sistema_educativo:
        normalised = [n for n in normalised if n["sistema"] == sistema_educativo]
    if distrito:
        normalised = [n for n in normalised if n["distrito"] == distrito]
    if centro_apoyo:
        normalised = [n for n in normalised if n["centro_apoyo"] == centro_apoyo]
    if nivel_practica:
        normalised = [n for n in normalised if n["nivel_practica"] == nivel_practica]

    # --- Gather unique filter options (from ALL rows, pre-filter) ---
    all_normalised = []
    for r in rows:
        all_normalised.append({
            "sistema": _norm_sistema(r.sistema_educativo),
            "distrito": _norm_distrito(r.distrito),
            "centro_apoyo": (r.centro_apoyo or "").strip() or "Sin dato",
            "nivel_practica": (r.nivel_y_practica or "").strip() or "Sin dato",
        })

    sistemas = sorted(set(n["sistema"] for n in all_normalised if n["sistema"] != "Sin dato"))
    distritos_all = sorted(set(n["distrito"] for n in all_normalised if n["distrito"] != "Sin distrito"))
    centros = sorted(set(n["centro_apoyo"] for n in all_normalised if n["centro_apoyo"] != "Sin dato"))
    niveles = sorted(set(n["nivel_practica"] for n in all_normalised if n["nivel_practica"] != "Sin dato"))

    # --- Build hierarchical data: distrito → escuela → estudiantes ---
    escuelas_map = {}  # (distrito, amie) → { info, estudiantes }
    for n in normalised:
        key = (n["distrito"], n["amie"] or "SIN_AMIE")
        if key not in escuelas_map:
            escuelas_map[key] = {
                "amie": n["amie"],
                "nombre_escuela": n["nombre_escuela"],
                "distrito": n["distrito"],
                "sistema_educativo": n["sistema"],
                "nombre_autoridad": n["nombre_autoridad"],
                "cargo_autoridad": n["cargo_autoridad"],
                "telefono_autoridad": n["telefono_autoridad"],
                "estudiantes": [],
            }
        student = students_map.get(n["student_id"])
        escuelas_map[key]["estudiantes"].append({
            "student_id": n["student_id"],
            "nombre": student.nombre if student else "",
            "cedula": student.cedula if student else "",
            "correo": student.correo if student else "",
            "telefono": student.telefono if student else "",
            "centro_apoyo": n["centro_apoyo"],
            "nivel_practica": n["nivel_practica"],
            "en_mineduc": n["en_mineduc"],
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

    # --- Flat escuelas list (for search) ---
    escuelas_flat = []
    for d in distritos_list:
        for e in d["escuelas"]:
            escuelas_flat.append({
                "amie": e["amie"],
                "nombre_escuela": e["nombre_escuela"],
                "distrito": d["distrito"],
                "sistema_educativo": e["sistema_educativo"],
                "total_estudiantes": e["total_estudiantes"],
                "nombre_autoridad": e["nombre_autoridad"],
                "cargo_autoridad": e["cargo_autoridad"],
                "telefono_autoridad": e["telefono_autoridad"],
                "estudiantes": e["estudiantes"],
            })

    # --- KPI totals ---
    total_estudiantes = len(normalised)
    total_escuelas = len(set(n["amie"] for n in normalised if n["amie"]))
    total_distritos = len(set(n["distrito"] for n in normalised if n["distrito"] != "Sin distrito"))
    en_mineduc_count = sum(1 for n in normalised if n["en_mineduc"].lower() == "sí")

    # por sistema educativo
    por_sistema = {}
    for n in normalised:
        por_sistema[n["sistema"]] = por_sistema.get(n["sistema"], 0) + 1
    por_sistema_list = [{"sistema": k, "total": v} for k, v in sorted(por_sistema.items())]

    # por nivel de práctica
    por_nivel = {}
    for n in normalised:
        por_nivel[n["nivel_practica"]] = por_nivel.get(n["nivel_practica"], 0) + 1
    por_nivel_list = [{"nivel": k, "total": v} for k, v in sorted(por_nivel.items())]

    # por centro de apoyo
    por_centro = {}
    for n in normalised:
        por_centro[n["centro_apoyo"]] = por_centro.get(n["centro_apoyo"], 0) + 1
    por_centro_list = [{"centro": k, "total": v} for k, v in sorted(por_centro.items())]

    # por distrito (for chart)
    por_distrito = {}
    for n in normalised:
        por_distrito[n["distrito"]] = por_distrito.get(n["distrito"], 0) + 1
    por_distrito_list = sorted(
        [{"distrito": k, "total": v} for k, v in por_distrito.items()],
        key=lambda x: -x["total"],
    )

    return {
        "total_estudiantes": total_estudiantes,
        "total_escuelas": total_escuelas,
        "total_distritos": total_distritos,
        "en_mineduc": en_mineduc_count,
        "por_sistema": por_sistema_list,
        "por_nivel": por_nivel_list,
        "por_centro": por_centro_list,
        "por_distrito": por_distrito_list,
        "distritos": distritos_list,
        "escuelas": escuelas_flat,
        "filtros": {
            "sistemas_educativos": sistemas,
            "distritos": distritos_all,
            "centros_apoyo": centros,
            "niveles_practica": niveles,
        },
    }


def _empty_response():
    return {
        "total_estudiantes": 0, "total_escuelas": 0, "total_distritos": 0,
        "en_mineduc": 0, "por_sistema": [], "por_nivel": [], "por_centro": [],
        "por_distrito": [], "distritos": [], "escuelas": [],
        "filtros": {"sistemas_educativos": [], "distritos": [], "centros_apoyo": [], "niveles_practica": []},
    }
