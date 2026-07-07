# Inventario y estandarización de métricas — Core

*Analista de datos de producto. Base: código real citado en `Ficha-Producto-Yachay-Deep.md` y `Auditoria-Tecnica-Yachay-Deep.md` (commit `41a0ea4`), más la meta en vivo de `yachaydeep.com/core`. Fecha: 2026-07-07.*

## Contexto (inferido de la evidencia; el `{CONTEXTO}` llegó vacío)

| Campo | Valor | Fuente |
|---|---|---|
| Producto | **Core** — inteligencia académica preventiva | continuidad de la auditoría anterior |
| Qué datos ingiere el usuario | Interacción de aula virtual: **accesos, entregas de tareas, calificaciones** (scraping Moodle/AVAC con Selenium), **uploads Excel/CSV/ZIP** por admin, y formularios (Microsoft Forms); más **demografía/PII** de estudiantes (cédula, etnia, domicilio) | Auditoría Técnica §4 (fuentes de ingesta), Ficha §1 |
| ¿Analítica de uso instrumentada? | **NO ENCONTRADO.** No hay GA, PostHog, Sentry ni capa de eventos propios en `requirements.txt`/`package.json`. Lo más cercano son `refresh_token`, rate-limit y `services/daily_digest.py` (correo operativo), que **no** son telemetría de producto | Auditoría Técnica §1 (stack completo, sin SDK de analítica) |

> **Límite de evidencia (honesto).** El repo `cvasconezp/yachay-deep` es **privado** y la landing `/core` es una SPA que no pude renderizar (sin navegador conectado). El inventario se construye sobre los **módulos citados a nivel de archivo** en los dos documentos técnicos (`routes/analytics/*`, `ml/*`, `models/*`), que son evidencia real de dónde se calcula cada cifra, no sobre el render de cada tarjeta. Donde una cifra mostrada no tiene origen rastreable, se marca **NO ENCONTRADO**.

---

## 1. Inventario de métricas

Organizado por dónde se calcula. "Dónde se muestra" es el módulo/vista que la expone según la evidencia; el detalle exacto de cada tarjeta no es verificable sin render.

**Capa de dominio — calculadas en backend (ML + consultas de analítica):**

| Métrica | Dónde se muestra | Dónde se calcula |
|---|---|---|
| `prob_desercion` (probabilidad de deserción) | Ficha 360°, dashboard de riesgo, alertas | Backend ML — `ml/predict.py` (modelo por carrera: LogisticRegression/RandomForest) |
| `prob_reprobacion` (probabilidad de reprobación) | Ficha 360°, dashboard | Backend ML — `ml/predict.py` |
| Nivel/priorización de riesgo + medio de contacto | Motor de recomendaciones, alertas | Backend — `ml/recommendations.py:146`, `adaptive_recommendations.py` |
| Contribuciones por feature (XAI) | Explicación "por qué está en riesgo" | Backend — `ml/explainability.py` (SHAP con **fallback casero**; `shap` no instalado) |
| Contrafactuales ("qué cambiaría el resultado") | Ficha del estudiante | Backend — `ml/counterfactual.py`, `counterfactual_conductual.py` |
| Indicadores por asignatura | Analítica de asignaturas | Backend/consulta — `routes/analytics/asignaturas` |
| Indicadores por docente · `docente_effectiveness` · `docente_tracking` | Analítica docente | Backend/consulta — `routes/analytics/docentes` |
| Entregas (entregadas/pendientes/atraso) | Analítica de entregas | Backend/consulta — `routes/analytics/entregas` |
| Indicadores de tutorías | Analítica de tutorías | Backend — `routes/analytics/tutorias` |
| Terceras matrículas | Analítica específica | Backend — `routes/analytics/terceras_matriculas` |
| Series históricas / tendencias | Vista histórica | Backend — `routes/analytics/historico` |
| Indicadores ejecutivos por autoridad | Reporte ejecutivo | Backend — `routes/analytics/executive` (`executive.py`) |
| Ficha 360° del estudiante (agregado) | Ficha 360° | Backend — agregación sobre modelos + ML |
| Efectividad de intervenciones (snapshots antes/después) | Seguimiento de intervención | Backend — `models/intervention.py:42-47`, `effectiveness.py` |
| Early-warning de práctica preprofesional | Módulo de prácticas | Backend — modelo `practica_preprofesional` |

