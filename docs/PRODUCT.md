# PRODUCT — Core (Yachay Deep)

**Carta de navegación del producto.** Qué es Core hoy, qué problema resuelve, quién lo usa, cómo funciona y hasta dónde puede llegar. Documento vivo — la fuente de verdad de "qué es este producto".

> **Core** · un producto de Yachay Deep Labs · Badge: **`INSIGNIA`** — *Fase 6 en curso (ver [ROADMAP.md](./ROADMAP.md)).*
> Frente: **Educación (instituciones)** · Sensibilidad de datos: **Alta** (PII de estudiantes + dato sensible étnico, LOPDP Ecuador).

---

## 1. Qué es (en una frase)

Un sistema de **alerta temprana** que detecta a qué estudiantes de educación superior virtual se les está yendo de las manos el semestre, **explica por qué**, y le dice al tutor **qué hacer** — antes de que abandonen.

## 2. El problema y para quién

En programas virtuales, la deserción y la reprobación se detectan tarde, cuando ya se perdió al estudiante. Los monitores y coordinadores no tienen tiempo de revisar la plataforma estudiante por estudiante ni de cruzar accesos, tareas y notas a mano. Core automatiza esa vigilancia: ingiere los datos dispersos del aula virtual, calcula el riesgo, lo prioriza y lo convierte en una lista accionable de a quién contactar y por qué.

**Usuarios:** monitores académicos, coordinadores de carrera, docentes y autoridades. **Comprador:** vicerrectorados académicos / bienestar estudiantil / coordinaciones de carrera de instituciones con oferta virtual.

## 3. El motor de la casa

Core encarna el motor de Yachay Deep en su forma más madura:

> **Ingerir datos desordenados → modelarlos → explicarlos (XAI) → devolverlos legibles y accionables.**

- **Ingerir** — scraping de Moodle/AVAC (Selenium) + uploads Excel/CSV + formularios. Accesos, entregas, calificaciones, demografía.
- **Modelar** — pipeline ETL + modelos ML de deserción/reprobación por carrera.
- **Explicar** — contribuciones por feature (XAI) + contrafactuales ("¿qué cambiaría el resultado?").
- **Accionar** — recomendaciones priorizadas, alertas, e intervenciones de ciclo cerrado con medición de impacto.

## 4. Las 5 capas (alcance actual)

1. **Descriptiva / diagnóstica** — dashboards, ficha 360°, indicadores por carrera, asignatura, docente y tutoría.
2. **Predictiva (ML)** — `prob_desercion` y `prob_reprobacion` por carrera.
3. **Explicabilidad (XAI)** — contribuciones por feature + contrafactuales. *Nota: hoy corre un fallback propio; SHAP real está pendiente de instalar (ver ROADMAP).*
4. **Recomendaciones** — motor con prioridad y medio de contacto.
5. **Intervenciones / ciclo cerrado** — registro, workflow, snapshots antes/después y efectividad.

Ver el detalle técnico en [ARCHITECTURE.md](./ARCHITECTURE.md), [MODULES.md](./MODULES.md) y [API.md](./API.md).

## 5. Métricas del producto

Tres clases, separadas por diseño (ver [DATA_DICTIONARY.md](./DATA_DICTIONARY.md) §8):

- **Dominio** — la interpretación de los datos cargados: riesgo, XAI, efectividad. Es el valor del producto. Vive en backend, recalculable.
- **Uso** — telemetría pseudonimizada (sin PII) de cómo se usa la app. Tabla aislada `usage_events`.
- **Impacto (marca)** — cifra única desde `GET /metrics/impact` (`estudiantes_monitoreados`, `programas_activos`). Las landings **leen** esa cifra; no se teclea.

## 6. Hasta dónde puede llegar

- **Corto:** narrativa automática con LLM sobre las salidas XAI; tablero de impacto de intervenciones explotando los snapshots ya guardados.
- **Medio:** multi-tenant real (Row-Level Security) + onboarding self-service; conectores de ingesta más allá de AVAC (Moodle API estándar, Canvas).
- **Ambicioso:** plataforma regional de *learning analytics* de retención con benchmarking anonimizado entre instituciones.

Detalle y secuencia en [ROADMAP.md](./ROADMAP.md).

## 7. Límite honesto

El motor es de **detección + explicación + acción**, no de **entrega de aprendizaje**. No tiene sentido convertirlo en LMS ni en tutor de contenidos — ahí compite con Moodle/Canvas y pierde. Su foco defendible es la **capa de inteligencia encima del LMS**. Si una institución no tiene datos digitales de interacción (accesos, tareas, notas), el motor no tiene de qué alimentarse.

## 8. Encaje en el portafolio

Core es el **caso de referencia más maduro** del patrón "ingerir → modelar → explicar → accionar" y el producto insignia de Yachay Deep Labs en educación. Comparte stack y módulos reutilizables (cifrado, auth, ETL, seguridad) con los productos hermanos (Kullki, Áncora), a los que sirve de plantilla técnica y de seguridad.

---

*Ver también: [ROADMAP.md](./ROADMAP.md) · [SECURITY.md](./SECURITY.md) · [AUDITS/](./AUDITS/) · [../README.md](../README.md)*
