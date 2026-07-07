# Diccionario de Datos

**Yachay Deep — Sistema de Alerta Temprana Académica**

Versión 2.0 · Mayo 2026

---

## 1. Visión General

La base de datos PostgreSQL 15 contiene 18 modelos organizados en tres dominios: académico, operativo, y ML/prácticas. Todas las tablas usan SQLAlchemy ORM y se crean automáticamente al iniciar el backend.

---

## 2. Dominio Académico

### 2.1 `students` — Estudiantes

Entidad central del sistema. Cada estudiante tiene indicadores de riesgo calculados por el ETL.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer PK | ID interno autoincremental |
| `cedula` | String UNIQUE | Cédula de identidad |
| `nombre` | String | Nombre completo (normalizado a MAYÚSCULAS) |
| `correo` | String | Correo personal |
| `correo_institucional` | String | Correo institucional (.edu.ec) |
| `telefono` | String | Teléfono de contacto |
| `whatsapp` | String | Número de WhatsApp |
| `carrera` | String | Carrera matriculada |
| `sede` | String | Centro de apoyo (votación mayoritaria de DatosEspecificos) |
| `campus` | String | Campus universitario |
| `nivel_academico` | Integer | Semestre actual (1–8) |
| `nivel_riesgo` | String | Alto / Medio / Bajo (calculado por ETL) |
| `indice_compromiso` | Float | 0.0–1.0 (acceso 30% + tareas 30% + rendimiento 25% + admin 15%) |
| `dias_sin_acceso` | Integer | Días desde último acceso a Moodle |
| `porcentaje_tareas` | Float | % de tareas entregadas |
| `promedio_calificaciones` | Float | Promedio de notas finales |
| `pais` | String | País de domicilio |
| `provincia` | String | Provincia |
| `ciudad` | String | Ciudad / cantón |
| `parroquia` | String | Parroquia |
| `barrio` | String | Barrio o comunidad |
| `fecha_nacimiento` | Date | Fecha de nacimiento |
| `genero` | String | Género |
| `autoidentificacion_etnica` | String | Autoidentificación étnica |
| `grupo` | String | Grupo académico (del reporte institucional) |
| `prob_desercion` | Float | 0.0–1.0 (predicción ML) |
| `prob_reprobacion` | Float | 0.0–1.0 (predicción ML) |
| `prediccion_updated_at` | DateTime | Última actualización de predicciones |
| `es_tercera_matricula` | Boolean | Oyente condicionado |
| `score_recuperabilidad` | Float | 0–100 (probabilidad de recuperación) |
| `nivel_recuperabilidad` | String | alto / medio / bajo |
| `periodo` | String | Período académico actual (ej: "2026-1") |
| `estado_matricula` | String | Estado de matrícula |
| `institution_id` | Integer FK | Institución (multi-tenancy) |
| `updated_at` | DateTime | Última actualización |

**Índices:** `idx_student_risk_level` (nivel_riesgo), `idx_student_carrera_riesgo` (carrera + nivel_riesgo)

**Relaciones:** → MoodleAccess, TaskSubmission, Grade, Intervention, Enrollment, PracticaPreprofesional

---

### 2.2 `enrollments` — Matrículas por asignatura

Cada fila = un estudiante × una asignatura matriculada (del reporte institucional Excel).

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer PK | |
| `student_id` | Integer FK → students | |
| `codigo_grupo` | String | Código Moodle del grupo (ej: 408364) |
| `codigo_asignatura` | String | Código de asignatura (ej: C-HU-201) |
| `asignatura` | String | Nombre de la asignatura |
| `tipo_asignatura` | String | COMUN / GENERICA / ESPECIFICA |
| `carrera` | String | Carrera |
| `nivel` | Integer | Nivel académico (1–8) |
| `nombre_grupo` | String | Nombre completo del grupo |
| `bloque` | Integer | Bloque académico (1 o 2) |
| `docente` | String | Nombre del docente |
| `correo_docente` | String | Correo del docente |
| `numero_repitencias` | Integer | Veces que ha cursado la materia |
| `pagado` | String | SI / NO |
| `estado_matriculado` | String | Estado de matrícula |
| `es_tercera_matricula` | Boolean | Tercera matrícula (condicionado) |
| `tipo_aprobacion` | String | CONDICIONADO / None |
| `estado_solicitud` | String | Aprobado / Trámite / No aplica |
| `periodo` | String | Período (ej: "68") |
| `fecha_matricula` | DateTime | Fecha de matrícula |
| `created_at` | DateTime | |

**Índices:** `idx_enrollment_student_periodo`, `idx_enrollment_codigo_grupo`

