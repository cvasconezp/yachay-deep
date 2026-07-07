"""
Utilidades de logging seguro. Nunca loguear PII en claro.

[SEC] Estándar de la casa (chore/estandar-casa, punto 4): los correos y cédulas
que se escriban a logs deben ir enmascarados. El detalle interno de excepciones
no se devuelve al cliente (ver main.py handler global).
"""
from __future__ import annotations


def mask_email(value: str | None) -> str:
    """u***@dominio — enmascara la parte local del correo para logs."""
    if not value or "@" not in str(value):
        return "***"
    local, _, domain = str(value).partition("@")
    head = local[0] if local else "*"
    return f"{head}***@{domain}"


def mask_cedula(value: str | None) -> str:
    """Deja solo los ultimos 2 digitos para trazabilidad sin exponer el documento."""
    if not value:
        return "***"
    v = str(value)
    return f"***{v[-2:]}" if len(v) >= 2 else "***"