**Capa de uso (telemetría):**

| Métrica | Estado |
|---|---|
| Sesiones, usuarios activos, funnel, retención, features usadas, clics | **NO ENCONTRADO** — no hay instrumentación de analítica de uso |

**Cifras de impacto / marketing (landing y ficha):**

| Cifra | Dónde se muestra | Dónde se calcula |
|---|---|---|
| "**3.040+ estudiantes**" | Tarjeta de Core en la página Labs | **NO ENCONTRADO** origen rastreable — §13 de la arquitectura anota que aparece "solo en la tarjeta de Labs", sin fuente canónica |
| "**25 programas**" | Tarjeta Labs | **NO ENCONTRADO** origen rastreable (deriva de conteo de carreras/tenants, sin fuente fijada) |
| "125 endpoints", "16+ modelos ORM", "14 módulos de analítica", "772 funciones de test" | README / ficha | Conteos de ingeniería en texto; **desincronizados** (el README dice "330+" tests vs. 772 reales) |

---

## 2. Clasificación — el eje central

**USO (telemetría) — clase esencialmente vacía en Core.** No existe capa instrumentada. Cualquier pregunta de uso ("¿cuántos monitores entraron esta semana?", "¿qué % abrió la ficha 360°?", "¿se actuó sobre la recomendación?") **hoy no tiene respuesta** en el producto. *Fuente de verdad: inexistente. Reproducible: N/A.*

**DOMINIO (interpretación de datos cargados) — el grueso del producto.** Todas las métricas del bloque de dominio de §1. Es el valor de Core: leer accesos/entregas/notas ingeridos y devolver riesgo explicado y accionable.
- *Fuente de verdad:* features derivadas por el ETL (`etl/transformers.py`, `etl/pipeline.py`) sobre los datos ingeridos; los modelos `.pkl` por carrera para las probabilidades.
- *Fórmula/definición:* `prob_desercion`/`prob_reprobacion` = salida del clasificador por carrera; XAI = contribución por feature (o su *fallback*); efectividad = delta de snapshots antes/después.
- *Cadencia:* recomputo en cada predicción; **reentrenamiento cada N ETLs**; scraping diario programado (`daily_scraping.yml`).
- *Reproducible/auditable:* **parcialmente.** Las consultas de analítica sí son recalculables. Las probabilidades ML **no son reproducibles en el tiempo** sin fijar la versión del modelo (reentrena periódicamente y no hay evidencia de registro/versionado de modelos). El XAI **no es reproducible contra SHAP real** porque corre el *fallback* casero (`shap` no está en `requirements.txt`).

**VANIDAD / MARKETING — deriva de DOMINIO, con fuente distinta.** "3.040+ estudiantes" y "25 programas" derivan conceptualmente de la capa de **dominio** (conteo de registros de estudiantes / de carreras-tenant ingeridos), pero **su fuente mostrada NO es la misma**: viven como texto en la tarjeta de Labs sin recalcularse desde la BD. Los conteos de ingeniería (endpoints/tests/modelos) son cifras de capacidad, hardcodeadas en README/ficha y ya **desincronizadas** (330+ vs 772). *Reproducible: no — no leen su fuente.*

---

## 3. Problemas de confiabilidad