---

### 2.3 `grades` — Calificaciones

Una fila por estudiante × asignatura × período. Fuente: calificaciones.csv (Moodle scraping) o TableauHistórico (fallback).

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer PK | |
| `student_id` | Integer FK → students | |
| `asignatura` | String | Nombre de la asignatura |
| `carrera` | String | Carrera |
| `grupo` | String | Grupo |
| `docente` | String | Nombre del docente |
| `nota_final` | Float | Nota final (0–100, aprobación ≥ 70) |
| `periodo` | String | Período (ej: "P68") |
| `sede` | String | Sede |
| `numero_repitencias` | Integer | Repitencias en esta materia |
| `nivel` | Integer | Nivel académico (1–8) |
| `created_at` | DateTime | |

**Índices:** `idx_grade_periodo`, `idx_grade_docente`, `idx_grade_student_periodo`, `idx_grade_asig_docente`

---

### 2.4 `moodle_accesses` — Accesos a Moodle

Frecuencia de acceso a la plataforma Moodle por estudiante y curso. Fuente: scraping Selenium.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer PK | |
| `student_id` | Integer FK → students | |
| `codigo_curso` | String | Código Moodle del curso |
| `periodo` | String | Período ("P67", "P68") |
| `snapshot_date` | Date | Fecha del snapshot ETL (para tendencias históricas) |
| `nombre_estudiante_moodle` | String | Nombre tal como aparece en Moodle |
| `ultimo_acceso_texto` | String | Texto original ("8 días 17 horas") |
| `dias_sin_acceso` | Float | Valor numérico parseado |
| `estado_moodle` | String | "Activo" / etc. |
| `fecha_extraccion` | DateTime | Cuándo se extrajo el dato |
| `created_at` | DateTime | |

**Índices:** `idx_moodle_periodo`, `idx_moodle_student_periodo`, `idx_moodle_snapshot`, `idx_moodle_student_snapshot`

---

### 2.5 `task_submissions` — Entregas de tareas

Estado de entrega y calificación de tareas por estudiante y curso. Fuente: scraping de Moodle.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer PK | |
| `student_id` | Integer FK → students | |
| `codigo_curso` | String | Código Moodle |
| `periodo` | String | Período |
| `snapshot_date` | Date | Fecha del snapshot |
| `unidad` | String | Unidad académica ("1", "2", "3", "4") |
| `estado` | String | Estado de la tarea |
| `calificacion` | Float | Nota obtenida |
| `calificacion_maxima` | Float | Nota máxima posible |
| `entregada` | Boolean | ¿Fue entregada? |
| `calificada` | Boolean | ¿Fue calificada? |
| `retrasada` | Boolean | ¿Entrega tardía? |
| `fecha_entrega` | DateTime | Fecha de entrega |
| `fecha_calificacion` | DateTime | Fecha de calificación |
| `calificacion_final` | Float | Nota final de la actividad |
| `total_curso` | Float | Total acumulado del curso |
| `total_entregas` | Integer | Total de entregas del curso |
| `total_calificadas` | Integer | Total calificadas del curso |
| `created_at` | DateTime | |

---

### 2.6 `courses` — Cursos

Catálogo de cursos Moodle detectados durante el scraping.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer PK | |
| `codigo_moodle` | String UNIQUE | Código del curso en Moodle |
| `nombre` | String | Nombre del curso |
| `carrera` | String | Carrera |
| `docente` | String | Docente asignado |
| `periodo` | String | Período |
| `grupo` | String | Grupo |
| `updated_at` | DateTime | |

---

### 2.7 `course_configs` — Configuración de cursos por semestre

Gestión dinámica de qué cursos Moodle scrapear cada semestre. Reemplaza listas hardcodeadas.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer PK | |
| `codigo_moodle` | String | Código Moodle del curso |
| `nombre` | String | Nombre en Moodle |
| `asignatura` | String | Nombre normalizado |
| `carrera` | String | Carrera |
| `docente` | String | Docente |
| `correo_docente` | String | Correo del docente |
| `semestre` | String | Semestre (ej: "2026-1") |
| `bloque` | String | "1", "2", o "ambos" |
| `nivel` | Integer | Nivel del plan de estudios (1–8) |
| `grupo` | String | Sección del curso |
| `activo` | Boolean | Si se debe scrapear este semestre |
| `es_especial` | Boolean | Curso sin actividades individuales |
| `notas` | Text | Observaciones del admin |

---

### 2.8 `semester_configs` — Configuración del semestre

