"""
Endpoints de configuración de cursos y semestres.
Permite al admin gestionar la lista dinámica de cursos AVAC por semestre.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from ..database import get_db
from ..models.course_config import CourseConfig, SemesterConfig
from ..auth.jwt import require_admin, get_current_user
from ..models.user import User

router = APIRouter(prefix="/courses", tags=["courses"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class CourseConfigCreate(BaseModel):
    codigo_avac: str
    nombre: Optional[str] = None
    asignatura: Optional[str] = None
    carrera: Optional[str] = None
    docente: Optional[str] = None
    semestre: Optional[str] = None
    bloque: Optional[str] = "ambos"   # "1", "2", o "ambos"
    grupo: Optional[str] = None
    activo: bool = True
    notas: Optional[str] = None


class CourseConfigUpdate(BaseModel):
    codigo_avac: Optional[str] = None
    nombre: Optional[str] = None
    asignatura: Optional[str] = None
    carrera: Optional[str] = None
    docente: Optional[str] = None
    semestre: Optional[str] = None
    bloque: Optional[str] = None
    grupo: Optional[str] = None
    activo: Optional[bool] = None
    notas: Optional[str] = None


class CourseConfigOut(BaseModel):
    id: int
    codigo_avac: str
    nombre: Optional[str]
    asignatura: Optional[str]
    carrera: Optional[str]
    docente: Optional[str]
    semestre: Optional[str]
    bloque: Optional[str]
    grupo: Optional[str]
    activo: bool
    notas: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class SemesterConfigCreate(BaseModel):
    semestre: str
    bloque_actual: str = "1"
    bloque1_inicio: Optional[datetime] = None
    bloque1_fin: Optional[datetime] = None
    bloque2_inicio: Optional[datetime] = None
    bloque2_fin: Optional[datetime] = None


class SemesterConfigUpdate(BaseModel):
    semestre: Optional[str] = None  # permite renombrar (ej. "68" → "P68")
    bloque_actual: Optional[str] = None
    bloque1_inicio: Optional[datetime] = None
    bloque1_fin: Optional[datetime] = None
    bloque2_inicio: Optional[datetime] = None
    bloque2_fin: Optional[datetime] = None


class SemesterConfigOut(BaseModel):
    id: int
    semestre: str
    activo: bool
    bloque_actual: str
    bloque1_inicio: Optional[datetime]
    bloque1_fin: Optional[datetime]
    bloque2_inicio: Optional[datetime]
    bloque2_fin: Optional[datetime]

    class Config:
        from_attributes = True


# ─── Course Endpoints ─────────────────────────────────────────────────────────

@router.get("/", response_model=list[CourseConfigOut])
def list_courses(
    semestre: Optional[str] = None,
    activo: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(CourseConfig)
    if semestre:
        query = query.filter(CourseConfig.semestre == semestre)
    if activo is not None:
        query = query.filter(CourseConfig.activo == activo)
    return query.order_by(CourseConfig.carrera, CourseConfig.asignatura).all()


@router.post("/", response_model=CourseConfigOut, dependencies=[Depends(require_admin)])
def create_course(payload: CourseConfigCreate, db: Session = Depends(get_db)):
    course = CourseConfig(**payload.model_dump())
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.post("/bulk", dependencies=[Depends(require_admin)])
def bulk_create_courses(courses: list[CourseConfigCreate], db: Session = Depends(get_db)):
    """Carga masiva de cursos — para migrar la lista del Excel al iniciar el semestre."""
    created = 0
    updated = 0
    for c in courses:
        existing = db.query(CourseConfig).filter(
            CourseConfig.codigo_avac == c.codigo_avac,
            CourseConfig.semestre == c.semestre,
        ).first()
        if existing:
            for field, value in c.model_dump(exclude_unset=True).items():
                setattr(existing, field, value)
            updated += 1
        else:
            db.add(CourseConfig(**c.model_dump()))
            created += 1
    db.commit()
    return {"created": created, "updated": updated, "total": created + updated}


@router.patch("/{course_id}", response_model=CourseConfigOut, dependencies=[Depends(require_admin)])
def update_course(course_id: int, payload: CourseConfigUpdate, db: Session = Depends(get_db)):
    course = db.query(CourseConfig).filter(CourseConfig.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(course, field, value)
    db.commit()
    db.refresh(course)
    return course


@router.delete("/{course_id}", dependencies=[Depends(require_admin)])
def delete_course(course_id: int, db: Session = Depends(get_db)):
    course = db.query(CourseConfig).filter(CourseConfig.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    db.delete(course)
    db.commit()
    return {"ok": True}


# ─── Semester Endpoints ───────────────────────────────────────────────────────

@router.get("/semester/active", response_model=Optional[SemesterConfigOut])
def get_active_semester(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()


@router.get("/semester/all", response_model=list[SemesterConfigOut])
def list_semesters(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(SemesterConfig).order_by(SemesterConfig.semestre.desc()).all()


@router.post("/semester/", response_model=SemesterConfigOut, dependencies=[Depends(require_admin)])
def create_semester(payload: SemesterConfigCreate, db: Session = Depends(get_db)):
    semester = SemesterConfig(**payload.model_dump())
    db.add(semester)
    db.commit()
    db.refresh(semester)
    return semester


@router.post("/semester/{semestre}/activate", dependencies=[Depends(require_admin)])
def activate_semester(semestre: str, db: Session = Depends(get_db)):
    """Activa un semestre y desactiva todos los demás."""
    db.query(SemesterConfig).update({"activo": False})
    s = db.query(SemesterConfig).filter(SemesterConfig.semestre == semestre).first()
    if not s:
        raise HTTPException(status_code=404, detail="Semestre no encontrado")
    s.activo = True
    db.commit()
    return {"activated": semestre}


class BloqueUpdate(BaseModel):
    bloque: str


@router.post("/semester/{semestre}/bloque", dependencies=[Depends(require_admin)])
def set_bloque(semestre: str, payload: BloqueUpdate, db: Session = Depends(get_db)):
    """Cambia el bloque activo del semestre (1 o 2)."""
    s = db.query(SemesterConfig).filter(SemesterConfig.semestre == semestre).first()
    if not s:
        raise HTTPException(status_code=404, detail="Semestre no encontrado")
    s.bloque_actual = payload.bloque
    db.commit()
    return {"semestre": semestre, "bloque_actual": payload.bloque}


@router.patch("/semester/{semestre}", response_model=SemesterConfigOut, dependencies=[Depends(require_admin)])
def update_semester(semestre: str, payload: SemesterConfigUpdate, db: Session = Depends(get_db)):
    """Actualiza las fechas, configuración o nombre de un semestre existente."""
    s = db.query(SemesterConfig).filter(SemesterConfig.semestre == semestre).first()
    if not s:
        raise HTTPException(status_code=404, detail="Semestre no encontrado")
    data = payload.model_dump(exclude_unset=True)
    # Si se está renombrando, verificar que no exista otro con el mismo nombre
    new_name = data.get("semestre")
    if new_name and new_name != s.semestre:
        existing = db.query(SemesterConfig).filter(SemesterConfig.semestre == new_name).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Ya existe un semestre con el nombre '{new_name}'")
    for field, value in data.items():
        setattr(s, field, value)
    db.commit()
    db.refresh(s)
    return s


@router.delete("/semester/{semestre}", dependencies=[Depends(require_admin)])
def delete_semester(semestre: str, db: Session = Depends(get_db)):
    """Elimina un semestre. No se permite eliminar el semestre activo."""
    s = db.query(SemesterConfig).filter(SemesterConfig.semestre == semestre).first()
    if not s:
        raise HTTPException(status_code=404, detail="Semestre no encontrado")
    if s.activo:
        raise HTTPException(status_code=400, detail="No se puede eliminar el semestre activo. Desactívalo primero.")
    db.delete(s)
    db.commit()
    return {"deleted": semestre}


@router.post("/semester/deactivate-all", dependencies=[Depends(require_admin)])
def deactivate_all_semesters(db: Session = Depends(get_db)):
    """Desactiva todos los semestres. Útil al finalizar un período académico
    para detener scraping y alertas de AVAC."""
    db.query(SemesterConfig).update({"activo": False})
    db.commit()
    return {"message": "Todos los semestres desactivados. El scraping diario y las alertas de AVAC se detendrán."}


@router.get("/semester/{semestre}/status", dependencies=[Depends(get_current_user)])
def semester_status(semestre: str, db: Session = Depends(get_db)):
    """Devuelve el estado del semestre incluyendo si ya finalizó."""
    s = db.query(SemesterConfig).filter(SemesterConfig.semestre == semestre).first()
    if not s:
        raise HTTPException(status_code=404, detail="Semestre no encontrado")
    return {
        "semestre": s.semestre,
        "activo": s.activo,
        "bloque_actual": s.bloque_actual,
        "fecha_fin_actual": str(s.fecha_fin_actual) if s.fecha_fin_actual else None,
        "semestre_finalizado": s.semestre_finalizado,
    }
