# Módulos Funcionales

**Yachay Deep — Sistema de Alerta Temprana Académica**

Versión 2.0 · Mayo 2026

---

## 1. Visión General

Yachay Deep implementa cinco capas funcionales de Learning Analytics, cada una construida sobre la anterior:

| Capa | Módulos | Estado |
|---|---|---|
| 1. Analítica descriptiva y diagnóstica | Dashboard, Ficha, Asignaturas, Docentes, Tutorías, Resumen | Operativo |
| 2. Analítica predictiva | Predicciones ML (deserción + reprobación) | Operativo |
| 3. Explicabilidad (XAI) | Contribuciones de features, alertas conductuales | Operativo |
| 4. Recomendaciones automáticas | Motor de recomendaciones (10 categorías) | Operativo |
| 5. Intervenciones y ciclo cerrado | Intervenciones con snapshots, medición de impacto | Operativo |

---

## 2. Dashboard Principal

**Página:** `Dashboard.jsx` (22 KB) · **API:** `dashboard.py` (25 KB)
**Acceso:** Todos los roles (filtrado por contexto del usuario)

Panel central con KPIs del semestre activo. Muestra distribución de riesgo por carrera, indicadores globales, y tarjetas dinámicas con métricas clave.

**Funcionalidades:**
- Distribución de estudiantes por nivel de riesgo (alto/medio/bajo)
- Filtros por carrera, sede, período y nivel de riesgo
- Tarjetas de KPI: total estudiantes, promedio de compromiso, tasa de intervención, alertas pendientes
- Exportación a Excel

**Datos:** Agrega indicadores de `students`, `grades`, `interventions` y `alert_events` del período activo.

---

## 3. Ficha del Estudiante

**Página:** `FichaEstudiante.jsx` (118 KB — la más compleja) · **API:** `students.py` (65 KB)
**Acceso:** Todos los roles (según permisos de carrera/asignatura)

Vista 360° de un estudiante individual. Integra 7 fuentes de datos con diagnóstico de riesgo automático.

**Secciones:**
- Datos personales y académicos (cédula, carrera, sede, nivel, grupo)
- Indicadores de riesgo: compromiso, días sin acceso, % tareas, promedio
- Predicciones ML: probabilidad de deserción y reprobación con explicabilidad XAI
- Contrafactuales: escenarios "qué pasaría si" para reducir el riesgo
- Recomendaciones automáticas con prioridad y medio de contacto sugerido
- Calificaciones del período actual y histórico
- Historial de intervenciones con medición de impacto (antes/después)
- Asignaturas matriculadas (enrollments)
- Accesos AVAC y estado de entregas por curso
- Prácticas preprofesionales (si aplica)
- Mapa coroplético de ubicación geográfica

**Diagnóstico de riesgo:** Árbol de decisión que combina `indice_compromiso`, días sin acceso, notas, e historial de intervenciones previas.

---

## 4. Alertas

**Página:** `Alertas.jsx` (52 KB) · **API:** `alerts.py` (30 KB)
**Acceso:** Todos los roles

Sistema de alertas automáticas generadas por umbrales configurables en `SemesterConfig`.

**Tipos de alerta:**

| Tipo | Condición | Severidad |
|---|---|---|
| `inactividad` | Días sin acceso > umbral (default 14) | Alto |
| `compromiso_bajo` | Índice compromiso < umbral (default 0.4) | Medio |
| `nota_cero` | Nota final = 0 en alguna asignatura | Alto |
| `tareas_bajas` | % tareas < umbral (default 50%) | Medio |
| `segunda_matricula` | Estudiante repitiendo una materia | Bajo |
| `tercera_matricula` | Oyente condicionado | Alto |
| `deterioro_progresivo` | Tendencia negativa entre períodos | Medio |

**Funcionalidades:**
- Filtros por tipo, severidad, carrera, estado de lectura
- Marcar como leída (individual o masivo)
- Badge en sidebar con conteo de alertas no leídas del período activo
- Generación automática post-ETL (configurable en `SemesterConfig.auto_alertas`)

---

## 5. Intervenciones

**Página:** `Intervenciones.jsx` (39 KB) + `InterventionForm.jsx` (12 KB) · **API:** `interventions.py` (31 KB)
**Acceso:** Todos los roles (monitor registra, coordinador/admin gestiona)

Registro y seguimiento de acciones de contacto y acompañamiento a estudiantes en riesgo.