Configuración global del semestre activo, fechas de bloques y umbrales académicos.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer PK | |
| `semestre` | String UNIQUE | Ej: "2026-1" |
| `activo` | Boolean | Solo uno activo a la vez |
| `bloque_actual` | String | "1" o "2" |
| `bloque1_inicio/fin` | DateTime | Fechas del bloque 1 |
| `bloque2_inicio/fin` | DateTime | Fechas del bloque 2 |
| `calendario_academico` | String (JSON) | Fechas de entrega y paso de notas |
| `umbral_nota_aprobacion` | Float | Default: 70.0 |
| `umbral_dias_inactividad` | Integer | Default: 14 |
| `umbral_tareas_minimo` | Float | Default: 50.0% |
| `umbral_compromiso_minimo` | Float | Default: 0.4 |
| `auto_alertas` | Boolean | Generar alertas automáticas post-ETL |
| `retrain_cada_n_etl` | Integer | Reentrenar ML cada N ejecuciones ETL |
| `retrain_contador_etl` | Integer | Contador desde último retrain |
| `ultimo_retrain` | DateTime | Fecha del último reentrenamiento |

---

## 3. Dominio Operativo

### 3.1 `users` — Usuarios del sistema

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer PK | |
| `email` | String UNIQUE | Correo de acceso |
| `nombre` | String | Nombre completo |
| `hashed_password` | String | Hash BCrypt de la contraseña |
| `role` | Enum | admin / coordinador / docente / monitor |
| `is_active` | Boolean | Usuario activo |
| `permissions` | JSON | Lista de tabs permitidos (ej: ["dashboard", "alertas"]) |
| `pin_hash` | String | Hash BCrypt del PIN de 6 dígitos (idle lock) |
| `created_at` | DateTime | |
| `last_login` | DateTime | Último login exitoso |

---

### 3.2 `interventions` — Intervenciones

Registro de cada contacto o acción de seguimiento sobre un estudiante.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer PK | |
| `student_id` | Integer FK → students | |
| `monitor_id` | Integer FK → users | Monitor que registró |
| `monitor_nombre` | String | Nombre (denormalizado) |
| `carrera` | String | Carrera del estudiante |
| `medio` | String | WhatsApp / Llamada / Email / Presencial |
| `motivo` | String | Bajo rendimiento / Inactividad / etc. |
| `estado` | String | Activo / SNA / Retirado |
| `asignatura` | String | Asignatura relacionada |
| `docente` | String | Docente relacionado |
| `observacion` | Text | Notas del monitor |
| `periodo` | String | Período (P67, P68) |
| `resultado` | String | Contactado / No contestó / etc. |
| `requiere_seguimiento` | String | "si" / "no" |
| `nota_cierre` | Text | Notas de resolución |
| **Derivaciones** | | |
| `derivar_bienestar` | Boolean | Derivar a bienestar estudiantil |
| `derivar_financiero` | Boolean | Derivar a área financiera |
| `derivar_coordinacion` | Boolean | Derivar a coordinación |
| `derivar_docente` | Boolean | Derivar al docente |
| `tipo_evento_critico` | String | Enfermedad / Pérdida laboral / etc. |
| `reporte_bienestar` | Text | Descripción detallada |
| `reporte_derivacion` | Text | Nota para otras derivaciones |
| `email_enviado` | Boolean | ¿Se envió email al estudiante? |
| **Snapshots (al crear)** | | |
| `snapshot_compromiso` | Float | Índice de compromiso al momento |
| `snapshot_dias_sin_acceso` | Integer | Días sin acceso al momento |
| `snapshot_porcentaje_tareas` | Float | % tareas al momento |
| `snapshot_prob_desercion` | Float | Prob. deserción al momento |
| `snapshot_prob_reprobacion` | Float | Prob. reprobación al momento |
| `snapshot_nivel_riesgo` | String | Nivel de riesgo al momento |
| **Workflow** | | |
| `estado_workflow` | String | pendiente / en_progreso / contactado / resuelto / escalado / sin_respuesta / cerrado |
| `asignado_a` | Integer FK → users | Monitor asignado |
| `fecha_asignacion` | DateTime | |
| `fecha_limite` | DateTime | SLA deadline |
| `fecha_contacto` | DateTime | Cuándo se contactó |
| `fecha_resolucion` | DateTime | Cuándo se resolvió |
| `escalado` | Boolean | ¿Fue escalada? |
| `escalado_a` | String | A quién se escaló |
| `prioridad` | Integer | 1=urgente, 2=normal, 3=baja |
| `overdue` | Boolean | SLA vencido |
| `created_at` | DateTime | |

---

### 3.3 `alert_events` — Alertas automáticas

