# Guía de Módulos y Hallazgos — Core (Yachay Deep)

**Documento maestro de patrones, convenciones y hallazgos de datos.**

> Propósito: si en el futuro necesitas construir un módulo nuevo que reutilice
> funcionalidad ya existente (KPIs, filtros, tabla pivote, notas de AVAC,
> intervenciones, exportación, etc.), lee esta guía **antes** de ponerte a leer
> todo el código. Aquí está el "cómo lo hicimos y por qué", incluyendo las
> trampas de datos que ya nos costaron tiempo.

Última actualización: 2026-09 (incorpora el módulo **Grupos** y el arreglo de
snapshots por curso de la **Ficha**).

---

## 0. Mapa rápido (TL;DR)

- **Backend analítica** → `backend/routes/analytics/<modulo>.py`, registrado en
  `backend/routes/analytics/__init__.py`. Prefijo `/analytics`.
- **Frontend página** → `frontend/src/pages/<Modulo>.jsx`, ruta en `App.jsx`,
  ítem de sidebar en `components/Layout.jsx`, método en `services/api.js`.
- **Auth** → `get_current_user` (cualquier autenticado) o `require_admin` (solo
  admin) en backend; `PrivateRoute adminOnly` o `tabKey` en frontend.
- **La nota mostrada** = `Grade.nota_final ?? TaskSubmission.total_curso`.
- **La carrera vive en `Student`**, no en `Grade` (filtra carrera vía Student).
- **Semestre vigente**: `Grade.periodo IS NULL`. Históricos: período etiquetado.
- **Bloques**: el semestre tiene 2 bloques; el scraper/ETL solo captura el
  **bloque activo**. Para AVAC usa el **snapshot más reciente por curso**.
- **Deploy**: push a `main` → Railway (backend) + Vercel (frontend). Compila el
  frontend antes. `frontend/dist/` está en `.gitignore` (lo compila Vercel).

---

## 1. Arquitectura general

| Capa | Ubicación | Notas |
|---|---|---|
| API | `backend/` (FastAPI, Python 3.11) | Routers incluidos en `backend/main.py` |
| Analítica | `backend/routes/analytics/*.py` | Un submódulo por vista; router agregado en `__init__.py` |
| Modelos | `backend/models/*.py` | SQLAlchemy; exportados en `models/__init__.py` |
| Frontend | `frontend/src/pages/*.jsx` | React 18 + Vite + Tailwind |
| API client | `frontend/src/services/api.js` | `this.get/post/...`; base `import.meta.env.VITE_API_URL \|\| "/api"` |
| Rutas | `frontend/src/App.jsx` | `PrivateRoute` envuelve cada página |
| Sidebar | `frontend/src/components/Layout.jsx` | `NAV_ITEMS` filtrado por permisos |

Hosting: **Railway** (backend + Postgres, vía `Dockerfile`) y **Vercel**
(frontend). Ambos hacen auto-deploy al hacer push a `main`.

---

## 2. Receta: agregar un módulo de analítica nuevo

### 2.1 Backend

1. Crea `backend/routes/analytics/<modulo>.py`:
   ```python
   from fastapi import APIRouter, Depends
   from sqlalchemy.orm import Session
   from ...database import get_db
   from ...models import Student, Grade, Enrollment   # lo que necesites
   from ...auth.jwt import require_admin               # o get_current_user
   from ...models.user import User
   from ._helpers import apply_periodo_filter, get_umbrales, normalize_riesgo

   router = APIRouter(prefix="/analytics", tags=["analytics"])

   @router.get("/<modulo>", response_model=...)
   def get_<modulo>(periodo=None, carrera=None, nivel=None,
                    db: Session = Depends(get_db),
                    current_user: User = Depends(require_admin)):
       ...
   ```
2. Regístralo en `backend/routes/analytics/__init__.py` (import + `router.include_router(...)`).
   - **Ojo**: en esta versión de FastAPI el `include_router` es *lazy*; las
     rutas no aparecen en `app.routes` hasta que llega un request. Para verificar
     que quedó registrado, usa `TestClient` y confirma que responde **401**
     (no 404) sin token.
3. Reutiliza `_helpers.py` (ver §7) para período, umbrales y riesgo.

### 2.2 Frontend

1. `frontend/src/pages/<Modulo>.jsx` — usa los componentes reutilizables (§5).
2. Método en `services/api.js`:
   ```js
   get<Modulo>Analytics(params = {}) {
     const qs = new URLSearchParams(params).toString();
     return this.get(`/analytics/<modulo>${qs ? "?" + qs : ""}`);
   }
   ```
3. Ruta en `App.jsx`:
   ```jsx
   <Route path="/<modulo>" element={
     <PrivateRoute adminOnly>{/* o tabKey="<modulo>" */}
       <Modulo />
     </PrivateRoute>} />
   ```
