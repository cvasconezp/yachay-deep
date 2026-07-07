# Referencia de API

**Yachay Deep — Sistema de Alerta Temprana Académica**

Versión 2.0 · Mayo 2026

---

## 1. Información General

**Base URL:** `https://<dominio>/api`
**Framework:** FastAPI (Python 3.11)
**Autenticación:** JWT en cookies `HttpOnly` + `Secure` + `SameSite=Lax`
**Formato:** JSON (request y response)

Todos los endpoints autenticados requieren una cookie `access_token` válida. Los endpoints públicos se indican explícitamente.

### Roles del sistema

| Rol | Código |
|---|---|
| Administrador | `admin` |
| Coordinador | `coordinador` |
| Docente | `docente` |
| Monitor | `monitor` |

---

## 2. Autenticación (`/api/auth`)

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `POST` | `/auth/login` | Iniciar sesión (retorna JWT en cookie) | Público |
| `POST` | `/auth/logout` | Cerrar sesión (invalida cookie) | Autenticado |
| `GET` | `/auth/me` | Obtener perfil del usuario actual | Autenticado |
| `POST` | `/auth/users` | Crear usuario | Admin |
| `GET` | `/auth/users` | Listar usuarios | Admin |
| `PATCH` | `/auth/users/{user_id}` | Actualizar usuario | Admin |
| `POST` | `/auth/set-pin` | Configurar PIN de bloqueo (6 dígitos) | Autenticado |
| `POST` | `/auth/verify-pin` | Verificar PIN de desbloqueo | Autenticado |
| `DELETE` | `/auth/pin` | Eliminar PIN configurado | Autenticado |

**Rate limiting:** `/auth/login` y `/auth/verify-pin` están limitados a 5 intentos por minuto por IP.

---

## 3. Estudiantes (`/api/students`)

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `GET` | `/students/search` | Buscar estudiantes (paginado, filtrable) | Autenticado |
| `GET` | `/students/{student_id}/ficha` | Ficha completa del estudiante (vista 360°) | Autenticado |
| `GET` | `/students/{student_id}/tendencias` | Tendencias históricas del estudiante | Autenticado |
| `GET` | `/students/{student_id}/comparativa` | Comparativa con pares del mismo grupo | Autenticado |
| `GET` | `/students/{student_id}/recovery-score` | Puntaje de recuperación individual | Autenticado |
| `POST` | `/students/recovery-scores/batch` | Puntajes de recuperación en lote | Autenticado |

**Filtros de búsqueda** (`/search`): `carrera`, `sede`, `periodo`, `nivel_riesgo`, `q` (texto libre), `page`, `page_size`.

**Aislamiento de datos:** Un docente solo ve estudiantes de sus cursos; un coordinador solo los de su carrera/sede.

---

## 4. Dashboard (`/api/dashboard`)

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `GET` | `/dashboard/risk` | Lista de estudiantes por nivel de riesgo | Autenticado |
| `GET` | `/dashboard/risk/{student_id}/inactividad` | Detalle de inactividad por curso | Autenticado |
| `GET` | `/dashboard/stats` | KPIs globales del período activo | Autenticado |
| `GET` | `/dashboard/carreras` | Distribución de riesgo por carrera | Autenticado |
| `GET` | `/dashboard/asignaturas` | Indicadores por asignatura | Autenticado |
| `GET` | `/dashboard/docentes/calificacion` | Resumen de calificación por docente | Autenticado |

---

## 5. Intervenciones (`/api/interventions`)

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `POST` | `/interventions/` | Registrar nueva intervención | Autenticado |
| `POST` | `/interventions/bulk` | Crear intervenciones masivas | Autenticado |
| `PATCH` | `/interventions/{intervention_id}` | Actualizar intervención existente | Autenticado |
| `DELETE` | `/interventions/{intervention_id}` | Eliminar intervención | Autenticado |
| `GET` | `/interventions/` | Listar intervenciones (filtrable) | Autenticado |
| `GET` | `/interventions/stats` | Estadísticas de intervenciones | Autenticado |
| `GET` | `/interventions/dashboard` | Panel resumen de intervenciones | Autenticado |
| `GET` | `/interventions/{intervention_id}/impact` | Medición de impacto (antes/después) | Autenticado |

**Snapshot automático:** Al crear una intervención se captura el estado actual del estudiante (compromiso, días sin acceso, tareas, predicciones ML) para medir impacto posterior.

---