**Campos de registro:**
- Medio de contacto: WhatsApp, Llamada, Email, Presencial
- Motivo: Bajo rendimiento, Inactividad, Solicitud del estudiante, etc.
- Observación, resultado, si requiere seguimiento
- Derivaciones: Bienestar, Financiero, Coordinación, Docente
- Evento crítico: Enfermedad, Pérdida laboral, etc.

**Snapshots:** Al crear una intervención, se captura automáticamente el estado actual del estudiante (compromiso, días sin acceso, tareas, predicciones ML). Esto permite medir el impacto comparando indicadores antes/después.

**Workflow:** pendiente → en_progreso → contactado → resuelto/escalado/cerrado. Con asignación de responsable, fecha límite (SLA), prioridad, y flag de overdue.

---

## 6. Entregas Pendientes

**Página:** `EntregasPendientes.jsx` (39 KB) · **API:** `students.py` (endpoints de tareas)
**Acceso:** Todos los roles

Monitoreo del estado de entregas de tareas por curso, con detalle por unidad académica.

**Funcionalidades:**
- Vista por curso: total entregas, calificadas, pendientes por calificar
- Detalle por estudiante: estado de cada tarea (entregada, calificada, retrasada)
- Detección de frescura de datos (alerta si el scraping no se ha ejecutado recientemente)
- Filtros por período y curso

---

## 7. Analítica de Asignaturas

**Página:** `Asignaturas.jsx` (22 KB) · **API:** `analytics/asignaturas.py`
**Acceso:** Todos los roles

Análisis de rendimiento y riesgo agrupado por asignatura.

**Métricas por asignatura:**
- Promedio de notas, distribución de aprobados/reprobados
- Promedio de compromiso de los estudiantes
- Tasa de entrega de tareas
- Número de intervenciones registradas
- Comparativa con otras asignaturas de la misma carrera

**Datos:** Batch queries optimizadas sobre `grades`, `enrollments`, e `interventions` con índices compuestos.

---

## 8. Analítica Docente

**Página:** `Docentes.jsx` (19 KB) + `SeguimientoDocente.jsx` (25 KB) · **API:** `analytics/docentes.py`
**Acceso:** Coordinador, Admin

Análisis de indicadores agrupados por docente, y seguimiento de actividad docente.

**Métricas por docente:**
- Promedio de notas de sus cursos
- Tasa de reprobación
- Promedio de compromiso de sus estudiantes
- Tiempo de calificación de tareas
- Comparativa con otros docentes de la misma carrera

---

## 9. Tutorías

**Página:** `Tutorias.jsx` (12 KB) · **API:** `analytics/tutorias.py`
**Acceso:** Todos los roles

Generación de listas de convocatoria para tutorías por asignatura, con motivos automáticos.

**Motivos automáticos (4 categorías):**
- Inactividad en AVAC
- Bajo rendimiento (nota < umbral)
- Tareas sin entregar
- Compromiso bajo

Permite generar la lista de estudiantes que deberían ser convocados a tutoría para cada asignatura, con el motivo específico.

---

## 10. Resumen de Datos Institucional

**Página:** `ResumenDatos.jsx` (82 KB) · **API:** `analytics/resumen.py`
**Acceso:** Coordinador, Admin

Vista agregada a nivel institucional con gráficos y comparativa entre períodos.

**Funcionalidades:**
- Distribución de riesgo por carrera (gráficos)
- Comparativa interperíodo: evolución de indicadores
- Selector de período para análisis histórico
- Exportación a Excel

---

## 11. Resumen Ejecutivo

**Página:** `Ejecutivo.jsx` (13 KB) · **API:** `dashboard.py`
**Acceso:** Admin

Vista simplificada para directivos con KPIs de alto nivel y tendencias.

---

## 12. Predicciones ML

**API:** `predictions.py` (15 KB) + `ml_advanced.py` (4 KB) · **Backend ML:** `ml/` (2,503 líneas)
**Acceso:** Admin (entrenamiento), Todos (consulta)

**Pipeline ML:**
1. **Features** (15 variables): académicas (nota promedio, materias reprobadas, repitencias), conductuales (días sin acceso, % tareas, compromiso), curriculares (nivel, número de materias)
2. **Entrenamiento**: LogisticRegression vs RandomForest por carrera (≥30 muestras) + modelo global fallback. Selección por AUC. Datos de períodos P57–P67.
3. **Predicción**: `prob_desercion` y `prob_reprobacion` (0.0–1.0) por estudiante
4. **XAI**: Contribuciones tipo SHAP por feature — explica por qué un estudiante está en riesgo
5. **Contrafactuales**: "¿Qué cambiaría si el estudiante entregara el 80% de tareas?" — escenarios mínimos para reducir riesgo
6. **Recomendaciones**: 10 categorías de acción con prioridad y medio de contacto sugerido
7. **Persistencia**: Modelos guardados en PostgreSQL (tabla `ml_model_stores`) para sobrevivir redeploys

