# Changelog

Todos los cambios notables de Core se documentan aquí.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).
Versionado semántico cuando aplique.

## [Unreleased] — rama `chore/estandar-casa`

### Added
- **Módulo Grupos** (vista pivote estudiante × asignatura). Endpoint `GET /analytics/grupos?periodo&carrera&nivel` (`backend/routes/analytics/grupos.py`, `require_admin`) y página `frontend/src/pages/Grupos.jsx` (sidebar antes de Asignaturas, ícono 👥, `adminOnly`). KPIs estilo Asignaturas; filtros Período/Carrera/Nivel/**Grupo**/**Condición especial**/**Riesgo** + buscador; primera columna congelada y **encabezados fijos**; encabezados ordenables; nota con color aprobado/reprobado y promedio por estudiante; **selección de filas + Registrar Intervención** (reutiliza `BulkInterventionModal`); export a Excel con columnas dinámicas. La nota sale de `Grade.nota_final ?? TaskSubmission.total_curso` (AVAC), igual que la Ficha.
- **Guía maestra de desarrollo:** `docs/GUIA_MODULOS_Y_HALLAZGOS.md` — patrones, convenciones y hallazgos de datos para construir módulos nuevos reutilizando lo existente (auth, filtros, tabla pivote, notas de AVAC, bloques, snapshots, normalización de asignaturas, intervenciones, despliegue). Incluye receta paso a paso, checklist y bitácora de hallazgos.
- **Fuente única de impacto:** endpoint `GET /metrics/impact` (`estudiantes_monitoreados`, `programas_activos`) computado desde la BD (`backend/routes/metrics.py`).
- **Telemetría de uso** pseudonimizada (actor por HMAC, sin PII) en tabla aislada `usage_events` (`backend/models/usage_event.py`, `backend/services/telemetry.py`); evento `login` instrumentado.
- **Logging seguro:** `backend/services/logsafe.py` (`mask_email`).
- **Diccionario de métricas** versionado (`docs/DATA_DICTIONARY.md` §8).
- **Documentación:** `docs/PRODUCT.md`, `docs/ROADMAP.md`, `docs/SECURITY.md`, `docs/DEPLOYMENT.md`, `docs/USER_GUIDE.md`, `docs/ADMIN_GUIDE.md`, `docs/AUDITS/`, `LICENSE`, `CONTRIBUTING.md`, este `CHANGELOG.md`.

### Changed
- **Ficha del estudiante — AVAC por curso:** los accesos y tareas ahora usan el **snapshot más reciente de cada curso** (antes solo el último snapshot global, que en pleno semestre solo trae el bloque activo). Así las materias de un bloque ya cerrado siguen mostrando su nota/actividad de AVAC en vez de "Sin AVAC / Cursando" (`backend/routes/students.py`).
- **Manejo de errores:** el handler global devuelve `{"detail":"Error interno"}` al cliente; la traza queda solo en logs (`backend/main.py`).
- **Correos enmascarados** en logs (`services/email.py`, `services/daily_digest.py`).
- **CI:** `pip-audit` / `npm audit` ahora **bloquean** el build (se retiró `|| true`) (`.github/workflows/ci.yml`).
- **Landing** lee la cifra de impacto desde `/metrics/impact` en vez de un número estático (`frontend/src/pages/Landing.jsx`).
- **README** alineado a los hallazgos de auditoría; se retiraron conteos hardcodeados; endoso canónico + badge `INSIGNIA`.

### Removed
- `docs/DEPLOY.md` (estaba deprecado) → eliminado; su reemplazo es `docs/DEPLOYMENT.md`. Contenido histórico en el historial de git.
- `docs/SECURITY_FRAMEWORK.md` (estaba deprecado) → eliminado; su reemplazo es `docs/SECURITY.md`. Contenido histórico en el historial de git.

### Pending (no incluido aún)
- Alembic (retirar `create_all`/`upgrade_tables`), rate limiting con store persistente, versionado de modelos ML.
- (Google OAuth queda **descartado en Core por diseño** — no es un pendiente.)
- 🔒 Contract 2.3b (drop del texto plano de PII) — requiere backup verificado + confirmación explícita.

---

*Base histórica: Fases 1–5 completadas; Fase 6 (integración LMS en tiempo real) en curso. Ver `docs/ROADMAP.md`.*
