"""URL base de AVAC derivada del período ACTIVO.

El número de 'grado' en AVAC sigue al número de período: P68→grado68, P69→grado69,
etc. Antes la URL estaba fija en `settings.AVAC_BASE_URL` (una variable de entorno),
y había que cambiarla cada semestre en DOS sitios distintos (Railway para la app y
GitHub Actions para el scraping). Esto hacía que, al cambiar de período, la
verificación de cookie y/o el scraping siguieran apuntando al grado viejo y la sesión
"no abriera" (redirigía a login / "cookie expirada").

`avac_base_url(db)` conserva el host de `settings.AVAC_BASE_URL` y reemplaza el
segmento `/gradoNN` por el del período activo leído de `SemesterConfig`. Si no hay BD
o no hay período activo, cae al valor de configuración tal cual.
"""
import re
from typing import Optional


def avac_base_url(db=None, fallback: Optional[str] = None) -> str:
    from ..config import settings
    base = (fallback or settings.AVAC_BASE_URL or "https://avac.ups.edu.ec/grado68").rstrip("/")
    host = re.sub(r"/grado\d+$", "", base)  # host sin el segmento /gradoNN
    if db is not None:
        try:
            from ..models.course_config import SemesterConfig
            sc = db.query(SemesterConfig).filter(SemesterConfig.activo == True).first()  # noqa: E712
            if sc and sc.semestre:
                m = re.search(r"(\d+)", str(sc.semestre))
                if m:
                    return f"{host}/grado{m.group(1)}"
        except Exception:
            pass
    return base
