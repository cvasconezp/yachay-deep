# DEPLOYMENT — Core (Yachay Deep)

Documento canónico de despliegue.

Stack de hosting: **Backend en Railway**, **Frontend en Vercel**, **PostgreSQL en Railway**.

---

## Requisitos

- Python 3.11+, Node.js 18+, PostgreSQL 14+.
- Cuentas Railway y Vercel.

## Variables de entorno (mínimas de producción)

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | Connection string PostgreSQL |
| `SECRET_KEY` | JWT secret — `openssl rand -hex 32` (la app aborta en prod si es el default) |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Bootstrap del admin inicial |
| `ENC_KEYS` / `BLIND_INDEX_KEY` | Cifrado en reposo (Fernet + blind index) — **custodiar offline** |
| `TELEMETRY_KEY` | Pseudonimización de telemetría de uso (opcional; cae a `SECRET_KEY`) |
| `CORS_ORIGINS` | Orígenes permitidos (JSON array o CSV) |
| `AVAC_*` | Credenciales de scraping (solo si se usa scraping) |
| `SMTP_*`, `BIENESTAR_EMAIL` | Correo (derivaciones) |
| `SENTRY_DSN` | Monitoreo de errores (opcional) |

`.env` está en `.gitignore`; solo se versiona `.env.example`. **Nunca** commitear secretos.

## Backend (Railway)

- Build por `Dockerfile` (`python:3.11-slim`, `uvicorn backend.main:app`).
- Migraciones: hoy vía `create_tables()` + `upgrade_tables()` en el arranque. ⏳ Migrar a **Alembic** (`alembic upgrade head`) — ver [ROADMAP.md](./ROADMAP.md).
- Healthcheck: `GET /health`.

## Frontend (Vercel)

- `vite build`; SPA con proxy `/api/*` → backend Railway.
- Configurar `VITE_API_URL` si aplica.

## CI/CD

- `.github/workflows/ci.yml`: lint (ruff) + tests con cobertura ≥60% + `pip-audit`/`npm audit` **bloqueantes**.
- `.github/workflows/daily_scraping.yml`: scraping programado.
- Deploy automático en push a `main` (Railway/Vercel).

## Backups

- `pg_dump` gestionado por la plataforma. ⏳ Documentar restore drill y custodiar `ENC_KEYS`/`BLIND_INDEX_KEY` offline (si se pierden, los datos cifrados son irrecuperables).

## Checklist de release

1. Tests en verde (`pytest --cov=backend --cov-fail-under=60`, `npm test`).
2. Variables de entorno de producción configuradas (secretos no-default).
3. Migración aplicada.
4. Healthcheck OK tras el deploy.

---

*Detalle de infraestructura y seguridad: [SECURITY.md](./SECURITY.md) · [SECURITY_INFRA_CHECKLIST.md](./SECURITY_INFRA_CHECKLIST.md). Última actualización: 2026-07.*
