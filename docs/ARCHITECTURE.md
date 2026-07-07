# Arquitectura del Sistema - Yachay Deep v2.0

> Sistema de Alerta Temprana Academica  
> Ultima actualizacion: Mayo 2026

---

## 1. Vision General

Yachay Deep es un sistema de alerta temprana academica que predice riesgos de desercion y reprobacion estudiantil mediante modelos de Machine Learning. Integra datos institucionales, plataformas LMS y registros academicos para generar alertas accionables, intervenciones de seguimiento y analitica ejecutiva en tiempo real.

---

## 2. Stack Tecnologico

| Capa | Tecnologia | Despliegue |
|------|-----------|------------|
| Frontend | React 18 + Vite + Tailwind CSS | Vercel (CDN global) |
| Backend | FastAPI (Python 3.11) | Railway (Docker) |
| Base de datos | PostgreSQL 15 | Railway (instancia dedicada) |
| Machine Learning | scikit-learn (LogReg / Random Forest) | Integrado en backend |
| Scraping | Selenium + BeautifulSoup | GitHub Actions (cron diario) |
| CI/CD | GitHub Actions | Auto-deploy desde main |

---

## 3. Diagrama de Arquitectura

```
                         ┌─────────────────────────────┐
                         │        USUARIOS              │
                         │  admin / coordinador /       │
                         │  docente / monitor           │
                         └─────────────┬───────────────┘
                                       │ HTTPS
                                       ▼
                         ┌─────────────────────────────┐
                         │     FRONTEND (Vercel)        │
                         │     React 18 + Vite + TW     │
                         │     SPA - CDN Global         │
                         └─────────────┬───────────────┘
                                       │ REST API
                                       │ JWT (HttpOnly Cookie)
                                       ▼
                         ┌─────────────────────────────┐
                         │     BACKEND (Railway)        │
                         │     FastAPI - Python 3.11    │
                         │     Docker Container         │
                         │                              │
                         │  ┌─────────┐ ┌────────────┐ │
                         │  │ Routes  │ │ ML Module  │ │
                         │  │ (49+2)  │ │ sklearn    │ │
                         │  └────┬────┘ └─────┬──────┘ │
                         │       │            │        │
                         │  ┌────┴────────────┴──────┐ │
                         │  │     ETL Pipeline       │ │
                         │  └────────────────────────┘ │
                         └─────────────┬───────────────┘
                                       │ Red privada
                                       ▼
                         ┌─────────────────────────────┐
                         │   PostgreSQL 15 (Railway)    │
                         │   15+ modelos, 3 dominios    │
                         └─────────────────────────────┘

        ┌──────────────────────────────────────────────────┐
        │              FUENTES DE DATOS                     │
        │                                                   │
        │  ┌──────────┐  ┌──────────────┐  ┌────────────┐ │
        │  │  Excel    │  │ Moodle  │  │  CSV       │ │
        │  │  Instit.  │  │ (Selenium)   │  │  Manual    │ │
        │  └─────┬─────┘  └──────┬───────┘  └─────┬──────┘ │
        │        └───────────────┼─────────────────┘        │
        │                        ▼                          │
        │              ETL Pipeline (Backend)                │
        └──────────────────────────────────────────────────┘
```

---

## 4. Modulos del Backend

La API expone **49 endpoints autenticados** y **2 publicos**, organizados en `backend/routes/`:

| Modulo | Archivo | Responsabilidad |
|--------|---------|-----------------|
| Estudiantes | `students.py` (65KB) | CRUD completo, ficha estudiantil, busqueda avanzada |
| Administracion | `admin.py` (42KB) | Gestion de usuarios, ejecucion ETL, configuracion del sistema, endpoints de debug |
| Exportacion | `export.py` (34KB) | Exportacion de datos en CSV, Excel y PDF |
| Intervenciones | `interventions.py` (31KB) | Registro y seguimiento de intervenciones estudiantiles |
| Alertas | `alerts.py` (30KB) | Generacion y gestion de alertas de riesgo |
| Dashboard | `dashboard.py` (25KB) | Agregacion de datos y KPIs para el tablero principal |
| Predicciones | `predictions.py` (15KB) | Predicciones ML y explicaciones XAI |
| Cursos | `courses.py` (14KB) | Gestion de asignaturas |
| Workflow | `workflow.py` (6KB) | Flujo de trabajo para intervenciones |
| Cola de trabajo | `workqueue.py` (6KB) | Cola de tareas para monitores |
| ML Avanzado | `ml_advanced.py` (4KB) | Predicciones avanzadas y contrafactuales |
| Instituciones | `institutions.py` (4KB) | Configuracion multi-tenant institucional |
| Analitica | `analytics/` | Modulo de analitica agregada |

