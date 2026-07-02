"""
backend/crypto.py — Cifrado a nivel de aplicacion para Yachay Deep.

Patron: field-level encryption at rest (column-level).
  - Cifrado autenticado  : Fernet (AES-128-CBC + HMAC-SHA256, IV aleatorio).
  - Rotacion de llaves   : MultiFernet (cifra con la 1ra, descifra con cualquiera).
  - Busqueda por igualdad: blind index (HMAC-SHA256 deterministico con clave).

Llaves (variables de entorno en Railway, NUNCA en el repo):
  ENC_KEYS        Lista separada por comas de llaves Fernet (base64 urlsafe).
                  La PRIMERA es la activa (con la que se cifra); las demas solo
                  se usan para descifrar durante una rotacion.
  BLIND_INDEX_KEY Clave hex (64 chars) para el HMAC del blind index.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from sqlalchemy import String, Text
from sqlalchemy.types import TypeDecorator


class CryptoConfigError(RuntimeError):
    """Falta configuracion de cifrado o esta mal formada."""


def is_configured() -> bool:
    """True si ENC_KEYS y BLIND_INDEX_KEY estan presentes (no vacias)."""
    return bool(os.getenv("ENC_KEYS", "").strip() and os.getenv("BLIND_INDEX_KEY", "").strip())


@lru_cache(maxsize=1)
def _get_multifernet() -> MultiFernet:
    raw = os.getenv("ENC_KEYS", "").strip()
    if not raw:
        raise CryptoConfigError("ENC_KEYS no esta configurada.")
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    try:
        return MultiFernet([Fernet(k.encode()) for k in keys])
    except (ValueError, TypeError) as exc:
        raise CryptoConfigError(f"ENC_KEYS mal formada: {exc}") from exc


@lru_cache(maxsize=1)
def _get_blind_index_key() -> bytes:
    raw = os.getenv("BLIND_INDEX_KEY", "").strip()
    if not raw:
        raise CryptoConfigError("BLIND_INDEX_KEY no esta configurada.")
    try:
        return bytes.fromhex(raw)
    except ValueError as exc:
        raise CryptoConfigError("BLIND_INDEX_KEY debe ser hex (64 chars).") from exc


def reset_key_cache() -> None:
    """Limpia el cache de llaves (tests o rotacion en caliente)."""
    _get_multifernet.cache_clear()
    _get_blind_index_key.cache_clear()


def encrypt(plaintext: Optional[str]) -> Optional[str]:
    if plaintext is None or plaintext == "":
        return plaintext
    return _get_multifernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(token: Optional[str]) -> Optional[str]:
    if token is None or token == "":
        return token
    try:
        return _get_multifernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise CryptoConfigError(
            "No se pudo descifrar: token invalido o la llave no esta en ENC_KEYS."
        ) from exc


def blind_index(value: Optional[str]) -> Optional[str]:
    """HMAC-SHA256 deterministico (hex 64) para busqueda por igualdad/unicidad.
    Normaliza trim+lower para colisionar variantes de mayusculas/espacios."""
    if value is None or value == "":
        return None
    norm = value.strip().lower().encode("utf-8")
    return hmac.new(_get_blind_index_key(), norm, hashlib.sha256).hexdigest()


def rotate_token(token: Optional[str]) -> Optional[str]:
    if token is None or token == "":
        return token
    return _get_multifernet().rotate(token.encode("ascii")).decode("ascii")


class EncryptedString(TypeDecorator):
    """Columna de texto cifrada de forma transparente (Fase Contract)."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt(value)

    def process_result_value(self, value, dialect):
        return decrypt(value)


BLIND_INDEX_LEN = 64
