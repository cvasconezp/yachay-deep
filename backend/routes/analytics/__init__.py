"""
Módulo de Analítica — refactorizado desde analytics.py monolítico.
[ARCH-03] Remediación: dividido en 5 submódulos.

Uso en main.py (sin cambios necesarios):
    from .routes.analytics import router as analytics_router
"""
from fastapi import APIRouter
from .asignaturas import router as asig_router
from .docentes import router as doc_router
from .tutorias import router as tut_router
from .resumen import router as res_router
from .docente_tracking import router as doc_track_router
from .entregas import router as entregas_router
from .terceras_matriculas import router as tm_router
from .practicas import router as practicas_router

router = APIRouter()
router.include_router(asig_router)
router.include_router(doc_router)
router.include_router(tut_router)
router.include_router(res_router)
router.include_router(doc_track_router)
router.include_router(entregas_router)
router.include_router(tm_router)
router.include_router(practicas_router)
