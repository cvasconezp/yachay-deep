# Contributing — Core (Yachay Deep)

Repositorio **propietario** (ver [LICENSE](./LICENSE)). Estas pautas aplican al equipo con acceso autorizado.

## Flujo de trabajo

1. Crea una rama por cambio: `feat/…`, `fix/…`, `chore/…`, `docs/…`.
2. Haz commits pequeños y descriptivos (recomendado: [Conventional Commits](https://www.conventionalcommits.org/), p. ej. `feat(metrics): …`).
3. Abre un Pull Request contra `main`. No hagas push directo a `main`.
4. El PR debe pasar CI (lint, tests, auditoría de dependencias).

## Antes de abrir el PR

```bash
# Backend
cd backend
pytest --cov=backend --cov-fail-under=60      # cobertura mínima 60%
ruff check . && ruff format --check .

# Frontend
cd ../frontend
npm test
```

- `pip-audit` / `npm audit` son **bloqueantes** en CI: resuelve o documenta en el allowlist explícito.
- Actualiza [CHANGELOG.md](./CHANGELOG.md) (sección `[Unreleased]`).
- Si tocas documentación, mantenla en `docs/` y actualiza el índice del [README](./README.md).

## Estándares de código

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.x. Lógica de dominio en backend (no recomputar métricas de dominio en el frontend).
- **Datos/seguridad:** nunca loguear PII (usa `services/logsafe.py`); nunca commitear secretos (`.env` está en `.gitignore`); métricas nuevas se documentan en `docs/DATA_DICTIONARY.md` §8.
- **Migraciones:** al adoptarse Alembic, todo cambio de esquema va con su migración (ver `docs/ROADMAP.md`).

## Operaciones sensibles (requieren aprobación explícita)

- Drop de datos / Contract 2.3b (texto plano de PII).
- Cambios en manejo de secretos, cifrado o permisos.
- Cualquier acción destructiva sobre datos reales.

## Reporte de seguridad

En privado a cvasconezp@gmail.com. No abras issues públicos con detalles explotables. Ver [docs/SECURITY.md](./docs/SECURITY.md).
