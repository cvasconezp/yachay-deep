"""
Public aggregate stats (no auth) — para los contadores en vivo de yachaydeep.com.
Solo expone conteos agregados y anónimos: total de estudiantes y de programas.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_prod_db
from ..models.student import Student

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/stats")
def public_stats(db: Session = Depends(get_prod_db)):
    students = db.query(Student).count()
    programs = (
        db.query(Student.carrera)
        .filter(Student.carrera.isnot(None), Student.carrera != "")
        .distinct()
        .count()
    )
    return {"students": students, "programs": programs}
