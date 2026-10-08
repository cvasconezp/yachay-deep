# Core — Yachay Deep

Sistema de alerta temprana académica (learning analytics) de Yachay Deep Labs, en uso con datos
reales de estudiantes de la UPS. Repositorio **propietario** (ver `LICENSE`). La documentación vive
en `docs/` y el índice está en `README.md`; este archivo solo orienta. Ante cualquier duda, `docs/`
y `CONTRIBUTING.md` mandan.

## Leer antes de tocar

| Si vas a… | Lee primero |
|---|---|
| Cambiar estructura, módulos o stack | `docs/ARCHITECTURE.md`, `docs/MODULES.md` |
| Tocar auth, sesiones, cifrado, permisos o PII | `docs/SECURITY.md`, `docs/SECURITY_INFRA_CHECKLIST.md` |
| Añadir o cambiar un endpoint | `docs/API.md` |
| Crear o cambiar una métrica o indicador | `docs/DATA_DICTIONARY.md` (§8), `docs/MODELO_CONCEPTUAL_METRICAS.md` |
| Tocar riesgo, modelos ML o explicaciones | `docs/RIESGO_Y_COMPROMISO.md`, `docs/MARCO_ABANDONO_REPROBACION.md` |
| Desplegar o cambiar variables de entorno | `docs/DEPLOYMENT.md` |
| Saber qué está pendiente | `docs/ROADMAP.md`, `docs/AUDITS/` |

## Stack

- **Backend** (`backend/`): Python 3.11, FastAPI, SQLAlchemy 2.x, PostgreSQL 15, pytest.
- **ML** (`backend/ml/`): scikit-learn (regresión logística y random forest), explicaciones tipo SHAP
  y contrafactuales.
- **Ingesta:** ETL en `backend/etl/`; scraping del AVAC con Selenium en `backend/scraping/`, que
  corre a diario en GitHub Actions (`daily_scraping.yml`) con credenciales y TOTP en secretos.
- **Frontend** (`frontend/`): React 18 (JSX) + Vite + Tailwind, Vitest + Testing Library,
  ECharts/Recharts.
- **Infra:** Railway (backend y base de datos), Vercel (frontend).

## Comandos

```bash
# Desde la raíz (pytest.ini fija testpaths y cobertura mínima del 60 %)
pytest
ruff check backend/ && ruff format --check backend/

# frontend/
npm test              # Vitest
npm run build
```

Antes de dar un cambio por terminado: pytest, ruff y `npm test`, y actualizar `CHANGELOG.md`
(sección `[Unreleased]`). En el CI, `pip-audit` y `npm audit` son bloqueantes; ruff hoy **no** lo
es (termina en `|| true`), así que no confiar en que el CI lo detecte.

## Cómo evoluciona la base de datos

**No hay migraciones.** Alembic está en `requirements.txt` pero no se ha adoptado. En cada arranque,
`main.py` ejecuta `create_tables()` (`create_all`) y `upgrade_tables()` en `backend/database.py`,
que añade columnas nuevas a tablas existentes desde un mapa tabla → columnas.

- Una **tabla nueva** se crea sola si su modelo está registrado en `backend/models/__init__.py`.
- Una **columna nueva** en una tabla existente debe añadirse también al mapa de `upgrade_tables()`;
  si no, el modelo la tiene y la base de producción no.
- Renombrar o borrar columnas no está cubierto por ese mecanismo. Pasar a Alembic es trabajo
  pendiente (`docs/ROADMAP.md`); no se hace de paso.

## Reglas de la casa

- **Lógica de dominio en el backend.** El frontend no recalcula métricas de dominio.
- **Toda métrica nueva** se documenta en `docs/DATA_DICTIONARY.md` §8.
- **Ámbito por carrera, denegar por defecto.** En rutas que leen estudiantes, filtrar con
  `filtrar_carrera()` de `backend/services/scope.py`. Un usuario no-admin sin carreras asignadas no
  ve ninguna.
- **Multi-tenant:** hoy cada cliente tiene su propia instancia. `backend/tenant_filter.py` prepara
  la base compartida (`tenant_query()` + RLS) para cuando haya cuatro o más clientes; si se activa,
  toda lectura de datos de cliente debe pasar por `tenant_query()`.
- **Nunca registrar PII.** Usar `mask_email()` / `mask_cedula()` de `backend/services/logsafe.py`.
  La PII sensible (cédula, etnia, ubicación, género, `totp_secret`) se guarda cifrada con Fernet e
  índice ciego; no añadir copias en texto plano.
- **Secretos:** nunca en el repo; `.env` está ignorado.
- **Ramas y PR:** una rama por cambio (`feat/`, `fix/`, `chore/`, `docs/`), PR contra `main`, sin
  push directo a `main`.
- **Idioma:** interfaz y documentación en español.

## Operaciones que requieren aprobación explícita

No ejecutar sin un sí explícito de Carlos:

- **Contract 2.3b:** el borrado del texto plano huérfano de PII. Requiere respaldo verificado.
- Cualquier borrado o acción destructiva sobre datos reales.
- Cambios en manejo de secretos, cifrado o permisos.
- Ejecutar ETL, scraping o reentrenamiento contra la base de producción.

## Marca

Los colores, tipografía y activos vienen del paquete `@yachaydeep/brand` (preset de Tailwind en
`frontend/tailwind.config.js`; activos sincronizados con `npm run sync-brand`). El sistema de marca
se cambia en el repo `yachaydeep-brand`, no aquí. Al diseñar o pulir interfaz, usar sus tokens en
lugar de colores o tipografías nuevas.

## Skills y agentes instalados

En `.claude/`, de terceros, sin hooks. Procedencia y licencias en
`.claude/THIRD_PARTY_NOTICES.md`.

- **Skills:** `impeccable` (diseño y auditoría de interfaz), `fastapi-patterns`, `python-patterns`,
  `python-testing`, `security-review`, `postgres-patterns`, `mle-workflow`, `react-patterns`,
  `react-testing`.
- **Agentes:** `python-reviewer`, `security-reviewer`, `database-reviewer`, `mle-reviewer`,
  `react-reviewer`, `privacy-engineer`, `data-visualization-engineer`, y los cuatro auxiliares
  `impeccable-*`.

`impeccable` descarga un binario desde las releases de su proyecto la primera vez que se ejecuta.
Lo contrasta con un `.sha256` que pide al mismo servidor: eso detecta una descarga corrupta, pero
**no** una release comprometida. Si no se quiere esa descarga, basta con no aprobar ese comando; el
skill tiene un modo de solo guía.

Son guías genéricas. Varias asumen migraciones con Alembic o un linter bloqueante, y aquí no hay
ninguna de las dos cosas. Si contradicen este archivo, `docs/` o `CONTRIBUTING.md`, prevalecen estos.