---

## 5. Modulos del Frontend

SPA en React con 16 vistas principales en `frontend/src/pages/`:

| Pagina | Archivo | Funcion |
|--------|---------|---------|
| Ficha Estudiante | `FichaEstudiante.jsx` (118KB) | Ficha detallada del estudiante con historial completo |
| Admin | `Admin.jsx` (99KB) | Panel de administracion del sistema |
| Resumen de Datos | `ResumenDatos.jsx` (82KB) | Analitica y resumen de datos agregados |
| Alertas | `Alertas.jsx` (52KB) | Gestion y visualizacion de alertas |
| Landing | `Landing.jsx` (45KB) | Pagina publica del sistema |
| Intervenciones | `Intervenciones.jsx` (39KB) | Seguimiento de intervenciones |
| Entregas Pendientes | `EntregasPendientes.jsx` (39KB) | Monitoreo de entregas de tareas |
| Seg. Docente | `SeguimientoDocente.jsx` (25KB) | Seguimiento y evaluacion docente |
| Dashboard | `Dashboard.jsx` (22KB) | Tablero principal con KPIs |
| Asignaturas | `Asignaturas.jsx` (22KB) | Analitica por asignatura |
| About | `About.jsx` (21KB) | Informacion del sistema |
| Docentes | `Docentes.jsx` (19KB) | Analitica por docente |
| Ejecutivo | `Ejecutivo.jsx` (13KB) | Resumen ejecutivo para directivos |
| Form Intervencion | `InterventionForm.jsx` (12KB) | Formulario de creacion de intervenciones |
| Tutorias | `Tutorias.jsx` (12KB) | Modulo de tutorias |
| Login | `Login.jsx` (4KB) | Autenticacion |

---

## 6. Esquema de Base de Datos

PostgreSQL 15 con **15+ modelos** organizados en 3 dominios:

```
┌─────────────────────────────────────────────────────────────┐
│                    DOMINIO ACADEMICO                        │
│                                                             │
│  Student ──┐     Course ──── CourseConfig                   │
│            ├── Enrollment                                   │
│            ├── Grade                                        │
│            ├── MoodleAccess                                   │
│            └── TaskSubmission                               │
│                                                             │
│  SemesterConfig (periodo activo y configuracion)            │
├─────────────────────────────────────────────────────────────┤
│                   DOMINIO OPERACIONAL                       │
│                                                             │
│  User (4 roles) ── Institution (multi-tenant)               │
│  Intervention ── AlertEvent                                 │
│  ScrapingRun ── RecommendationLog ── SystemSetting          │
├─────────────────────────────────────────────────────────────┤
│               DOMINIO ML Y PRACTICAS                        │
│                                                             │
│  MLModelStore (modelos serializados)                        │
│  EscuelaPractica ── PracticaPreprofesional                  │
│  DocenteTracking                                            │
└─────────────────────────────────────────────────────────────┘
```

### Gestion de Periodos

El sistema maneja un formato dual de periodos:
- **Formato "P68"**: usado en calificaciones
- **Formato "68"**: usado en matriculas

La funcion `apply_periodo_filter()` normaliza ambos formatos. `SemesterConfig` determina el semestre activo. Al inicio de semestre (sin calificaciones), el sistema aplica fallback a datos de matricula.

---

## 7. Pipeline ETL

Estrategia de **full-refresh por periodo** (delete + insert) para evitar duplicados.