1. **Sin telemetría de uso (ausencia total).** No se puede definir ni medir "estudiante/monitor activo", adopción de features, ni si las recomendaciones se accionan. Es la mayor brecha de esta auditoría: Core mide muy bien el *dominio* y nada del *uso*. *Evidencia: stack sin GA/PostHog/Sentry/eventos, Auditoría §1.*
2. **Cifras de impacto sin fuente única.** "3.040+/25" solo en la tarjeta Labs, sin origen rastreable ni recomputo → **NO ENCONTRADO**. Riesgo de que envejezcan o contradigan la BD. *Evidencia: Arquitectura §13.*
3. **Conteos de ingeniería hardcodeados y desincronizados.** README "330+" tests vs. 772 reales; "125 endpoints", "16+ modelos" como texto. *Evidencia: Ficha §2.*
4. **Reproducibilidad del ML.** Reentrenamiento cada N ETLs sin versionado de modelo → `prob_desercion` de hoy no necesariamente reproducible mañana. **XAI "tipo-SHAP"** (fallback) ≠ SHAP real. *Evidencia: Ficha §1, §2; Auditoría §1 (shap no instalado).*
5. **Definiciones de dominio no documentadas de forma central.** "Riesgo", "docente_effectiveness", "en riesgo" no tienen diccionario de métricas versionado explícito (existe `docs/DATA_DICTIONARY.md`, pero cobertura de *definición de métrica* no verificable). *Evidencia: Ficha §3 (docs).*
6. **Riesgo de recomputo en el frontend en exportes.** El grueso del dominio vive en backend (bien), pero el frontend incluye `xlsx`/`file-saver` y `recharts`: verificar que los exportes **lean** valores calculados en backend y no los recomputen en cliente. *Evidencia: Auditoría §1 (frontend deps).*
7. **Formato no canónico casa-wide.** "3.040+" usa punto de miles (locale `es_EC`, confirmado en `og:locale`); las probabilidades ML (%/decimales) no tienen formato estandarizado compartido con los demás productos. *Evidencia: `web_fetch` og:locale; ausencia de guía de formato.*
8. **Mezcla uso/dominio:** hoy **no** ocurre (no hay uso instrumentado), pero cuando se instrumente telemetría hay que separarla explícitamente de los indicadores de dominio en los dashboards ejecutivos.

---

## 4. Estandarización propuesta (converger con la casa)

**Taxonomía común — tres capas separadas.**
- **Uso (telemetría):** capa nueva, aislada, con eventos pseudonimizados (LOPDP). Vive fuera de las tablas de dominio.
- **Dominio (indicadores):** siempre en backend, recalculable, con trazabilidad a la feature/consulta y a la versión de modelo.
- **Impacto (marca):** vistas de solo-lectura que **leen** una cifra canónica; nunca la reescriben.

**Fuente única de verdad para cada cifra de impacto.** Un endpoint canónico (p.ej. `GET /metrics/impact`) que compute "estudiantes monitoreados" y "programas activos" desde la BD, con su definición fijada; la landing/tarjeta Labs y cualquier pitch **consumen** ese número, no lo teclean.

**Diccionario de métricas versionado.** Extender `docs/DATA_DICTIONARY.md` a un diccionario con: `nombre · definición · fórmula · fuente (tabla/consulta/modelo) · cadencia · dueño · versión`. Entradas mínimas: `prob_desercion`, `prob_reprobacion`, `nivel_riesgo`, `docente_effectiveness`, `efectividad_intervencion`, `estudiantes_monitoreados`, `programas_activos`, y las definiciones de "activo/en riesgo".

**Formato canónico compartido.** Miles con punto (`es_EC`), decimales con coma, probabilidades como % con 1 decimal, monedas y % con la misma regla en toda la casa (aplicable también a Kullki/Áncora).

**Métricas de dominio auditables.** Mantenerlas en backend (ya lo están), y añadir: **versionado/registro de modelos** para reproducir `prob_*`, instalar `shap` real (o documentar el fallback como método propio y fijarlo), y garantizar que los exportes reflejan el valor backend.

**Qué instrumentar (uso) — recomendado, mínimo viable y pseudonimizado:**
`login`, `dashboard_view`, `ficha360_view`, `alerta_vista`, `recomendacion_vista`, `intervencion_creada`, `intervencion_cerrada`, `export_generado`. Con eso se responde adopción, funnel detección→intervención y "monitor activo".

**Qué mover al backend (dominio):** nada estructural — el dominio ya está en `routes/analytics/*` y `ml/*`. Acciones: (a) confirmar que los exportes `xlsx` del frontend no recomputan; (b) sacar "3.040+/25" de texto estático a la fuente canónica; (c) versionar los modelos para reproducibilidad.

---

## 5. Salida

### Tabla de métricas