4. Ítem de sidebar en `components/Layout.jsx` → array `NAV_ITEMS`
   (`{ path: "/<modulo>", label: "...", icon: "👥" }`).
   - **Ojo permisos**: el sidebar filtra por `user.permissions.includes(tabKey)`
     donde `tabKey = path.replace("/", "")`. Si el módulo es `adminOnly`, basta
     con que el admin tenga `permissions = null` (acceso total). Si quieres que
     otros roles lo vean, añade el `tabKey` a `ROLE_PRESETS` en
     `hooks/useAuth.jsx` **y** `pages/Admin.jsx` (deben coincidir).

### 2.3 Orden de trabajo recomendado
Backend + endpoint probado (con datos sintéticos vía `TestClient`) → frontend →
`npm run build` para verificar que compila → push.

---

## 3. Modelo de datos: qué vive dónde (¡crítico!)

| Dato | Fuente confiable | Notas / trampas |
|---|---|---|
| Nombre, cédula, carrera, nivel académico, grupo (paralelo), nivel de riesgo, tercera matrícula | **`Student`** | `Student.carrera` es la fuente del desplegable de carreras. `Student.grupo` = paralelo. `Student.nivel_academico` = nivel del estudiante. |
| Nota final de asignatura | **`Grade.nota_final`** | `Grade.carrera` y `Grade.nivel` **suelen venir NULL/incompletos** — no filtres por ellos. Semestre vigente = `periodo IS NULL`. |
| Materias matriculadas (roster + nivel + carrera + docente + grupo por sección) | **`Enrollment`** | `Enrollment.periodo` viene como `"68"` (sin la "P"). `Enrollment.codigo_grupo` = ID del aula AVAC. Tiene `nivel`, `bloque`, `numero_repitencias`, `es_tercera_matricula`. |
| Nota parcial de AVAC ("Total del Curso") y actividad de tareas | **`TaskSubmission`** | `total_curso` es la nota del AVAC. Enlaza con la matrícula por `TaskSubmission.codigo_curso == Enrollment.codigo_grupo`. Tiene `snapshot_date` (histórico). |
| Acceso al aula AVAC (días sin acceso, último acceso) | **`AvacAccess`** | También con `snapshot_date`. |

### 3.1 La carrera vive en `Student`, no en `Grade`
Para filtrar por carrera, resuelve primero los `student_id` de esa carrera y
filtra por ellos:
```python
carrera_sids = [sid for (sid,) in db.query(Student.id).filter(
    func.lower(Student.carrera).contains(carrera.lower())).all()]
q = q.filter(Grade.student_id.in_(carrera_sids))
```
Filtrar por `Grade.carrera`/`Enrollment.carrera` como **texto** es frágil por
tildes/ortografía (p. ej. `"COMUNICACIÓN"` vs `"COMUNICACION"`). Filtrar por
`student_id` evita ese problema.

### 3.2 La nota que se muestra = `Grade.nota_final ?? total_curso`
La Ficha (y ahora Grupos) muestran: si hay **nota final** en `Grade`, esa manda;
si aún no hay (semestre en curso), se usa el **`total_curso` de las tareas AVAC**
(`TaskSubmission`). Cuando llega el archivo de notas finales, la final reemplaza
automáticamente al valor de AVAC. Enlace: `codigo_curso == codigo_grupo`.

### 3.3 Períodos (`apply_periodo_filter`)
- Semestre **vigente**: las calificaciones se guardan con `periodo IS NULL`
  (histórico = período etiquetado, p. ej. `P67`).
- `apply_periodo_filter(query, periodo, column=None, include_null=False)`:
  - `periodo="P68"` matchea `"P68"` y `"68"`; con `include_null=True` **también**
    incluye `NULL` (útil para traer las notas del semestre vigente).
  - `periodo="actual"`/`""` → sobre `Grade` filtra `periodo IS NULL`.
  - Para columnas de `Enrollment`/`TaskSubmission` pasa `column=...`.

### 3.4 Bloques (2 por semestre) — el hallazgo que más confunde
El semestre tiene **Bloque 1 y Bloque 2** (8 semanas c/u). El scraper y el ETL
**solo capturan el bloque activo** (`get_active_codigos` en
`scraping/ingresos_avac.py`, `_get_codigos_for_bloque` en `etl/pipeline.py`,
`services/bloques.py`). Consecuencia:
- Una materia de un bloque ya cerrado deja de rasparse; su última nota/actividad
  AVAC queda en un **snapshot anterior**.
- El estudiante puede tener materias del bloque cerrado sin nota final aún → se
  ven como "Cursando/Sin AVAC" si solo miras el snapshot más reciente global.

