# Modelo conceptual: cómo se piensa el riesgo, el compromiso y las métricas de Core

**Documento de diseño.** Explica *por qué* cada métrica está pensada como está,
cómo se combinan para producir el **índice de compromiso** y el **nivel de
riesgo**, y qué queda pendiente. Complementa la referencia técnica
`docs/RIESGO_Y_COMPROMISO.md` (fórmulas exactas) y `docs/DATA_DICTIONARY.md`.

Estado: refleja el código a **2026-09**, ya con la mejora **H1** (respaldo
académico con `total_curso`) implementada.

---

## 1. Filosofía: prevención, no calificación

Core es un **sistema de alerta temprana**, no un cuadro de notas. Su tesis
pedagógica: *la desconexión precede al abandono*. Por eso el modelo pondera más
el **comportamiento (engagement)** que la calificación: un estudiante con buenas
notas pero que dejó de entrar y de entregar es un riesgo latente que las notas
—que llegan tarde— no capturan. Las métricas se diseñan para **priorizar la
acción** (a quién contactar primero), no solo para describir.

Consecuencia esperada (no un error): un estudiante con notas altas pero baja
actividad **puede** salir en riesgo. Lo que sí era un error —y se corrigió (H1)—
es castigar a quien tiene buen desempeño solo porque la *nota final* aún no está
cargada.

---

## 2. Índice de compromiso (0–1): las cuatro dimensiones

El índice es una suma ponderada de cuatro señales continuas. Cada peso es una
decisión de diseño:

| Dimensión | Peso | Qué mide / cómo se piensa |
|---|---:|---|
| **Acceso a AVAC** | 30 % | *Engagement con la plataforma.* Se mide con el **último acceso real** (mínimo de días entre asignaturas), no con la materia más abandonada (ver §4.1). Curva **exponencial decreciente** (`0.30·e^(−d/10)`): entrar hoy vale el máximo; a los ~7 días cae a la mitad; a los 30 casi cero. Un decaimiento suave, no un corte binario. |
| **Actividades** | 30 % | *Cumplimiento.* Proporción de tareas entregadas sobre el total (lineal). Refleja el hábito de trabajo, no solo la nota. |
| **Rendimiento académico** | 25 % | *Desempeño.* Sigmoide centrada en 70 (umbral de aprobación). Usa **`nota_final ?? total_curso`** [H1]: la nota final manda; si aún no existe, el **parcial de AVAC** (`total_curso`) es el proxy. |
| **Administrativo** | 15 % | *Situación de matrícula.* Matriculado suma completo; estado irregular, parcial; sin dato, señal mínima. |

**Datos ausentes = señal, no neutro.** Si falta una dimensión, no se asume "va
bien" (neutral) ni "va pésimo" (0 absoluto): se asigna un valor pequeño y
proporcional. La ausencia de evidencia es, ella misma, una señal de riesgo
latente. (Salvo el caso académico, que ahora tiene el respaldo AVAC.)

**Regla de datos insuficientes.** Con menos de **2** dimensiones con dato real
(no default), el estudiante queda **Sin clasificar** (gris): preferimos no
etiquetar antes que etiquetar con ruido.

---

## 3. Nivel de riesgo: derivación inversa del compromiso

El riesgo **no** se calcula aparte: es la **lectura inversa** del índice
(más compromiso → menos riesgo), en bandas pensadas para **priorizar**:

| Índice | Nivel | Sentido operativo |
|---|---|---|
| ≥ 0.80 | **Sin riesgo** (azul) | Fuera del radar; va bien. |
| ≥ 0.65 | **Bajo** (verde) | Vigilar de lejos. |
| ≥ 0.35 | **Medio** (amarillo) | Atender. |
| < 0.35 | **Alto** (rojo) | Prioridad de intervención. |

**Por qué cuatro niveles y no tres.** Con tres, "Medio" se convertía en cajón de
sastre (~52 % del total): inútil para priorizar. Añadir **"Sin riesgo"** saca del
radar a quien va bien y le devuelve a "Bajo" su sentido de *vigilancia ligera*.