## 6. Alertas (`/api/alerts`)

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `GET` | `/alerts/pending` | Alertas pendientes (no leídas) | Autenticado |
| `GET` | `/alerts/count` | Conteo de alertas no leídas | Autenticado |
| `PATCH` | `/alerts/{alert_id}/read` | Marcar alerta como leída | Autenticado |
| `POST` | `/alerts/generate` | Generar alertas automáticas | Admin |
| `POST` | `/alerts/digest/send` | Enviar digest de alertas | Admin |
| `GET` | `/alerts/digest/preview` | Vista previa del digest | Admin |
| `GET` | `/alerts/debug/conditions` | Condiciones de generación (debug) | Admin |
| `GET` | `/alerts/student-tasks-detail/{student_id}` | Detalle de tareas del estudiante | Autenticado |

---

## 7. Predicciones ML (`/api/predictions`)

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `POST` | `/predictions/train` | Entrenar modelos ML | Admin |
| `POST` | `/predictions/run` | Ejecutar predicciones sobre estudiantes activos | Admin |
| `GET` | `/predictions/task-status` | Estado de tarea async de ML | Admin |
| `GET` | `/predictions/status` | Estado general de modelos entrenados | Admin |
| `GET` | `/predictions/student/{student_id}` | Predicciones de un estudiante (deserción + reprobación) | Autenticado |
| `GET` | `/predictions/student/{student_id}/recommendations` | Recomendaciones automáticas (10 categorías) | Autenticado |
| `GET` | `/predictions/student/{student_id}/counterfactual` | Escenarios contrafactuales | Autenticado |
| `POST` | `/predictions/student/{student_id}/what-if` | Simulación "qué pasaría si" personalizada | Autenticado |
| `POST` | `/predictions/notify-tutoria` | Notificar convocatoria a tutoría | Autenticado |

---

## 8. ML Avanzado (`/api/ml`)

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `POST` | `/ml/adaptive/train` | Entrenar modelo adaptativo | Admin |
| `GET` | `/ml/adaptive/status` | Estado del modelo adaptativo | Admin |
| `GET` | `/ml/adaptive/predict/{student_id}` | Predicción adaptativa individual | Autenticado |
| `GET` | `/ml/explain/{student_id}` | Explicabilidad XAI (contribuciones por feature) | Autenticado |
| `POST` | `/ml/clustering/run` | Ejecutar clustering de estudiantes | Admin |
| `GET` | `/ml/clustering/status` | Estado del clustering | Admin |

---

## 9. Workflow de Intervenciones (`/api/workflow`)

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `GET` | `/workflow/states` | Estados posibles del workflow | Autenticado |
| `PATCH` | `/workflow/interventions/{intervention_id}/transition` | Transicionar estado de intervención | Autenticado |
| `POST` | `/workflow/interventions/{intervention_id}/assign` | Asignar responsable | Autenticado |
| `POST` | `/workflow/auto-assign` | Asignación automática por carga | Admin |
| `GET` | `/workflow/carga` | Carga de trabajo por monitor | Autenticado |
| `POST` | `/workflow/check-sla` | Verificar SLAs vencidos | Admin |
| `GET` | `/workflow/interventions/{intervention_id}/logs` | Historial de cambios de la intervención | Autenticado |
| `GET` | `/workflow/overdue` | Intervenciones vencidas (overdue) | Autenticado |

**Estados del workflow:** `pendiente` → `en_progreso` → `contactado` → `resuelto` / `escalado` / `cerrado`.

---

## 10. Cola de Trabajo (`/api/workqueue`)

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `GET` | `/workqueue` | Cola de trabajo priorizada del usuario actual | Autenticado |

---

## 11. Cursos y Semestres (`/api/courses`)

### Configuración de cursos

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `GET` | `/courses/` | Listar configuraciones de cursos | Autenticado |
| `POST` | `/courses/` | Crear configuración de curso | Admin |
| `POST` | `/courses/bulk` | Crear cursos en lote | Admin |
| `PATCH` | `/courses/{course_id}` | Actualizar curso | Admin |
| `DELETE` | `/courses/{course_id}` | Eliminar configuración | Admin |
| `GET` | `/courses/duplicates` | Detectar cursos duplicados | Admin |
| `POST` | `/courses/deduplicate` | Deduplicar cursos | Admin |