**Auto-reentrenamiento:** Configurable en `SemesterConfig.retrain_cada_n_etl` — reentrenamiento automático cada N ejecuciones del ETL.

---

## 13. Administración

**Página:** `Admin.jsx` (99 KB) · **API:** `admin.py` (43 KB)
**Acceso:** Solo Admin

Panel de administración completo del sistema.

**Secciones:**
- **Usuarios**: CRUD de usuarios, asignación de roles y permisos granulares
- **ETL**: Ejecución manual del pipeline, monitoreo de estado, logs
- **Scraping**: Configuración y ejecución de scraping AVAC, estado de últimas ejecuciones
- **Cursos**: Gestión de `course_configs` (qué cursos scrapear por semestre)
- **Semestre**: Configuración de `SemesterConfig` (fechas de bloques, umbrales, auto-alertas)
- **ML**: Entrenamiento manual, estado de modelos, métricas de rendimiento
- **Alertas**: Generación manual de alertas, configuración de umbrales
- **Instituciones**: Configuración multi-tenancy (preparado para múltiples universidades)
- **Debug**: Endpoints de diagnóstico (requieren admin, protegidos desde commit `5de8da9`)
- **Exportación**: Reportes en Excel y PDF

---

## 14. Pipeline ETL

**Backend:** `etl/` (4,046 líneas) · **Ejecución:** Manual (Admin) o automático (GitHub Actions diario)

**Fuentes de datos:**

| Fuente | Formato | Frecuencia |
|---|---|---|
| Reporte institucional | Excel (.xlsx) | Inicio de semestre |
| Scraping AVAC (ingresos) | CSV generado | Diario (L-V) |
| Scraping AVAC (tareas) | CSV generado | Diario (L-V) |
| Calificaciones AVAC | CSV generado | Diario (L-V) |
| TableauHistórico | CSV | Fin de período |
| Formulario prácticas | Google Forms | Ad-hoc |

**Flujo de ejecución (11 pasos):**
1. Lectura de reporte institucional y datos personales
2. Detección y activación automática de semestre
3. Carga de enrollments (asignaturas matriculadas)
4. Lectura de calificaciones (con fallback a TableauHistórico si no hay datos AVAC)
5. Cálculo de indicadores de riesgo (compromiso, días sin acceso, % tareas)
6. Upsert de estudiantes con indicadores actualizados
7. Carga de accesos AVAC y estado de tareas
8. Upsert de calificaciones del semestre actual
9. Upsert de calificaciones históricas
10. Deduplicación de estudiantes (match por nombre normalizado)
11. Backfill de carrera en grades sin carrera

**Estrategia:** Full-refresh por período (delete + insert) para evitar duplicados acumulativos.

---

## 15. Scraping AVAC

**Backend:** `scraping/` (1,158 líneas) · **Ejecución:** GitHub Actions (diario L-V 22:00 UTC)

Extracción automatizada de datos del AVAC (Moodle institucional) usando Selenium + BeautifulSoup.

**Datos extraídos:**
- Ingresos: último acceso por estudiante por curso
- Tareas: estado de entrega, calificación, fechas
- Calificaciones: notas por unidad y nota final

**Autenticación:** SSO Microsoft + MFA TOTP automatizado.

**Post-scraping:** Ejecuta automáticamente el pipeline ETL con los datos frescos.

---

## 16. Exportación

**API:** `export.py` (34 KB)
**Acceso:** Coordinador, Admin

Exportación de datos en múltiples formatos:
- Excel (.xlsx) con formato profesional
- PDF con encabezado institucional
- CSV para análisis externo

Disponible en: Dashboard, Asignaturas, Docentes, Tutorías, Ficha del Estudiante.

---

## 17. Landing y About

**Páginas:** `Landing.jsx` (45 KB) + `About.jsx` (21 KB)
**Acceso:** Público (sin autenticación)

Página de presentación del sistema con información sobre funcionalidades, equipo y tecnología. Diseñada para visitantes y potenciales clientes institucionales.

---

*Documento interno — Yachay Deep / PachaTech*