---

## 4. Otras métricas que alimentan Core (y cómo se piensan)

### 4.1 Días sin acceso: dos números, dos propósitos
- **MÍNIMO** (`dias_desde_ultimo_acceso`) = *cuándo pisó AVAC por última vez*. Es
  el dato honesto de engagement con la plataforma → alimenta el **índice**.
- **MÁXIMO** (`dias_sin_acceso`) = *la materia más descuidada*. Es accionable **por
  curso** → alimenta la **alerta por asignatura**, no el índice global.

Hallazgo (n = 5 996): usar el máximo para el índice anulaba el 30 % para casi
todos (con varias materias, siempre hay una descuidada). El máximo prom. era 34.9
días (puntaje 0.009) vs 4.2 del último acceso (0.198): **22×**. El máximo
*condenaba*; el mínimo *discrimina*.

### 4.2 Porcentaje de tareas / actividades
Entregadas / total. Nutre la dimensión de cumplimiento (30 %) y genera alertas de
incumplimiento (`≥ 2` actividades vencidas eleva el riesgo). Se acota por
**bloque activo**: las tareas de un bloque cerrado no cuentan como "no entregadas"
(hundían el % de todos).

### 4.3 Promedio académico: `nota_final ?? total_curso` [H1]
La nota final (archivo de calificaciones) es la verdad definitiva; mientras no
llega, el **parcial de AVAC** (`total_curso`) es el mejor proxy disponible. Misma
regla que usan la Ficha y el módulo Grupos, ahora también en el motor de riesgo.
El promedio de AVAC se calcula **por curso** (deduplicado, no ponderado por nº de
unidades) y se promedia por estudiante.

### 4.4 Estado de matrícula (administrativo)
Señal de riesgo administrativo-financiero: un pago pendiente es una compuerta que
puede derivar en baja. Aporta el 15 % del índice.

### 4.5 Condición especial: repitencia y tercera matrícula
- **2da matrícula (repitente)**: `numero_repitencias > 1`.
- **3ra matrícula (condicionado)**: `es_tercera_matricula = True` → riesgo
  estructural; en la normativa, reprobar implica separación de la carrera →
  seguimiento prioritario. Se exponen como filtros/distintivos (Alertas, Grupos).

### 4.6 Predicciones ML (deserción / reprobación)
Modelos por carrera (LogisticRegression / RandomForest) que estiman
`prob_desercion` y `prob_reprobacion`, con explicabilidad (contribuciones por
feature) y contrafactuales. Son una **capa complementaria** al índice heurístico:
el índice prioriza *hoy*; el ML anticipa *el desenlace*.

### 4.7 Score de recuperabilidad
Estima cuán recuperable es un estudiante en riesgo (0–100) para orientar dónde la
intervención rinde más. Prioriza esfuerzo, no solo detecta.

### 4.8 Alertas e intervenciones (ciclo cerrado)
Los umbrales (inactividad, compromiso, tareas) generan **alertas**; sobre ellas se
registran **intervenciones** con snapshots antes/después para **medir impacto**
(`delta_compromiso`, `delta_prob_desercion`). El registro replica los campos del
historial (fecha, medio, motivo, estado, resultado, seguimiento).

### 4.9 El tiempo y la estructura: bloques y snapshots
- **Bloques**: el semestre son 2 bloques de 8 semanas; el scraping/ETL procesan el
  **bloque activo**. Las materias del bloque cerrado se excluyen de días/tareas
  (para no inflar el riesgo) pero conservan su última foto (para mostrar su nota).
- **Snapshots**: `AvacAccess`/`TaskSubmission` guardan una foto por día. Para
  mostrar datos se usa el **snapshot más reciente por curso** (no el global), así
  las materias del bloque cerrado no desaparecen.

---

## 5. Análisis: ¿paper (génesis) o implementación vigente?