### 3.5 Snapshots: usa el más reciente **por curso**, no el global
`AvacAccess` y `TaskSubmission` guardan una foto por día (`snapshot_date`). El
error clásico (que tuvo la Ficha) es filtrar al **último snapshot global**, que
en pleno semestre solo trae el bloque activo. Lo correcto:
```python
# por curso: el snapshot más reciente que tenga datos de ESE curso
latest_by_course = dict(
    db.query(TaskSubmission.codigo_curso, func.max(TaskSubmission.snapshot_date))
      .filter(...).group_by(TaskSubmission.codigo_curso).all())
rows = [t for t in todas if t.snapshot_date == latest_by_course.get(t.codigo_curso)]
# Nota: None == None es True en Python → los cursos con snapshot NULL (legacy)
# se conservan; los que tienen fecha descartan los NULL a favor de la fecha.
```
En Grupos, `_total_curso_map` hace lo equivalente: por `(student, curso)` toma la
mejor nota del snapshot más reciente, incluyendo período NULL.

### 3.6 Nombres de asignatura: normaliza igual que la Ficha
Los nombres del scraping traen **artefactos de Excel** (`_x000d_`), saltos de
línea y difieren en tildes/mayúsculas entre `Enrollment` y `Grade`. Para
emparejar asignatura↔nota usa la misma normalización que la Ficha
(`_normalize_asig` en `routes/students.py`), replicada en
`analytics/grupos.py::_norm_asig`:
1. quita `_xNNNN_`, 2. colapsa saltos/espacios, 3. mayúsculas, 4. quita tildes.
Si no hay match exacto, empareja **por subcadena** (mayor solapamiento), igual
que `_find_canon_key`. Sin esto, notas reales aparecen como "—".

### 3.7 Condición especial y riesgo
- **Condicionado (3ra matrícula)** = `Student.es_tercera_matricula == True`.
- **Repitente (2da matrícula)** = `Enrollment.numero_repitencias > 1`
  (y no tercera). Mismo criterio que el módulo Alertas.
- **Riesgo**: normaliza siempre con `normalize_riesgo(...)` → `"Alto"|"Medio"|"Bajo"`.

---

## 4. Autenticación y permisos

- **Backend**: `Depends(get_current_user)` = cualquier usuario autenticado;
  `Depends(require_admin)` = solo rol admin (`backend/auth/jwt.py`). Endpoints de
  analítica sensibles/administrativos → `require_admin`.
- **Frontend**: `<PrivateRoute adminOnly>` restringe a admin; `tabKey="x"`
  restringe por permiso. El sidebar (`Layout.jsx`) muestra el ítem solo si el
  permiso está presente (admin con `permissions = null` ve todo).
- Presets de permisos por rol: `hooks/useAuth.jsx` y `pages/Admin.jsx`
  (`ROLE_PRESETS`) — mantener sincronizados.

---

## 5. Componentes y patrones de UI reutilizables

| Necesitas | Usa | Dónde |
|---|---|---|
| Selector de período (autoselecciona el vigente) | `PeriodSelector` | `components/PeriodSelector.jsx` |
| Tarjetas KPI de colores | `SummaryCard` / `StatCard` (`color="blue\|red\|yellow\|green"`) | `components/StatCard.jsx` |
| Badge de riesgo / barra de compromiso | `RiskBadge`, `CompromisoBar` | `components/RiskBadge.jsx` |
| Exportar a Excel (con hoja de autoría) | `ExportExcelButton` (`data`, `columns=[{key,label}]`) | `components/ExportExcelButton.jsx` |
| Registrar intervención a varios estudiantes | `BulkInterventionModal` (`selectedStudents=[{id,nombre,carrera}]`, `periodo`, `onClose`, `onSaved`) | `components/BulkInterventionModal.jsx` |
| Lista de carreras para filtros | `api.getCarreras()` → `/dashboard/carreras` (distinct `Student.carrera`) | — |
| Períodos disponibles + default | `api.getPeriodosDisponibles()` → `/analytics/periodos` | — |

### 5.1 Barra de filtros (patrón)
`PeriodSelector` + `<select>` de Carrera/Nivel/... + buscador a la derecha
(`ml-auto`) + contador de resultados. Estilo de `<select>`:
`border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500`.
Los filtros "de servidor" (período/carrera/nivel) recargan; los "de cliente"
(grupo/condición/riesgo/buscador) filtran en memoria sobre la respuesta.

### 5.2 Tabla con **primera columna congelada** + **encabezados fijos**
Contenedor con scroll en ambos ejes y alto máximo; `thead th` sticky arriba y la
primera celda sticky también a la izquierda (esquina con mayor z-index):
```jsx
<div className="overflow-auto max-h-[65vh]">
  <table className="border-collapse">
    <thead>
      <tr>
        <th className="sticky left-0 top-0 z-30 bg-gray-50 ...">Estudiante</th>
        {cols.map(c => <th className="sticky top-0 z-20 bg-gray-50 ...">{c}</th>)}
      </tr>
    </thead>
    <tbody>
      <tr className="group">
        <td className="sticky left-0 z-10 bg-white group-hover:bg-blue-50 ...">nombre</td>
        ...
      </tr>
    </tbody>
  </table>
</div>
```
Reglas: cada `th`/`td` sticky necesita **fondo opaco** propio (`bg-gray-50` /
`bg-white`) o se transparenta al hacer scroll. Esquina superior-izquierda con el
z-index más alto.