Eventos generados automáticamente basados en umbrales del semestre activo.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer PK | |
| `student_id` | Integer FK → students | |
| `tipo` | String | inactividad / compromiso_bajo / nota_cero / tareas_bajas / segunda_matricula / tercera_matricula / deterioro_progresivo |
| `codigo_curso` | String | Curso específico (si aplica) |
| `mensaje` | Text | Mensaje descriptivo |
| `severidad` | String | alto / medio / bajo |
| `leido` | Boolean | ¿Fue leída? |
| `leido_por` | String | Usuario que la marcó |
| `leido_at` | DateTime | Cuándo se leyó |
| `created_at` | DateTime | |

---

### 3.4 `institutions` — Instituciones (multi-tenancy)

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer PK | |
| `nombre` | String UNIQUE | Nombre de la institución |
| `codigo` | String UNIQUE | Código corto |
| `logo_url` | String | URL del logo |
| `avac_url` | String | URL del Moodle/Moodle |
| `moodle_api_token` | String | Token API Moodle |
| `activa` | Boolean | Institución activa |
| `umbral_riesgo_alto` | Float | Default: 0.70 |
| `umbral_riesgo_medio` | Float | Default: 0.40 |
| `umbral_dias_critico` | Integer | Default: 14 |
| `umbral_compromiso_bajo` | Float | Default: 0.30 |
| `carreras` | Text (JSON) | Lista de carreras |
| `periodos_activos` | Text (JSON) | Períodos activos |

---

### 3.5 Tablas auxiliares

| Tabla | Descripción |
|---|---|
| `scraping_runs` | Registro de ejecuciones de scraping (fecha, estado, duración, errores) |
| `recommendation_logs` | Log de recomendaciones automáticas generadas por el motor ML |
| `ml_model_stores` | Persistencia de modelos ML en PostgreSQL (sobrevive redeploys de Railway) |
| `system_settings` | Configuraciones key-value del sistema |
| `docente_trackings` | Seguimiento de actividad docente |

---

## 4. Dominio ML y Prácticas

### 4.1 `escuelas_practica` — Catálogo de escuelas (prácticas preprofesionales)

Instituciones educativas donde los estudiantes realizan prácticas. Datos cruzados con el catálogo SEIBE.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer PK | |
| `amie` | String UNIQUE | Código AMIE de la institución |
| `nombre` | String | Nombre de la escuela |
| `zona/provincia/canton/parroquia/direccion` | String | Ubicación geográfica |
| `distrito` | String | Distrito educativo |
| `sistema_educativo` | String | Intercultural bilingüe / Hispana |
| `jurisdiccion` | String | Jurisdicción |
| `nacionalidad` | String | Nacionalidad indígena predominante |
| `lengua_predominante` | String | Lengua predominante |
| `nombre_autoridad/cargo/telefono` | String | Datos de la autoridad |

### 4.2 `practicas_preprofesionales` — Asignaciones de prácticas

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer PK | |
| `student_id` | Integer FK → students | |
| `escuela_id` | Integer FK → escuelas_practica | |
| `nombre_practica` | String | Ej: "Práctica de Modelos Pedagógicos" |
| `nivel_practica` | String | Ej: "4to nivel" |
| `centro_apoyo` | String | Ej: "Cayambe" |
| `en_mineduc` | String | "Sí" / "No" |
| `amie_escuela/nombre_escuela/distrito/...` | String | Datos denormalizados |
| `periodo` | String | Ej: "P68" |
| `timestamp_formulario` | DateTime | Fecha del formulario |

---

## 5. Diagrama de Relaciones

```
Student (1) ──→ (N) Enrollment
Student (1) ──→ (N) Grade
Student (1) ──→ (N) MoodleAccess
Student (1) ──→ (N) TaskSubmission
Student (1) ──→ (N) Intervention
Student (1) ──→ (N) AlertEvent
Student (1) ──→ (N) PracticaPreprofesional

User (1) ──→ (N) Intervention (como monitor)
EscuelaPractica (1) ──→ (N) PracticaPreprofesional

CourseConfig ──→ configuración de scraping por semestre
SemesterConfig ──→ configuración global del período activo
Institution ──→ configuración multi-tenancy
```

---

## 6. Gestión de Períodos

El sistema maneja períodos académicos con formato dual:

| Formato | Ejemplo | Usado en |
|---|---|---|
| `"P68"` | Período 68 | grades, moodle_accesses, task_submissions |
| `"68"` | Período 68 | enrollments (reporte institucional) |
| `"2026-1"` | Semestre | semester_configs, course_configs |