El paper describe **cómo nace Core**: el índice seminal `0.40·A + 0.60·C` (acceso
binario + actividades), con 3 bandas. La implementación vigente es la **v2**: 4
dimensiones continuas (30/30/25/15), 4 niveles, datos ausentes como señal, y ahora
H1. **Para las valoraciones y umbrales operativos, la v2 es superior** y es la que
debe regir el producto:

- El acceso **continuo** conserva información que el binario (≤7 días = 1/0)
  descarta.
- Incorpora **rendimiento** y **administrativo**, dimensiones que el modelo
  seminal ignoraba.
- Trata la **ausencia de datos** de forma explícita (crítico con scraping real).
- Cuatro niveles **priorizan** mejor que tres.

**Decisión implementada:** se mantiene y mejora la v2 (se añadió H1). El paper, al
ser sobre la *génesis*, puede presentar `0.40·A + 0.60·C` como el punto de partida
y **narrar la evolución v1→v2** con su justificación empírica (el hallazgo del
último acceso, el cajón de sastre de "Medio", el sesgo por notas ausentes). Eso es
más honesto y más publicable que declarar una fórmula que el sistema ya no usa.

> Nota de umbrales: tras H1 la distribución de niveles cambiará (más estudiantes
> reciben crédito académico real). Los umbrales 0.80/0.65/0.35 deben
> **re-validarse** con la distribución del próximo ETL y, si hay desenlaces reales
> de fin de período, contra reprobación/deserción (sensibilidad/especificidad).

---

## 6. Pendientes

### P-DISC — Alerta de discrepancia nota final ↔ AVAC (importante)
**Problema:** una asignatura puede tener **88 en AVAC** (`total_curso`) y **0 en
la nota final** por una **baja administrativa**. Ambos datos son correctos, pero
la divergencia suele esconder un **error rectificable** o un trámite pendiente. La
regla `nota_final ?? total_curso` **elige una** y oculta el conflicto.

**Diseño propuesto:**
1. **Conservar ambas** notas por (estudiante, asignatura): la final (`Grade`) y el
   parcial AVAC (`TaskSubmission.total_curso` del snapshot más reciente del curso).
2. **Marcar discrepancia** cuando difieren de forma extrema — p. ej. `|final −
   avac| ≥ 30`, o `final ≤ umbral_reprobación` con `avac ≥ umbral_aprobación`.
3. **Alertar** (nueva señal / badge en Ficha y Grupos, y opcionalmente una alerta
   accionable) para revisar y **rectificar** antes de que llegue el reclamo del
   estudiante.
4. No cambia el índice de riesgo (H1 sigue como está); es una capa de **calidad de
   datos** y anticipación de reclamos.

### Otros pendientes
- **Re-validar umbrales** del índice tras H1 (§5).
- **Mezcla académica por asignatura** (hoy H1 es a nivel de promedio del
  estudiante): usar `nota_final ?? total_curso` materia por materia y luego
  promediar, para el caso mixto (algunas con final, otras solo AVAC).
- **Refinar H2 (bloques)** en el índice del ETL: `recalculo.py` ya excluye cursos
  de bloque cerrado; alinear el mismo criterio en `transformers.py`.

---

## 7. Dónde vive cada cosa (código)

| Concepto | Archivo |
|---|---|
| Fórmula del índice + niveles + H1 | `backend/etl/transformers.py::calcular_indice_compromiso` |
| Cálculo en el ETL (batch) | `backend/etl/transformers.py` (build df_master) y `backend/etl/pipeline.py` |
| Recálculo periódico (BD) | `backend/services/recalculo.py` |
| Umbrales de alertas | `backend/services/alert_generator.py`, `SemesterConfig` |
| Bloques (ventanas, cursos cerrados) | `backend/services/bloques.py` |
| Deterioro / tendencias | `backend/services/deterioro_detector.py` |
| Impacto de intervenciones | `backend/services/intervention_metrics.py` |
| Referencia técnica de fórmulas | `docs/RIESGO_Y_COMPROMISO.md` |

---

*Mantener vivo: si cambia un peso, un umbral o una fuente de datos, actualizar
este documento y `docs/RIESGO_Y_COMPROMISO.md` en el mismo commit.*
