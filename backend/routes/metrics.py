"""
Fuente única de verdad para las cifras de impacto de marca (chore/estandar-casa, punto 5).

La landing / tarjeta de Labs debe LEER `GET /metrics/impact`; NO debe existir
"3.040+ / 25 programas" como texto estático en el frontend.

Definiciones fijadas (ver docs/DATA_DICTIONARY.md, clase = Impacto):
  - estudiantes_monitoreados: número de estudiantes en la base. Cada registro de
    `students` proviene de ingesta real (scraping AVAC / uploads), por lo que el
    conteo equivale a "estudiantes con datos que el motor monitorea".
  - programas_activos: número de carreras/programas DISTINTOS con al menos un
    estudiante monitoreado (carrera no nula).

Ambas se computan en BACKEND, desde la BD, y son recalculables (auditable).
Sin PII: solo agregados. Endpoint público de solo lectura.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.student import Student
from ..auth.jwt import get_current_user

router = APIRouter(prefix="/metrics", tags=["metrics"])

IMPACT_DEFINITIONS = {
    "estudiantes_monitoreados": (
        "Numero de estudiantes en la base (cada uno proviene de ingesta real; "
        "equivale a estudiantes con datos monitoreados por el motor)."
    ),
    "programas_activos": (
        "Numero de carreras/programas distintos con al menos un estudiante monitoreado."
    ),
}


@router.get("/impact")
def impact(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Cifra de impacto de Core (conteos agregados, sin PII).

    REQUIERE AUTENTICACIÓN. Antes era pública y la landing comercial la leía en vivo:
    cualquiera podía pedir /api/metrics/impact y obtener el conteo real de estudiantes
    y carreras de la institución. No es dato personal, pero sí dato institucional, y
    publicarlo con fines comerciales exige convenio firmado. Mientras no exista, esta
    cifra es de uso interno y la landing no la muestra.
    """
    estudiantes = int(db.query(func.count(Student.id)).scalar() or 0)
    programas = int(
        db.query(func.count(func.distinct(Student.carrera)))
        .filter(Student.carrera.isnot(None))
        .scalar()
        or 0
    )
    return {
        "estudiantes_monitoreados": estudiantes,
        "programas_activos": programas,
        "definiciones": IMPACT_DEFINITIONS,
        "fuente": "GET /metrics/impact (computado desde BD)",
    }
