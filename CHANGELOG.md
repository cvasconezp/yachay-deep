# Changelog

Todos los cambios notables de Core se documentan aquí.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).
Versionado semántico cuando aplique.

## [Unreleased] — rama `chore/estandar-casa`

<!-- ───────────────────────────────────────────────────────────────────── -->
### Sesiones oct 2026 — transición de período P68 → P69

**Added**
- **Módulo Reprobación y Abandono** (interno `reprobados`): responde "¿qué estudiantes reprobaron y por qué?". Endpoint `GET /analytics/reprobados?periodo&carrera&nivel` + `GET /analytics/reprobados/export` (`backend/routes/analytics/reprobados.py`, `require_admin`) y página `frontend/src/pages/Reprobados.jsx` (ruta `/reprobados`, sidebar 📉, `adminOnly`). Por cada reprobado reúne: académico (asignaturas reprobadas con nota, promedio, repitencia/3ª matrícula), conductual (índice de compromiso, días sin AVAC, % tareas), administrativo (estado de matrícula), seguimiento (intervenciones, "sin respuesta"/"sin intervención") y predictivo (prob. reprobación/deserción, recuperabilidad); `causa_probable` heurística (Administrativa > Desconexión > Académica). KPIs + filtros Período/Carrera/Nivel/Grupo/Riesgo/Causa/Condición + buscador. **Export Excel enriquecido** generado en backend con openpyxl: hoja **LÉEME** (autoría/licencia/cita), hoja **Análisis** (KPIs + lectura automática en español + gráficas nativas: pastel por causa, barras por riesgo y seguimiento) y hoja **Detalle**. El cálculo vive en `_compute_reprobados()`, compartido por JSON y export.
- **Listado plano de docentes (exportable):** `GET /analytics/docentes/listado?carrera&periodo` — una fila por **docente × asignatura × grupo** (desde `CourseConfig`, enriquecida con matrículas y notas): docente, **correo**, carrera, asignatura, nivel, grupo, bloque, código AVAC, período, nº estudiantes, riesgo alto, promedio, % aprobación. En la página Docentes, botón **"Exportar listado"** (junto a "Exportar resumen") con enlace al aula AVAC y columnas ampliables (`DOC_LISTADO_COLS`). Sirve para cualquier carrera.
- **Mallas curriculares oficiales (PDF → JSON)** para que la Ficha muestre la malla **completa** por carrera aunque no se haya cursado la asignatura: `backend/data/mallas/GESTION_AMBIENTAL.json` (8 niveles/43), `MARKETING_E_INTELIGENCIA_DE_MERCADOS.json` (8/41), `GASTRONOMIA.json` (4/23) + alias `TECNOLOGIA_SUPERIOR_EN_GASTRONOMIA.json`. Emparejamiento de asignaturas **sin tildes** (`_normalize_asig`).
- **Marco conceptual de literatura:** `docs/MARCO_ABANDONO_REPROBACION.md` — terminología (deserción/abandono/permanencia/retención/rezago), tipología nano/micro/meso/macro, catálogo de variables mapeado a Core (✅ usado / 🟡 capturado / ⬜ brecha), modelos teóricos (Tinto, Bean & Eaton, Spady, Lent, Becker, Bronfenbrenner) y recomendación de nombre del módulo ("Reprobación y Abandono").

