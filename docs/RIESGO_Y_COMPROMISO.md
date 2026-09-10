# Cálculo de Riesgo y Compromiso en Core — Sistematización

**Documento técnico-metodológico.** Describe cómo Core calcula *actualmente* el
**índice de compromiso** y el **nivel de riesgo**, contrasta con lo declarado en
el paper y resume los **aportes y hallazgos** que el paper puede reivindicar.

Fuente de verdad del código: `backend/etl/transformers.py::calcular_indice_compromiso`
(umbrales y pesos) y el punto de cálculo en `backend/etl/pipeline.py` (~L1495–1527).
Última revisión: 2026-09.

---

## 1. Respuesta corta a "¿por qué casi todos salen en riesgo alto con buenas notas?"

Sí, hoy puede pasar, y se debe a **tres causas combinadas**, no a un error aislado:

1. **El nivel de riesgo se deriva del índice de compromiso, no de las notas.** El
   riesgo es *inverso* al índice: índice bajo → riesgo alto. Las calificaciones
   pesan solo **25 %** del índice; el **60 %** es engagement (acceso AVAC 30 % +
   actividades 30 %) y **15 %** es administrativo.
2. **[CORREGIDO 2026-09 — H1]** El componente académico usaba solo la NOTA FINAL
   (`nota_final`); en el término en curso, al no haber finales, asignaba el
   *default* ≈ **nota 50** a casi todos y sesgaba a "Alto". **Ahora usa
   `nota_final ?? total_curso`**: si no hay nota final, toma el parcial de AVAC
   (`total_curso`) como proxy; cuando llega la final, la reemplaza. Ver §5.
3. **Bloques cerrados sin refresco** inflan la inactividad y el incumplimiento:
   durante un bloque, las materias del otro bloque dejan de rasparse, bajando el
   ratio de actividades y subiendo los días sin acceso → castiga el engagement.

El resultado: la mayoría cae por debajo del umbral y queda "Alto". El
`nivel_riesgo` que muestra Grupos es `Student.nivel_riesgo`, calculado por el
**último ETL** (una foto global), no recomputado en vivo por grupo.

---

## 2. Fórmula vigente (implementada) — modelo ponderado multinivel v2

El índice de compromiso ∈ [0, 1] es la suma de cuatro componentes continuos:

| Componente | Peso | Fórmula (implementada) | Dato de entrada | Default si falta |
|---|---:|---|---|---|
| Acceso AVAC (engagement) | 30 % | `0.30 · e^(−d/10)` | `d` = **días desde el último acceso** (MÍN entre asignaturas) | 0.03 |
| Actividades (cumplimiento) | 30 % | `(entregadas / totales) · 0.30` | tareas AVAC (todas las materias) | 0.05 |
| Rendimiento académico | 25 % | `0.25 / (1 + e^(−0.08·(P−70)))` (sigmoide centrada en 70) | `P` = **`nota_final ?? total_curso`** (media; la final manda, el parcial AVAC es respaldo) — [H1] | 0.04 (≈ nota 50) |
| Administrativo | 15 % | matriculado → 0.15 · irregular → 0.05 | `estado_matricula` | 0.03 |

`índice = acceso + actividades + rendimiento + administrativo` (máximo 1.00).

Referencia de la curva de acceso: d=0 → 0.30 · d=7 → 0.15 · d=14 → 0.07 · d=30 → 0.01.
Referencia de la sigmoide: nota 50 → 0.04 · 60 → 0.08 · 70 → 0.125 · 80 → 0.19 · 90 → 0.23.

### 2.1 Clasificación de riesgo (a partir del índice)

| Índice | Nivel | Color |
|---|---|---|
| ≥ 0.80 | **Sin riesgo** | azul |
| ≥ 0.65 | **Bajo** | verde |
| ≥ 0.35 | **Medio** | amarillo |
| < 0.35 | **Alto** | rojo |
| (menos de 2 fuentes de datos reales) | **Sin clasificar** (None) | gris |

Constantes en código: `UMBRAL_SIN_RIESGO = 0.80`, `UMBRAL_BAJO = 0.65`,
`UMBRAL_MEDIO = 0.35`. La regla de "datos insuficientes" exige **≥ 2 componentes
con dato real** (no default) para asignar nivel.

### 2.2 Cómo se alimenta (ETL)

`calcular_indice_compromiso(dias_sin_acceso=máx, tareas_entregadas, tareas_totales,
promedio_calificaciones=media_nota_final, estado_matricula, bloque_actual,
dias_desde_ultimo_acceso=mín)`. El engagement se mide con el **mínimo** (último
acceso real), mientras que la "materia más descuidada" (máximo) se conserva para
la **alerta por curso**, no para el índice global.

---

## 3. Contraste con lo declarado en el paper

En el paper (Tabla 1) el índice de compromiso se declara como:

> `Índice = 0.40·A + 0.60·C`, con `A = 1 si días sin acceso ≤ 7 (si no, 0)` y
> `C = actividades cumplidas / máximo`; bandas **≥ 0.80 Alto · ≥ 0.50 Medio · < 0.50 Bajo**.

La implementación **actual difiere** de esa formulación (es una versión posterior,
"v2 mejorada"). Diferencias que conviene declarar con honestidad metodológica:

| Aspecto | Paper (Tabla 1) | Implementación vigente (v2) |
|---|---|---|
| Nº de dimensiones | 2 (acceso + actividades) | 4 (acceso, actividades, rendimiento, administrativo) |
| Acceso | binario (A = 1/0 con corte en 7 días) | **continuo**: `0.30·e^(−d/10)` |
| Pesos | 0.40 / 0.60 | 0.30 / 0.30 / 0.25 / 0.15 |
| Rendimiento y matrícula | no entran en el índice | sí (25 % y 15 %) |
| Datos ausentes | no especificado | **señal proporcional** (defaults 0.03–0.05), no neutral |
| Niveles | 3 (Alto/Medio/Bajo) | **4** (+ "Sin riesgo") + "Sin clasificar" |
| Umbrales | 0.80 / 0.50 | 0.80 / 0.65 / 0.35 |
| Semántica de bandas | niveles de *compromiso* | niveles de *riesgo* (inverso al índice) |

**Recomendación:** actualizar el paper para describir el modelo v2 realmente
implementado (o presentar v1→v2 como evolución con su justificación empírica).
Reportar la fórmula exacta, los pesos, los umbrales y el manejo de datos ausentes
es parte de la reproducibilidad.

---

## 4. Aportes que el paper puede reivindicar (según los hallazgos)

1. **Modelo de engagement multinivel y continuo** (no binario/escalonado): evita
   "agujeros" entre rangos y da gradiente fino de priorización. Aporte metodológico
   frente a reglas de umbral duro típicas de sistemas de alerta temprana (EWS).
2. **Datos ausentes como señal, no como neutro** (P3-FIX): la falta de acceso,
   tareas o notas se penaliza de forma proporcional. Aporte: los EWS suelen tratar
   el faltante como 0 o como promedio; aquí se modela como riesgo latente.
3. **Hallazgo empírico "último acceso vs materia más descuidada"** (n = 5 996):
   usar el **mínimo** (último acceso real, prom. 4.2 días → 0.198) en vez del
   **máximo** (materia más abandonada, prom. 34.9 días → 0.009) cambia el puntaje
   de acceso ~**22×**. Con el máximo, el 30 % del índice se anulaba para casi todos
   (solo 33 de 3 493 podían salir "Bajo"): *el modelo condenaba en vez de
   discriminar*. Este es un hallazgo publicable sobre **operacionalización de la
   inactividad** en entornos multi-asignatura.
4. **Nivel "Sin riesgo" y rescate del sentido de "Bajo"**: con solo 3 niveles y sin
   uno neutro, "Medio" se volvía cajón de sastre (**51.8 %** del total), inútil para
   priorizar. Aporte: diseño de bandas orientado a la **acción/priorización**, no
   solo a la descripción.
5. **Umbrales calibrables por período** (`SemesterConfig`): reproducibilidad y
   adaptación institucional; el paper puede reportar los valores usados y su
   sensibilidad.

---

## 5. Limitaciones / hallazgos a declarar (y mejoras propuestas)

Estas son observaciones honestas que fortalecen el paper (validez interna) y
marcan trabajo futuro:

- **H1 — [IMPLEMENTADO 2026-09] Sesgo a "Alto" por notas finales ausentes.** El
  componente académico ahora usa `nota_final ?? total_curso`: si no hay nota final,
  toma el parcial de AVAC como proxy; la final, cuando existe, manda. Aplicado en
  `calcular_indice_compromiso` (param `promedio_total_curso`) y en los tres puntos
  de cálculo (ETL `transformers.py`, `pipeline.py`, `services/recalculo.py`).
  Efecto medido en el caso base: índice 0.676→0.838, de "Bajo" a "Sin riesgo".
  *Pendiente asociado:* re-validar los umbrales (0.80/0.65/0.35) con la nueva
  distribución tras el próximo ETL.
- **P-DISC — [PENDIENTE] Alerta de discrepancia nota final vs AVAC.** Cuando la
  nota final y el `total_curso` de AVAC **difieren extremadamente** (p. ej. AVAC 88
  y final 0 por una baja administrativa), hay que **conservar ambas** y **emitir una
  alerta** para revisar/rectificar y anticipar reclamos de estudiantes. No se
  resuelve con `nota_final ?? total_curso` (eso elige una); requiere comparar las
  dos y marcar la divergencia. Ver diseño propuesto en
  `docs/MODELO_CONCEPTUAL_METRICAS.md` §Pendientes.
- **H2 — Artefactos de bloque.** Durante un bloque, las materias del bloque cerrado
  no se refrescan; su inactividad/incumplimiento infla el riesgo. *Propuesta:*
  acotar días y ratio por ventana de bloque activo (ya existe `services/bloques.py`
  `acotar_dias`/`cursos_del_bloque_cerrado`; extender su uso al índice).
- **H3 — El riesgo mostrado es del último ETL**, no en vivo por grupo/filtro.
  Declarar la latencia de actualización (cadencia del scraping/ETL).
- **H4 — Ponderación engagement-dominante (60 %).** Es una decisión de diseño
  (enfoque preventivo: la desconexión precede al abandono), pero implica que un
  estudiante con excelentes notas y baja actividad medida siga como "Alto".
  Declararlo como *elección teórica* y validarlo contra desenlaces reales
  (reprobación/deserción) para reportar sensibilidad/especificidad.

### Métricas sugeridas para el paper
Distribución de niveles (con % por banda), impacto del cambio MÍN vs MÁX,
proporción de estudiantes "Sin clasificar", y —si hay ground truth de fin de
período— matriz de confusión / AUC del índice como predictor de reprobación o
deserción. Con eso el modelo pasa de "declarado" a "validado".

---

*Este documento refleja el estado del código a 2026-09. Si el modelo cambia
(p. ej. se adopta H1), actualízalo junto con `docs/DATA_DICTIONARY.md`.*