```
Paso  Operacion                          Fuente
────  ─────────────────────────────────  ──────────────────
 1    Leer reporte + datos personales    Excel institucional
 2    Auto-detectar semestre             Metadatos del reporte
 3    Cargar matriculas                  Excel institucional
 4    Leer calificaciones                Excel (con fallback historico)
 5    Calcular indicadores de riesgo     Datos calculados
 6    Upsert estudiantes                 BD
 7    Cargar accesos Moodle + tareas       Selenium (Moodle)
 8    Upsert calificaciones              BD
 9    Calificaciones historicas          BD
10    Deduplicacion                      BD
11    Backfill de carrera en notas       BD
```

### Fuentes de datos

- **Reporte institucional**: archivo Excel con matriculas, calificaciones y datos personales
- **Moodle**: scraping automatizado con Selenium via GitHub Actions (cron diario)
- **Carga manual**: archivos CSV subidos por administradores

---

## 8. Modulo de Machine Learning

### Predicciones

- **Riesgo de desercion**: probabilidad de abandono del estudiante
- **Riesgo de reprobacion**: probabilidad de reprobar asignaturas

### Estrategia de Modelado

- Modelos entrenados **por carrera** (minimo 30 muestras) con **fallback global**
- Compara Logistic Regression vs Random Forest, selecciona el de mejor AUC
- Reentrenamiento bajo demanda via panel de administracion

### Explicabilidad (XAI)

- **Contribuciones por variable**: valores tipo SHAP que indican el peso de cada factor en la prediccion
- **Contrafactuales**: escenarios "que pasaria si" para explorar reducciones de riesgo

### Persistencia de Modelos

- Serializacion con **joblib** en disco
- Respaldo en PostgreSQL (`MLModelStore`) para sobrevivir redeploys de Railway

---

## 9. Infraestructura

### Railway (Backend + BD)

- Contenedor Docker con auto-deploy desde la rama `main`
- Variables de entorno cifradas
- Red privada entre API y base de datos
- Instancia dedicada de PostgreSQL

### Vercel (Frontend)

- CDN global con distribucion automatica
- Auto-deploy desde la rama `main`
- HTTPS automatico via Let's Encrypt

### GitHub Actions (CI/CD + Scraping)

- Workflow de scraping diario (Moodle)
- Pipeline de pruebas automatizadas

---

## 10. Autenticacion y Seguridad

| Mecanismo | Implementacion |
|-----------|---------------|
| Tokens | JWT HS256 en cookies HttpOnly + Secure + SameSite=Lax |
| Passwords | Hash con BCrypt |
| Roles | 4 niveles: `admin`, `coordinador`, `docente`, `monitor` |
| Rate limiting | 5 intentos/min en login y endpoints de PIN |
| Bloqueo por inactividad | PIN de 6 digitos con timeout de 5 minutos |
| Headers de seguridad | CSP, X-Frame-Options, HSTS, X-Content-Type-Options, Referrer-Policy |

---

## 11. Decisiones Arquitectonicas Clave

| Decision | Justificacion |
|----------|--------------|
| **SPA desacoplada + REST API** | Permite despliegue independiente de frontend y backend; escala horizontal del API sin afectar al cliente |
| **Full-refresh ETL (delete + insert)** | Elimina problemas de duplicados y estados inconsistentes; simplifica la logica de carga a cambio de mayor costo por ejecucion |
| **Modelos ML por carrera con fallback global** | Captura patrones especificos de cada carrera sin fallar cuando hay pocas muestras |
| **JWT en HttpOnly cookies** | Protege contra XSS (el token no es accesible via JavaScript); SameSite=Lax mitiga CSRF |
| **Doble persistencia de modelos ML** | joblib para rendimiento en produccion + PostgreSQL para durabilidad ante redeploys |
| **Selenium via GitHub Actions** | Desacopla el scraping del backend; ejecuta en entorno limpio sin consumir recursos del servidor |
| **Formato dual de periodos** | Acomoda las convenciones inconsistentes entre sistemas institucionales sin requerir migracion de datos |
| **Railway + Vercel** | Combina la flexibilidad de Docker (backend) con el rendimiento de CDN global (frontend) a costo operativo minimo |

---

*Yachay Deep v2.0*