**Fixed (integridad de datos y robustez)**
- **Carrera del estudiante — fuente de verdad = reporte.** Dos arreglos sistémicos: (1) al consolidar el reporte, la carrera se toma por **moda** (la más frecuente entre las matrículas), no por la primera fila arbitraria (`transform_personales`); (2) `_seed_students_from_personales` ahora **sobreescribe siempre** la carrera desde el reporte, incluso para matriculados **sin actividad en AVAC** (antes solo se actualizaba a quienes aparecían en el master de AVAC, así que un "Sin AVAC" se quedaba con una carrera vieja/equivocada para siempre). Caso: RODRIGUEZ CHASIN DAVID ISRAEL salía en "Ciencia de Datos" con sus 6 matrículas en Antropología.
- **Ficha — la nota de una matrícula vigente sale SOLO del período vigente.** En la vista vigente, `calificaciones` = período activo (o sin período); `calificaciones_historicas` = **estrictamente** períodos anteriores; la nota de cada matrícula se busca solo en el período vigente (antes caía al histórico por nombre y mostraba notas de períodos anteriores en materias recién matriculadas). Caso: FARINANGO MALDONADO KARINA RUBI con notas en materias de P69 recién matriculadas (`backend/routes/students.py`, `frontend/src/pages/FichaEstudiante.jsx`).
- **Ficha — matrículas solo del período vigente** (no mezclar P68/P69 en "Asignaturas matriculadas"); la malla sigue mostrando el histórico. Caso: CHAVARRIA GUAJAN KIMBERLY.
- **Deduplicación de estudiantes insensible al orden de nombres** (match por tokens ordenados ≥3): caso GLENDY OSWALDO TAPUY LANZA duplicado por orden de apellidos/nombres.
- **ETL robusto ante CSV institucionales (Windows-1252/Latin-1) y decimales con coma:** `_leer_csv_robusto` (utf-8-sig → cp1252 → latin-1) y `_nota_a_float`. Resuelve cargas que daban "0 registros".
- **Contador de registros del ETL** cuenta las matrículas; `_sync_course_configs` deja de reventar con `pd.NA` ("boolean value of NA is ambiguous").
- **Crash "asig is not defined"** en el detalle de Analítica de Asignaturas (el export por grupo usaba una variable fuera de alcance → `detalle.asignatura/.docente`) (`frontend/src/pages/Asignaturas.jsx`).
- **Reprobados — Nivel desde matrícula** cuando `Grade.nivel` viene NULL; export Excel recuperó la hoja **LÉEME** que faltaba.

**Changed**
- **Enlace de AVAC por período (grado del período).** Frontend centralizado en `frontend/src/utils/avac.js` (`avacCourseUrl(codigo, periodo)`; `GRADO_VIGENTE`); al pasar a P69 se apunta a `grado69` en Asignaturas, Docentes, Entregas, Seguimiento y Ficha. **Backend:** la verificación de la cookie AVAC y el scraping derivan el grado del **período activo** (`_avac_base_url(db)` en `backend/routes/admin.py`; `AVAC_BASE_URL` por defecto `grado69`); antes quedaban fijos en `grado68` y la cookie "no abría" sesión en P69. El nº de grado sigue al nº de período (P69→grado69).
- **Grupos — selector `fuente_nota`** (mixta/final/avac) para elegir el origen de la nota mostrada (`backend/routes/analytics/grupos.py`, `frontend/src/pages/Grupos.jsx`).

**Security**
- **Dependencias — CVEs nuevos (CI `security-audit`):** `cryptography` 48.0.1 → **50.0.2** (cierra PYSEC-2026-3552/3553/3554; JWT y Fernet verificados). `python-jose` 3.5.0 sin fix para CVE-2026-85394 → allowlist del CI (se elimina al migrar a PyJWT). Frontend `.nsprc`: excepciones documentadas (react-router modo-RSC no usado; tooling de build/test — braces, browserslist, nanoid, postcss, source-map-js, undici vía jsdom — que no llega al bundle del navegador). TODO: `npm audit fix` donde resuelvan las deps privadas para subir de versión y retirar excepciones.

**Hardening de control de acceso por carrera (revisión con agentes)**
- Varios endpoints devolvían datos de estudiantes **sin aplicar el ámbito por carrera** (`services/scope.py`), así que un usuario no-admin acotado a una carrera podía leer PII (cédula, correo, notas, intervenciones) o indicadores de riesgo de **cualquier** estudiante por ID (IDOR) o por volcados de listado/exportación. Se cerró aplicando `filtrar_carrera` / `asegurar_acceso_carrera` (el admin sigue sin restricción) en: `export.py` (ficha PDF, Excel de estudiantes e intervenciones), `analytics/resumen.py` (listado y stats), `alerts.py` (pendientes, conteo, detalle por estudiante), `predictions.py` (student/recommendations/counterfactual/what-if), `ml_advanced.py` (adaptive/explain), `dashboard.py` (inactividad por curso) e `interventions.py` (crear/bulk/listar).
- **Path traversal** en la subida de prácticas (`admin.py`): se usa `basename` del filename y se confirma que el destino queda dentro de la carpeta.
- **PII en logs:** se enmascaran correos en login fallido y cambio de correo (`mask_email`); `/health` ya no expone el detalle del error de BD a llamadores no autenticados.