| Métrica | Clase | Dónde se calcula | Fuente | Reproducible | Problema | Acción |
|---|---|---|---|---|---|---|
| `prob_desercion` | Dominio | Backend `ml/predict.py` | Modelo por carrera + features ETL | Parcial (sin versionado de modelo) | Reentrena cada N ETLs sin registro | Versionar modelos; fijar snapshot para auditoría |
| `prob_reprobacion` | Dominio | Backend `ml/predict.py` | idem | Parcial | idem | idem |
| Nivel de riesgo / priorización | Dominio | Backend `ml/recommendations.py` | Salida ML + reglas | Parcial | Definición de "riesgo" no documentada | Diccionario de métricas |
| Contribuciones por feature (XAI) | Dominio | Backend `ml/explainability.py` | Fallback casero (no SHAP) | No (≠ SHAP real) | `shap` no instalado | Instalar SHAP o documentar/fijar el método |
| Contrafactuales | Dominio | Backend `ml/counterfactual*.py` | Modelo + features | Parcial | — | Documentar definición |
| Indicadores asignatura/docente/entregas/tutorías/históricos | Dominio | Backend `routes/analytics/*` | Consultas sobre datos ingeridos | Sí | Definiciones no centralizadas | Diccionario de métricas |
| `docente_effectiveness` | Dominio | Backend `routes/analytics/docentes` | Consulta | Sí | Nombre/definición ambiguos | Definir en diccionario |
| Efectividad de intervención | Dominio | Backend `effectiveness.py` + snapshots | `models/intervention.py` | Sí | Falta tablero que la explote | Exponer en dashboard |
| Sesiones / activos / funnel / retención | Uso | — | — | N/A | **NO ENCONTRADO** (sin telemetría) | Instrumentar eventos (§4) |
| "3.040+ estudiantes" | Impacto | Texto en tarjeta Labs | **NO ENCONTRADO** | No | Sin fuente canónica; deriva de dominio | Endpoint canónico de impacto |
| "25 programas" | Impacto | Texto en tarjeta Labs | **NO ENCONTRADO** | No | idem | idem |
| "125 endpoints / 772 tests / 16+ modelos" | Impacto (capacidad) | README/ficha | Conteo manual | No | Hardcodeado y desincronizado (330+ vs 772) | Generar en CI o retirar de copy |

### Recomendación

- **Instrumentar (uso):** capa de eventos pseudonimizada con el set mínimo del §4 — es lo único que hoy falta por completo y desbloquea adopción/funnel/retención.
- **Mover/blindar (dominio):** el dominio ya vive en backend; falta **versionar modelos** (reproducibilidad de `prob_*`), **resolver SHAP**, verificar que exportes no recomputan, y **reemplazar las cifras de impacto en texto por lecturas de una fuente canónica**.

### Ficha de estandarización de métricas de ESTE repo (Core)

- **Telemetría de uso:** **NO ENCONTRADO** (sin GA/PostHog/Sentry/eventos). *Brecha prioritaria.*
- **Indicadores de dominio:** en backend (`routes/analytics/*`, `ml/*`); consultas recalculables; ML **sin versionado** y XAI en *fallback* (no SHAP) → reproducibilidad parcial.
- **Cifras de impacto:** "3.040+ estudiantes / 25 programas" **sin fuente canónica** (solo tarjeta Labs); conteos de ingeniería hardcodeados y desincronizados.
- **Fuente de verdad:** features del ETL + modelos `.pkl` por carrera (dominio); impacto sin fuente fijada.
- **Formato:** `es_EC` (punto de miles) en marca; probabilidades ML sin formato canónico compartido.
- **Diccionario de métricas:** parcial (`docs/DATA_DICTIONARY.md`); sin definición versionada de métricas (fórmula/dueño/fuente).
- **Auditabilidad:** consultas de analítica ✅ recalculables; probabilidades ML ⚠️ no reproducibles sin fijar versión de modelo.
- **Sensibilidad:** las features derivan de PII bajo LOPDP (incl. dato sensible étnico) → la telemetría de uso debe nacer pseudonimizada.

---

*Método: evidencia de los dos documentos técnicos de Core (nivel archivo:línea), la reconciliación §13 de la Arquitectura de Marca v2.0 y la meta en vivo de `yachaydeep.com/core`. Repo privado y render de la SPA fuera de alcance; los ítems sin origen rastreable se marcan NO ENCONTRADO en lugar de inferirse.*
