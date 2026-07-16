"""Ámbito por carrera: qué carreras puede ver cada usuario.

POR QUÉ EXISTE
--------------
Hasta ahora los permisos eran solo por MÓDULO (`User.permissions`): decidían si veías
la pestaña "Estudiantes", no A CUÁLES estudiantes. Un monitor con acceso al módulo veía
las 25 carreras enteras. La documentación afirmaba que el acceso era "según permisos de
carrera/asignatura", pero eso no existía en el código.

DISEÑO: DENEGAR POR DEFECTO
---------------------------
Para roles no-admin, `carreras` NULL o [] significa NINGUNA carrera, no todas. Es más
seguro: si alguien crea un usuario y olvida marcar carreras, ese usuario no ve nada —
un fallo visible e inofensivo. Con el criterio contrario, el olvido pasa desapercibido
y expone todo. El admin ignora el campo: siempre ve todo.

CÓMO USARLO EN UNA RUTA NUEVA
-----------------------------
    from ..services.scope import filtrar_carrera
    q = filtrar_carrera(db.query(Student), current_user)

Para un objeto ya cargado (ficha, detalle), usar `asegurar_acceso_carrera`.
"""
from fastapi import HTTPException, status

from ..models.user import User, UserRole
from ..models.student import Student


def es_admin(user) -> bool:
    rol = getattr(user, "role", None)
    return rol == UserRole.admin or rol == "admin"


def carreras_de(user) -> list[str] | None:
    """Carreras visibles. None = sin restricción (solo admin)."""
    if user is None or es_admin(user):
        return None
    valor = getattr(user, "carreras", None)
    if not valor:
        return []          # denegar por defecto
    return [str(c) for c in valor]


def sin_restriccion(user) -> bool:
    return carreras_de(user) is None


def puede_ver_carrera(user, carrera) -> bool:
    permitidas = carreras_de(user)
    if permitidas is None:
        return True
    return carrera in permitidas


def filtrar_carrera(query, user, columna=None):
    """Aplica el ámbito a una consulta. Por defecto filtra sobre Student.carrera.

    `columna` permite filtrar otros modelos que tengan carrera (Intervention, CourseConfig).
    """
    permitidas = carreras_de(user)
    if permitidas is None:
        return query
    col = columna if columna is not None else Student.carrera
    if not permitidas:
        # Ninguna carrera asignada: consulta vacía, no la consulta entera.
        return query.filter(False)
    return query.filter(col.in_(permitidas))


def asegurar_acceso_carrera(user, carrera):
    """403 si el usuario no puede ver esa carrera. Para detalles y fichas."""
    if not puede_ver_carrera(user, carrera):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene acceso a los datos de esta carrera",
        )


def carreras_permitidas_o_none(user) -> list[str] | None:
    """Azúcar para construir consultas manuales/SQL: None = todas."""
    return carreras_de(user)