**Correcciones de correctitud**
- **Reprobados sin `?periodo`** usaba `periodo IS NULL` ("actual") y, tras la migración que etiqueta los grades NULL como P67, devolvía el informe **vacío**; ahora cae al período **activo**. El filtro `?nivel` usa el nivel **de la matrícula** (Enrollment), no `Grade.nivel` (que suele venir NULL y excluía estudiantes / corrompía promedios).
- **`docentes/listado`** ya no incluye secciones con `CourseConfig.semestre` NULL en todos los períodos (arrastraba secciones viejas al listado del período pedido).
- **`_upsert_enrollments`** etiqueta el período por **moda** (no por la primera fila), coherente con la auto-activación del semestre.

**Estabilidad — pool de conexiones a la BD**
- El panel de Administración mostraba de forma intermitente "Error: No se pudo cargar el estado del sistema" (y 500 en `/admin/etl/scraping-progress`, `/admin/system/avac-cookie`, predicciones). Causa: `QueuePool limit of size 3 overflow 5 reached, connection timed out` — el pool (máx 8) se agotaba porque el servidor corre un solo worker de uvicorn y FastAPI atiende los endpoints sync en un threadpool (~40), que bajo el polling del panel + endpoints ML superaba las 8 conexiones. Se sube el pool a **10+20=30** (configurable por entorno: `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `DB_POOL_RECYCLE`) en `backend/database.py`.

**AVAC por período — auto-derivado también en el scraping**
- Nuevo `backend/services/avac.py::avac_base_url(db)`: deriva el grado del **período activo** (P69→grado69). Lo usan la verificación de cookie (`admin.py`, refactorizado) y el **scraping** (`ingresos_avac.py`, `estado_tareas.py`). Antes el scraping corría en GitHub Actions con `AVAC_BASE_URL` fijo en grado68 (secret/entorno distinto al de Railway), así que al pasar a P69 la cookie "no abría". Ahora el scraping se auto-corrige desde la BD sin depender de esa variable; el default del workflow se actualizó a grado69.

<!-- ───────────────────────────────────────────────────────────────────── -->
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
- **Motor de riesgo de 3 capas + novedades (análisis del paper):** documentado en `docs/MODELO_CONCEPTUAL_METRICAS.md` §5.1. El paper articula índice → banda → **estado** con **novedades** cualitativas (red de seguridad) y **compuerta administrativa**; Core hoy colapsa la 3ª capa en la 2ª y trata la matrícula como 15 % (no compuerta). Pendiente decidir e implementar: capa "estado", novedades, decisión sobre la compuerta, declarar el límite conductual y exponer los puntajes por componente en la UI (PD2). Solo documentación por ahora.
- **P-DISC — Alerta de discrepancia nota final ↔ AVAC:** conservar ambas notas por (estudiante, asignatura) y alertar cuando difieren extremadamente (p. ej. AVAC 88 / final 0 por baja administrativa), para rectificar y anticipar reclamos. Es la **primera novedad** concreta de la capa "estado". Diseño en `docs/MODELO_CONCEPTUAL_METRICAS.md` §6.
- **Re-validar umbrales** del índice (0.80/0.65/0.35) con la distribución posterior a H1.
- Alembic (retirar `create_all`/`upgrade_tables`), rate limiting con store persistente, versionado de modelos ML.
- **Higiene de dependencias:** correr `cd frontend && npm audit fix` donde resuelvan las deps privadas `@yachaydeep` (tu máquina o CI) para subir de versión las transitivas con fix (react-router 7.18.x, braces, browserslist, nanoid, postcss, source-map-js, undici) y **retirar** las excepciones de `frontend/.nsprc`. Migrar `python-jose` → **PyJWT** para eliminar `ecdsa` y cerrar CVE-2026-85394 (quita dos entradas del allowlist de `pip-audit`).
- **Scraping AVAC auto-derivado por período:** hoy el scraping lee `AVAC_BASE_URL` del entorno (se actualizó a `grado69`); falta que derive el grado del período activo igual que la verificación de cookie, para no tocar la variable cada semestre.
- (Google OAuth queda **descartado en Core por diseño** — no es un pendiente.)
- 🔒 Contract 2.3b (drop del texto plano de PII) — requiere backup verificado + confirmación explícita.

---

*Base histórica: Fases 1–5 completadas; Fase 6 (integración LMS en tiempo real) en curso. Ver `docs/ROADMAP.md`.*