### Configuración de semestre

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `GET` | `/courses/semester/active` | Obtener semestre activo | Autenticado |
| `GET` | `/courses/semester/all` | Listar todos los semestres | Autenticado |
| `POST` | `/courses/semester/` | Crear semestre | Admin |
| `POST` | `/courses/semester/{semestre}/activate` | Activar semestre | Admin |
| `POST` | `/courses/semester/{semestre}/bloque` | Cambiar bloque activo | Admin |
| `PATCH` | `/courses/semester/{semestre}` | Actualizar configuración de semestre | Admin |
| `DELETE` | `/courses/semester/{semestre}` | Eliminar semestre | Admin |
| `POST` | `/courses/semester/deactivate-all` | Desactivar todos los semestres | Admin |
| `GET` | `/courses/semester/{semestre}/status` | Estado detallado del semestre | Autenticado |

---

## 12. Exportación (`/api/export`)

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `GET` | `/export/columnas-disponibles` | Columnas disponibles para exportación de estudiantes | Coordinador+ |
| `GET` | `/export/estudiantes/excel` | Exportar estudiantes a Excel (.xlsx) | Coordinador+ |
| `GET` | `/export/intervenciones/columnas-disponibles` | Columnas disponibles para intervenciones | Coordinador+ |
| `GET` | `/export/intervenciones/excel` | Exportar intervenciones a Excel | Coordinador+ |
| `GET` | `/export/ficha/{student_id}/pdf` | Ficha del estudiante en PDF | Coordinador+ |

---

## 13. Administración (`/api/admin`)

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `POST` | `/admin/etl/run` | Ejecutar pipeline ETL | Admin |
| `GET` | `/admin/etl/runs` | Historial de ejecuciones ETL (paginado) | Admin |
| `GET` | `/admin/etl/runs/{run_id}/log` | Log detallado de una ejecución | Admin |
| `POST` | `/admin/etl/upload-historico` | Subir datos históricos (TableauHistórico) | Admin |
| `POST` | `/admin/etl/upload-and-run` | Subir reporte institucional y ejecutar ETL | Admin |
| `POST` | `/admin/etl/upload-practicas` | Subir datos de prácticas preprofesionales | Admin |
| `POST` | `/admin/etl/trigger-scraping` | Disparar scraping Moodle | Admin |
| `GET` | `/admin/etl/scraping-progress` | Progreso del scraping en curso | Admin |
| `GET` | `/admin/system/status` | Estado del sistema | Admin |
| `GET` | `/admin/system/network-check` | Verificar conectividad de red | Admin |
| `PUT` | `/admin/system/avac-cookie` | Actualizar cookie Moodle (SSO) | Admin |
| `GET` | `/admin/system/avac-cookie` | Obtener estado de cookie Moodle | Admin |
| `POST` | `/admin/students/deduplicate` | Deduplicar estudiantes | Admin |
| `GET` | `/admin/debug/student-avac/{student_id}` | Debug: datos Moodle de un estudiante | Admin |
| `GET` | `/admin/debug/student-search` | Debug: búsqueda avanzada de estudiantes | Admin |
| `GET` | `/admin/debug/bloque-filter/{student_id}` | Debug: filtro de bloque activo | Admin |
| `GET` | `/admin/debug/task-submissions/{codigo_curso}` | Debug: entregas de tareas por curso | Admin |

---

## 14. Instituciones (`/api/institutions`)

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `GET` | `/institutions` | Listar instituciones | Admin |
| `POST` | `/institutions` | Crear institución | Admin |
| `PATCH` | `/institutions/{institution_id}` | Actualizar institución | Admin |
| `GET` | `/institutions/{institution_id}` | Detalle de institución | Admin |

---

## 15. Analítica (`/api/analytics/...`)

### Asignaturas

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `GET` | `/analytics/asignaturas` | Métricas por asignatura (notas, compromiso, entregas) | Autenticado |
| `GET` | `/analytics/asignaturas/{asignatura}/detalle` | Detalle de una asignatura específica | Autenticado |

### Docentes

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `GET` | `/analytics/docentes` | Métricas por docente | Coordinador+ |
| `GET` | `/analytics/docentes/{docente_nombre}/detalle` | Detalle de un docente | Coordinador+ |

### Seguimiento docente

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `GET` | `/analytics/docente-tracking` | Tracking de actividad docente | Coordinador+ |
| `GET` | `/analytics/docente-tracking/resumen` | Resumen general de tracking | Coordinador+ |
| `GET` | `/analytics/docente-tracking/{docente_name}` | Tracking individual de un docente | Coordinador+ |