La función `apply_periodo_filter()` busca ambos formatos simultáneamente en las queries.

---

## 7. Índice de Compromiso

Fórmula del `indice_compromiso` (0.0–1.0):

| Componente | Peso | Fuente |
|---|---|---|
| Acceso a Moodle | 30% | moodle_accesses.dias_sin_acceso |
| Entrega de tareas | 30% | task_submissions (% entregadas) |
| Rendimiento académico | 25% | grades.nota_final (promedio) |
| Estado administrativo | 15% | enrollment (pagado, estado) |

Se aplica **decaimiento exponencial por inactividad**: a mayor días sin acceso, el componente de acceso decae exponencialmente hacia 0.

---

## 8. Diccionario de Métricas (estándar de la casa)

*Añadido en `chore/estandar-casa` (punto 6). Cada métrica declara: definición · fórmula · fuente · cadencia · dueño · clase · versión. Clases: **Uso** (telemetría) · **Dominio** (interpretación de datos cargados) · **Impacto** (marca).*

**Definiciones de estado (fijadas):**

- **Estudiante "monitoreado"** = estudiante presente en `students` (cada registro proviene de ingesta real). Base de las cifras de impacto.
- **Estudiante "en riesgo"** = `prob_desercion` **o** `prob_reprobacion` por encima del umbral del modelo de su carrera (umbral configurable; no hardcodear en frontend).
- **Actor "activo" (uso)** ≠ monitoreado. En telemetría, actor con ≥1 evento en la ventana (p. ej. 7 días). Vive en la capa de uso, separado del dominio.

| Nombre | Clase | Definición | Fórmula / cálculo | Fuente (código) | Cadencia | Dueño | Versión |
|---|---|---|---|---|---|---|---|
| `prob_desercion` | Dominio | Probabilidad de deserción en el periodo | Clasificador por carrera (LogReg/RF) sobre features del ETL | `ml/predict.py` + `.pkl` por carrera | Cada predicción; retrain cada N ETLs | ML | 1.0 |
| `prob_reprobacion` | Dominio | Probabilidad de reprobación | Modelo de reprobación por carrera | `ml/predict.py` | Idem | ML | 1.0 |
| `nivel_riesgo` | Dominio | Nivel de riesgo (Alto/Medio/Bajo) | Regla sobre señales + umbrales del `SemesterConfig` | ETL + `ml/recommendations.py` | Post-ETL | ML | 1.0 |
| `indice_compromiso` | Dominio | 0.0–1.0 (acceso 30% + tareas 30% + rendimiento 25% + admin 15%) | Ver §7 | ETL | Post-ETL | Analítica | 1.0 |
| `docente_effectiveness` | Dominio | Efectividad docente por resultados de sus estudiantes | Agregación por docente | `routes/analytics/docentes` | Por consulta | Analítica | 1.0 |
| `efectividad_intervencion` | Dominio | Cambio de riesgo antes/después de intervenir | Δ entre snapshots pre/post | `models/intervention.py`, `services/*` | Al cerrar intervención | Analítica | 1.0 |
| `estudiantes_monitoreados` | Impacto | Estudiantes en la base (ingesta real) | `COUNT(students)` | `routes/metrics.py::/metrics/impact` | Tiempo real (BD) | Producto | 1.0 |
| `programas_activos` | Impacto | Carreras distintas con ≥1 estudiante monitoreado | `COUNT(DISTINCT students.carrera)` | `routes/metrics.py::/metrics/impact` | Tiempo real (BD) | Producto | 1.0 |
| `login`, `dashboard_view`, `ficha360_view`, `alerta_vista`, `recomendacion_vista`, `intervencion_creada`, `intervencion_cerrada`, `export_generado` | Uso | Eventos de telemetría pseudonimizada (actor por HMAC, sin PII) | Inserción en `usage_events` vía `track()` | `services/telemetry.py`, `models/usage_event.py` | Tiempo real por evento | Producto | 1.0 |

**Reglas:**

- **Impacto se lee, no se reescribe:** landings y pitches consumen `/metrics/impact`; prohibido teclear la cifra (la landing ya la lee, ver `Landing.jsx`).
- **Dominio siempre en backend**, recalculable; las `prob_*` deben poder reproducirse fijando la versión del modelo (ver `ml_model_stores` / punto 12 del plan).
- **Uso siempre pseudonimizado** (HMAC), aislado de tablas de dominio, sin PII en `props`.
- **Formato canónico de la casa:** miles con punto, decimales con coma, probabilidades como % con 1 decimal (`es_EC`).

---

*Documento interno — Yachay Deep*