### 5.3 Selección de filas + intervención
Set de `student_id` seleccionados, checkbox por fila (con `stopPropagation` para
no navegar), checkbox "seleccionar todos los visibles" en el encabezado, y una
barra que aparece con la selección para abrir `BulkInterventionModal`. Ver
`Grupos.jsx` y `Alertas.jsx` como referencia.

---

## 6. Helpers de analítica (`routes/analytics/_helpers.py`)

- `apply_periodo_filter(query, periodo, column=None, include_null=False)` — ver §3.3.
- `get_umbrales(db)` — umbrales configurables (`nota_aprobacion` = 70 por
  defecto) desde `SemesterConfig`.
- `normalize_riesgo(valor)` → `"Alto"|"Medio"|"Bajo"|None`.
- `build_risk_map(rows)` — cuenta por nivel de riesgo normalizado.

---

## 7. Despliegue

- Push a `main` dispara **Railway** (backend, `Dockerfile`) y **Vercel**
  (frontend). `railway.json` fija el builder Dockerfile.
- **Compila el frontend antes** de desplegar: `cd frontend && npm run build`
  (solo verifica que compila; `frontend/dist/` está en `.gitignore` — lo
  construye Vercel).
- Verifica el estado del despliegue del backend por el commit desplegado en
  Railway. Si el frontend (Vercel) sale antes que el backend (Railway), puede
  haber unos minutos donde la UI nueva llama a un endpoint que aún no existe →
  esperar a que Railway termine.
- Los `404` de `/predictions/student/{id}` y `/counterfactual` son **normales**
  cuando el modelo ML no tiene predicción para ese estudiante; no son errores del
  despliegue.

---

## 8. Checklist para un módulo nuevo

- [ ] Endpoint en `routes/analytics/<modulo>.py` + registrado en `__init__.py`.
- [ ] Auth correcta (`require_admin` o `get_current_user`).
- [ ] Reutiliza `_helpers` (período/umbrales/riesgo) y respeta §3 (Student para
      carrera, nota = `nota_final ?? total_curso`, snapshot por curso, normalizar
      nombres de asignatura).
- [ ] Método en `api.js`, ruta en `App.jsx`, ítem en `Layout.jsx` (+ permisos si
      aplica).
- [ ] UI con componentes reutilizables (§5).
- [ ] Prueba con `TestClient` + datos sintéticos (incluye casos: período NULL,
      tildes/artefactos en nombres, total_curso sin nota final, bloque cerrado).
- [ ] `npm run build` sin errores.
- [ ] Push a `main`; verifica el commit desplegado en Railway.

---

## 9. Bitácora de hallazgos (por qué el código es así)

Registro de los problemas reales que encontramos y cómo se resolvieron — útil
para no repetirlos:

1. **`/analytics/grupos` salía vacío para una carrera** → se filtraba por
   `Grade.carrera` (casi siempre NULL). Fix: filtrar carrera vía `Student` (§3.1).
2. **Carreras con tilde salían vacías** (Comunicación, etc.) → el respaldo de
   matrícula comparaba texto de carrera. Fix: filtrar por `student_id` de la
   carrera, no por texto (§3.1).
3. **La tabla salía sin notas en el semestre vigente** → `Grade` aún no tiene
   finales de P68; las notas están en `TaskSubmission.total_curso`. Fix:
   `nota = nota_final ?? total_curso`, enlazando `codigo_curso = codigo_grupo` (§3.2).
4. **Notas reales aparecían como "—"** → nombres de asignatura con artefactos de
   Excel / tildes distintas entre `Enrollment` y `Grade`. Fix: normalización tipo
   Ficha + match por subcadena (§3.6).
5. **Ficha mostraba "Sin AVAC/Cursando" en materias de bloque cerrado** → filtraba
   al último snapshot global (solo bloque activo). Fix: snapshot más reciente
   **por curso** (§3.5).
6. **Notas del semestre vigente tienen `periodo NULL`** → `apply_periodo_filter`
   con `include_null=True` para traerlas (§3.3).
7. **Bloques**: el scraper/ETL solo procesan el bloque activo; materias de bloque
   cerrado conservan su última nota/actividad en snapshots previos (§3.4).

---

*Mantén esta guía viva: cuando un módulo nuevo descubra otra trampa de datos o
cree un patrón reutilizable, agrégalo aquí.*
