# SECURITY — Core (Yachay Deep)

Documento canónico de seguridad. Refleja el estado real del código (julio 2026). Sustituye a `SECURITY_FRAMEWORK.md` (marcado como deprecado). Ver también [SECURITY_INFRA_CHECKLIST.md](./SECURITY_INFRA_CHECKLIST.md) y [AUDITS/](./AUDITS/).

Sensibilidad: **Alta** — PII de estudiantes incluida **categoría especial** (autoidentificación étnica), bajo **LOPDP (Ecuador)**.

---

## Autenticación y sesión

- **JWT HS256 en cookie `HttpOnly` + `Secure` + `SameSite=Lax`**, dominio acotado (`.yachaydeep.com`).
- **Access token 30 min** + **refresh token 30 días** rotativo con **detección de reuso**.
- **PIN de bloqueo por inactividad** (server-side, 423 hasta verificar).
- **Hash de contraseñas: argon2id** (bcrypt legacy con rehash transparente).
- **2FA TOTP** (pyotp) con códigos de recuperación hasheados; flags `REQUIRE_2FA` / `REQUIRE_ADMIN_2FA`.
- **RBAC** con 4 roles (admin/coordinador/docente/monitor) + aislamiento multi-tenant por contexto.
- **Google OAuth**: no aplica en Core (por diseño). Cuentas provisionadas por admin + login contraseña/2FA; el login con Google es patrón de Áncora, no de Core.

## Datos y cifrado

- **Cifrado en reposo** de PII sensible: Fernet field-level + blind index (HMAC) para búsqueda exacta. Campos cifrados: cédula, etnia, país/provincia/ciudad/parroquia/barrio, género, `totp_secret`.
- ⚠️ **Contract 2.3b pendiente:** el texto plano huérfano sigue físicamente en la BD hasta ejecutar el drop (requiere backup verificado + confirmación — gate).
- **En tránsito:** HTTPS (Railway/Vercel) + HSTS.
- **LOPDP:** registro de tratamiento y política de retención — pendientes de formalizar.

## Postura OWASP (resumen)

- **Secretos:** variables de entorno; `validate_security_settings()` aborta en producción si `SECRET_KEY` es el default. `.env` no versionado.
- **Cabeceras:** CSP, HSTS (prod), X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy, Permissions-Policy.
- **CORS:** orígenes explícitos + regex `*.yachaydeep.com`, `allow_credentials`. No wildcard.
- **Inyección SQL:** ORM parametrizado; f-strings de SQL solo sobre valores no-usuario (allowlist recomendado).
- **XSS:** React escapa por defecto; sin `dangerouslySetInnerHTML`.
- **Rate limiting:** en login y verify-pin. ⏳ pendiente extender a refresh/uploads/admin con store persistente (hoy in-memory).
- **Logging seguro:** ✅ correos enmascarados (`services/logsafe.py`); nunca se loguean tokens/contraseñas.
- **Errores:** ✅ el cliente recibe `{"detail":"Error interno"}`; la traza va solo a logs.

## CI/CD de seguridad

- GitHub Actions: lint + tests con cobertura mínima 60% + **`pip-audit` / `npm audit` bloqueantes**.
- Backups: `pg_dump` (plataforma). ⏳ pendiente restore drill documentado + custodia offline de `ENC_KEYS`/`BLIND_INDEX_KEY`.

## Reporte de vulnerabilidades

Reportar en privado a cvasconezp@gmail.com. No abrir issues públicos con detalles explotables.

---

*Estado y hallazgos priorizados: ver [AUDITS/](./AUDITS/). Última actualización: 2026-07.*