### Tutorías

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `GET` | `/analytics/tutorias/por-asignatura` | Convocatoria de tutorías por asignatura | Autenticado |

### Resumen institucional

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `GET` | `/analytics/periodos` | Listar períodos disponibles | Autenticado |
| `GET` | `/analytics/resumen` | Resumen de indicadores institucionales | Coordinador+ |
| `GET` | `/analytics/resumen/estudiantes-listado` | Listado detallado de estudiantes para resumen | Coordinador+ |
| `GET` | `/analytics/comparativa` | Comparativa entre períodos | Coordinador+ |

### Entregas pendientes

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `GET` | `/analytics/entregas-pendientes` | Entregas pendientes por curso | Autenticado |
| `GET` | `/analytics/entregas-resumen` | Resumen de entregas | Autenticado |

### Vista ejecutiva

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `GET` | `/analytics/executive` | KPIs de alto nivel para directivos | Admin |

### Analítica histórica

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `GET` | `/analytics/historical/asignaturas` | Rendimiento histórico por asignatura | Coordinador+ |
| `GET` | `/analytics/historical/abandono-asignaturas` | Tasas históricas de abandono | Coordinador+ |

### Efectividad de intervenciones

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `GET` | `/analytics/effectiveness` | Efectividad general de intervenciones | Coordinador+ |

### Efectividad docente

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `GET` | `/analytics/docente-effectiveness` | Efectividad por docente | Coordinador+ |

### Terceras matrículas

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `GET` | `/analytics/terceras-matriculas` | Lista de estudiantes en tercera matrícula | Autenticado |
| `GET` | `/analytics/terceras-matriculas/resumen` | Resumen de terceras matrículas | Autenticado |

### Reporte mensual

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `GET` | `/analytics/monthly-report` | Reporte mensual consolidado | Coordinador+ |

### Prácticas preprofesionales

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| `GET` | `/analytics/practicas-resumen` | Resumen de prácticas preprofesionales | Autenticado |

---

## 16. Resumen de Endpoints

| Módulo | Prefijo | Endpoints | Acceso principal |
|---|---|---|---|
| Autenticación | `/auth` | 9 | Público / Admin |
| Estudiantes | `/students` | 6 | Autenticado |
| Dashboard | `/dashboard` | 6 | Autenticado |
| Intervenciones | `/interventions` | 8 | Autenticado |
| Alertas | `/alerts` | 8 | Autenticado / Admin |
| Predicciones | `/predictions` | 9 | Admin / Autenticado |
| ML Avanzado | `/ml` | 6 | Admin / Autenticado |
| Workflow | `/workflow` | 8 | Autenticado / Admin |
| Cola de trabajo | `/workqueue` | 1 | Autenticado |
| Cursos/Semestres | `/courses` | 16 | Admin / Autenticado |
| Exportación | `/export` | 5 | Coordinador+ |
| Administración | `/admin` | 17 | Admin |
| Instituciones | `/institutions` | 4 | Admin |
| Analítica | `/analytics` | 22 | Autenticado / Coordinador+ |
| **Total** | | **125** | |

---

## 17. Códigos de Respuesta

| Código | Significado |
|---|---|
| `200` | Operación exitosa |
| `201` | Recurso creado |
| `400` | Request inválido (validación Pydantic) |
| `401` | No autenticado (token faltante o expirado) |
| `403` | Sin permisos para este recurso |
| `404` | Recurso no encontrado |
| `429` | Rate limit excedido (login/PIN) |
| `500` | Error interno del servidor |

**Formato de error estándar:**

```json
{
  "detail": "Descripción del error"
}
```

---

## 18. Notas Técnicas

**Paginación:** Los endpoints de listado usan parámetros `page` (default 1) y `page_size` (default 20, máx. 100). La respuesta incluye `total`, `page`, `page_size` y `items`.

**Filtrado contextual:** Los datos se filtran automáticamente según el rol del usuario. Un docente nunca recibe datos de estudiantes fuera de sus cursos.

**Tareas asíncronas:** Los entrenamientos ML y el ETL se ejecutan en background tasks de FastAPI. El estado se consulta vía polling (`/predictions/task-status`, `/admin/etl/runs`).

**Validación:** Todos los inputs se validan con esquemas Pydantic antes de procesarse. Los campos de texto se sanitizan para prevenir inyección.

---

*Documento interno — Yachay Deep*
