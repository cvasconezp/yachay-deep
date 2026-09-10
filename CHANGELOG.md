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
- **Modelo de riesgo/compromiso — respaldo académico con AVAC (H1):** el componente de rendimiento del índice de compromiso ahora usa `nota_final ?? total_curso`. Ante la ausencia de nota final (semestre en curso), toma el parcial de AVAC (`total_curso`) como proxy; la nota final, cuando existe, la reemplaza. Antes se asignaba ~nota 50 a todos y el modelo sesgaba a "Alto" pese a buenos parciales. Implementado en `backend/etl/transformers.py::calcular_indice_compromiso` (nuevo parámetro `promedio_total_curso`) y en los tres puntos de cálculo (`transformers.py`, `pipeline.py`, `services/recalculo.py`). Los nuevos valores de riesgo se reflejan tras el próximo ETL/recálculo. Docs: `docs/RIESGO_Y_COMPROMISO.md`, `docs/MODELO_CONCEPTUAL_METRICAS.md`.
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
- **P-DISC — Alerta de discrepancia nota final ↔ AVAC:** conservar ambas notas por (estudiante, asignatura) y alertar cuando difieren extremadamente (p. ej. AVAC 88 / final 0 por baja administrativa), para rectificar y anticipar reclamos. Diseño en `docs/MODELO_CONCEPTUAL_METRICAS.md` §6.
- **Re-validar umbrales** del índice (0.80/0.65/0.35) con la distribución posterior a H1.
- Alembic (retirar `create_all`/`upgrade_tables`), rate limiting con store persistente, versionado de modelos ML.
- (Google OAuth queda **descartado en Core por diseño** — no es un pendiente.)
- 🔒 Contract 2.3b (drop del texto plano de PII) — requiere backup verificado + confirmación explícita.

---

*Base histórica: Fases 1–5 completadas; Fase 6 (integración LMS en tiempo real) en curso. Ver `docs/ROADMAP.md`.*
