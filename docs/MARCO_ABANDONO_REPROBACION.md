# Marco conceptual: abandono, deserción y reprobación

**Documento de referencia (fundamentado en literatura).** Sirve para (a) nombrar
bien los módulos, (b) tener un catálogo de variables que la literatura asocia a la
reprobación y al abandono, mapeado contra lo que Core ya captura y lo que falta, y
(c) orientar la evolución del modelo de riesgo. Complementa
`docs/MODELO_CONCEPTUAL_METRICAS.md` y `docs/RIESGO_Y_COMPROMISO.md`.

Última revisión: 2026-10.

---

## 1. Terminología (y por qué importa)

La literatura advierte "proliferación terminológica": varios términos se usan,
a veces, como sinónimos, pero tienen matices que conviene respetar.

| Término | Qué nombra | Observación de la literatura |
|---|---|---|
| **Deserción** | Abandono prematuro de la carrera sin titularse. | Es el más usado (~65 % de artículos) pero **cuestionado**: carga una connotación militar y responsabiliza al estudiante. Se recomienda evitarlo como etiqueta. |
| **Abandono** | El mismo fenómeno, visto como proceso multicausal. | **Término preferido** por neutralidad política; concibe el fenómeno como complejo e institucional, no como culpa del estudiante. |
| **Permanencia** | Acciones del **estudiante** para seguir en la carrera. | Enfoque positivo, centrado en el sujeto. |
| **Retención** | Acciones de la **institución** para que el estudiante no abandone. | Enfoque positivo, centrado en la institución. |
| **Rezago** | Atraso en la trayectoria (no avanza al ritmo del plan). | Antesala frecuente del abandono; distinto de reprobar una materia. |
| **Reprobación** | No aprobar una o más asignaturas (`nota_final < umbral`). | Es un **evento académico**, a menudo **causa o señal** de abandono, pero **no es** abandono. |

**Tipología de abandono por alcance** (útil para no sobre-afirmar): *nano*
(cambio administrativo/modalidad), *micro* (cambia de programa en la misma
institución), *meso* (cambia de institución), *macro* (sale del sistema de
educación superior). Lo que normalmente preocupa como "deserción" es el abandono
meso/macro.

> **Implicación para Core:** reprobación ≠ abandono. El módulo que hoy llamamos
> "Reprobados" reporta **reprobación** con **señales de riesgo de abandono**; no
> confirma deserción (eso lo estiman el modelo ML `prob_desercion` y, en su día,
> los desenlaces reales).

### Recomendación de nombre

- Nombrar el **fenómeno**, no a la persona ("Reprobados" etiqueta al sujeto).
- Si se mantiene centrado en reprobar: **"Reprobación"** o **"Análisis de Reprobación"**.
- Si se amplía hacia el riesgo/salida: **"Reprobación y Abandono"** (evitar
  "Deserción" en el título).
- Si a futuro es el hogar de todo el seguimiento de estudiantes en riesgo:
  **"Permanencia"** (paraguas positivo, alineado con "retención") — o un hub
  genérico **"Informes"** si agrupará varios reportes.

Sugerencia operativa: **"Reprobación y Abandono"** como etiqueta del módulo actual
(la ruta `/reprobados` y el endpoint pueden quedarse para no romper enlaces).

---

## 2. Variables asociadas (catálogo de la literatura) → mapeo a Core

La literatura organiza los factores en **niveles** (sujeto, institucional, sistema,
macrosocial). Abajo, cada grupo con ejemplos y su estado en Core: **✅ usado** en el
modelo de riesgo, **🟡 capturado** pero no usado, **⬜ no capturado** (brecha).

### 2.1 Nivel sujeto (individual)

**Académicos** *(los más estudiados — la variable "desempeño universitario" aparece
en ~93 artículos de la revisión LatAm):*
- Calificaciones / nota final, asignaturas aprobadas vs. reprobadas — ✅
- Repitencia / número de matrícula (2da, 3ra) — ✅
- Rendimiento en enseñanza media y prueba de ingreso — ⬜ (no se captura)
- Rezago / avance en la malla — 🟡 (la malla existe; falta un indicador de atraso)

**Conductuales / compromiso (engagement con el AVAC)** *(fortaleza de Core):*
- Accesos al aula virtual, días desde el último acceso — ✅
- Cumplimiento de actividades / % de tareas — ✅
- Índice de compromiso (acceso + actividades + rendimiento + administrativo) — ✅

**Sociodemográficos:**
- Género — 🟡 (capturado, cifrado; no entra al riesgo)
- Edad — 🟡 (hay `fecha_nacimiento`; no se usa)
- Lugar de residencia / ruralidad / distancia — 🟡 (residencia cifrada; no se usa)
- Ascendencia étnico-racial — 🟡 (autoidentificación cifrada; no se usa)
- Estructura familiar (vivir con la familia) — ⬜

**Socioeconómicos:**
- Ingresos del hogar — ⬜
- Trabajo estudiantil (trabaja y estudia) — ⬜
- Educación / ocupación de los padres — ⬜
- Acceso a computador / conectividad — ⬜ (relevante en modalidad en línea)

**Psicológicos / salud:**
- Motivación, autoeficacia, orientación vocacional, salud mental — ⬜
  *(coincide con el límite declarado de Core: el índice es solo conductual, no
  cognitivo ni emocional — Bergdahl et al., 2024. Las "novedades" cualitativas y las
  derivaciones a Bienestar podrían cubrir parte).* 

