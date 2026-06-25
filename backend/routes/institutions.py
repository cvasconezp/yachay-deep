"""
Endpoints para Multi-tenancy Institucional (Épica 5.4)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional

from ..database import get_db
from ..models.institution import Institution
from ..auth.jwt import get_current_user

router = APIRouter(prefix="/institutions", tags=["institutions"])


class InstitutionCreate(BaseModel):
    nombre: str
    codigo: Optional[str] = None
    avac_url: Optional[str] = None
    umbral_riesgo_alto: float = Field(0.70, ge=0, le=1)
    umbral_riesgo_medio: float = Field(0.40, ge=0, le=1)
    umbral_dias_critico: int = Field(14, ge=1)
    umbral_compromiso_bajo: float = Field(0.30, ge=0, le=1)


class InstitutionUpdate(BaseModel):
    nombre: Optional[str] = None
    avac_url: Optional[str] = None
    activa: Optional[bool] = None
    umbral_riesgo_alto: Optional[float] = None
    umbral_riesgo_medio: Optional[float] = None
    umbral_dias_critico: Optional[int] = None
    umbral_compromiso_bajo: Optional[float] = None


@router.get("")
def list_institutions(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Lista todas las instituciones."""
    institutions = db.query(Institution).order_by(Institution.nombre).all()
    return [{
        "id": i.id,
        "nombre": i.nombre,
        "codigo": i.codigo,
        "avac_url": i.avac_url,
        "activa": i.activa,
        "umbrales": {
            "riesgo_alto": i.umbral_riesgo_alto,
            "riesgo_medio": i.umbral_riesgo_medio,
            "dias_critico": i.umbral_dias_critico,
            "compromiso_bajo": i.umbral_compromiso_bajo,
        },
    } for i in institutions]


@router.post("")
def create_institution(
    body: InstitutionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Crea una nueva institución."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo admin puede crear instituciones")

    existing = db.query(Institution).filter(Institution.nombre == body.nombre).first()
    if existing:
        raise HTTPException(status_code=409, detail="Ya existe una institución con ese nombre")

    inst = Institution(
        nombre=body.nombre,
        codigo=body.codigo,
        avac_url=body.avac_url,
        umbral_riesgo_alto=body.umbral_riesgo_alto,
        umbral_riesgo_medio=body.umbral_riesgo_medio,
        umbral_dias_critico=body.umbral_dias_critico,
        umbral_compromiso_bajo=body.umbral_compromiso_bajo,
    )
    db.add(inst)
    db.commit()
    db.refresh(inst)

    return {"id": inst.id, "nombre": inst.nombre, "message": "Institución creada"}


@router.patch("/{institution_id}")
def update_institution(
    institution_id: int,
    body: InstitutionUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Actualiza una institución."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo admin puede modificar instituciones")

    inst = db.query(Institution).filter(Institution.id == institution_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institución no encontrada")

    for field, value in body.dict(exclude_unset=True).items():
        if value is not None:
            setattr(inst, field, value)

    db.commit()
    return {"id": inst.id, "nombre": inst.nombre, "message": "Institución actualizada"}


@router.get("/{institution_id}")
def get_institution(
    institution_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Obtiene detalle de una institución."""
    inst = db.query(Institution).filter(Institution.id == institution_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institución no encontrada")

    return {
        "id": inst.id,
        "nombre": inst.nombre,
        "codigo": inst.codigo,
        "avac_url": inst.avac_url,
        "activa": inst.activa,
        "umbrales": {
            "riesgo_alto": inst.umbral_riesgo_alto,
            "riesgo_medio": inst.umbral_riesgo_medio,
            "dias_critico": inst.umbral_dias_critico,
            "compromiso_bajo": inst.umbral_compromiso_bajo,
        },
    }