### 2.2 Nivel institucional

- Relación docente–estudiante y metodología — 🟡 (hay datos de docente y seguimiento
  docente; no entra al riesgo del estudiante)
- Tutorías / asesorías académicas — 🟡 (módulo de Tutorías + Intervenciones existen)
- Estrategias de permanencia e intervenciones (medio, motivo, resultado,
  seguimiento) — ✅ (ciclo de intervención con impacto)
- Relación con pares / trabajo colaborativo — ⬜
- Plan de estudios, flexibilidad, evaluación — ⬜

### 2.3 Nivel sistema educativo

- **Becas / ayudas financieras** *(la variable más estudiada — ~53 artículos)* — ⬜
- Estado de matrícula / pago (riesgo administrativo-financiero) — ✅ (15 % del índice)
- Accesibilidad territorial, políticas, presupuesto — ⬜

### 2.4 Nivel macrosocial

- Crisis económicas, inseguridad, pandemia / disponibilidad tecnológica — ⬜
  (contexto; normalmente no se modela por estudiante)

---

## 3. Modelos teóricos de referencia

- **Tinto (integración académica y social):** el abandono es, sobre todo, un fallo
  de **integración**. Core mide bien la cara **académica** (notas) y **conductual**
  (acceso/actividades), pero **no** la **integración social** (relación con pares,
  pertenencia) → brecha teórica.
- **Spady (1970):** antecedente sociológico de Tinto.
- **Bean & Eaton (modelo psicológico):** el estudiante llega con rasgos
  preexistentes (autoeficacia, estilos atribucionales) que median su interacción con
  la institución → apoya incorporar variables psicológicas.
- **Lent (sociocognitivo / satisfacción académica):** la satisfacción con la
  experiencia de aprendizaje como predictor.
- **Modelos económicos (capital humano — Becker):** se abandona cuando el costo
  percibido supera el beneficio esperado → relevancia de lo financiero/becas.
- **Ecológico (Bronfenbrenner):** integra micro/meso/exo/macrosistema; encuadra por
  qué conviene mirar varios niveles, no solo al estudiante.

---

## 4. Lectura para Core (qué tenemos, qué falta, cómo evolucionar)

1. **Core es fuerte en lo conductual-académico** (engagement con el AVAC +
   rendimiento + administrativo). Eso coincide con las dimensiones que la literatura
   halla más operacionalizables con datos de plataforma.
2. **La mayor brecha es socioeconómica y psicológica**, justo las que la literatura
   marca como determinantes (ingresos, trabajo, becas; motivación, autoeficacia).
   Core **ya captura** varias **sociodemográficas** (género, edad, etnia,
   residencia) pero **no las usa** en el riesgo — oportunidad de evolución de bajo
   costo (ya están en la base, cifradas).
3. **Integración social (Tinto) y becas/financiero fino** no se miden hoy →
   candidatos de alto valor si se consiguen esos datos.
4. **Separar conceptos en el producto:** "reprobación" (evento académico) como
   señal, y "abandono/permanencia" como el objetivo de prevención. El módulo de
   reprobados es una **entrada** a ese objetivo, no el objetivo en sí.
5. **Para el paper / comparación:** este catálogo permite situar a Core frente al
   estado del arte (qué dimensiones cubre y cuáles no) y planificar la incorporación
   gradual de variables, declarando siempre el límite conductual (Bergdahl et al.,
   2024).

> **Nota de validación:** incorporar variables sensibles (etnia, género, residencia,
> ingresos) a un modelo de riesgo exige cuidado ético (sesgo, equidad) y, en Core,
> respeta el cifrado en reposo de la PII. Antes de usarlas, validar que mejoran la
> predicción sin introducir discriminación.

---

## 5. Referencias

- Revisión sistemática mixta sobre **abandono y permanencia** en universidades de
  Latinoamérica y el Caribe (terminología, niveles de factores y modelos teóricos):
  https://www.scielo.sa.cr/pdf/aie/v24n2/1409-4703-aie-24-02-123.pdf
- **Predictive models for higher education dropout: a systematic literature review**
  (tipología nano/micro/meso/macro; dimensiones socioeconómica, académica,
  psicológica/salud, acceso): https://epaa.asu.edu/index.php/epaa/article/view/6845
- *How Does Learning Analytics Contribute to Prevent Students' Dropout in Higher
  Education: A Systematic Literature Review*:
  https://repositorio.upt.pt/items/187fb88e-4f04-4670-a0cc-ff00319af4f0/full
- *Predictors and early warning systems in higher education: a systematic literature
  review*: https://core.ac.uk/works/143459820
- *A Systematic Review of the Factors that Impact the Prediction of Retention and
  Dropout in Higher Education* (HICSS):
  https://scholarspace.manoa.hawaii.edu/items/cea3a935-cc7d-44f6-8c96-d8aaadbb2e7c
- Bergdahl, N., et al. (2024). *Unpacking student engagement in higher education
  learning analytics: a systematic review.* IJETHE, 21(1), 63. (Límite conductual
  del compromiso; ya citado en el paper de Yachay Deep.)
- Marcos clásicos: Tinto (integración), Spady, Bean & Eaton (psicológico), Lent
  (sociocognitivo), Becker (capital humano), Bronfenbrenner (ecológico).

*Mantener vivo: si se incorpora una variable nueva al modelo de riesgo, anotar aquí
en qué nivel/dimensión cae y con qué evidencia de la literatura se justifica.*
