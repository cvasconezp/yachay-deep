# Auditoría de identidad de marca — Core

*Producto auditado contra "Arquitectura de Marca — Yachay Deep v2.0" (julio 2026). Fecha: 2026-07-07.*

## Contexto

| Campo | Valor | Fuente |
|---|---|---|
| Producto | **Core** — inteligencia académica preventiva (Learning Analytics → Early Warning → DSS) | Arquitectura §3 |
| Frente/segmento | Educación (instituciones) | Arquitectura §2, §13 |
| Madurez esperada | **INSIGNIA** (uno a la vez; Fase 6 aún en curso) | Arquitectura §2, §7 |
| Color asignado | "Color **diferenciado propio**" (aún sin definir); el sitio usa `brand-gold` de la casa | Arquitectura §8 |
| Dominio | Ruta interna `/core` (marketing) + app por subdominio de tenant `ups.yachaydeep.com` | Arquitectura §5, §13; Auditoría Técnica §1 (flujo) |

### Alcance y límites de evidencia (declaración honesta)

- **Repo `cvasconezp/yachay-deep`: privado.** El sandbox no tiene credenciales; no pude leer CSS/tokens, `index.html`, favicon ni componentes directamente. Los puntos que dependen del código fuente se apoyan en los dos documentos técnicos ya cargados (`Ficha-Producto-Yachay-Deep.md`, `Auditoria-Tecnica-Yachay-Deep.md`).
- **Landing `/core`: SPA client-rendered, sin navegador conectado.** La captura en vivo (`web_fetch`) solo devuelve el *shell* estático; el contenido renderizado por JS (texto de endoso en cabecera/pie, badge visual, emoji, logo-lockup) **no es verificable** en esta pasada y se marca como tal, no se infiere.
- Lo verificable con certeza: **meta/SEO en vivo** de `/core`, **patrón de dominio**, y los registros que la propia arquitectura §8/§13 ya dejó anotados del sitio.

---

## 1. Endoso y naming

**🟡 Endoso (cabecera y pie) — no verificable directamente.** La arquitectura §13 dejó la casilla de Core como *"(endoso a verificar en landing)"*, y el *shell* de `/core` no contiene texto de endoso (se inyecta por JS). No puedo confirmar si aparece la fórmula canónica **"un producto de Yachay Deep Labs"** ni si es consistente entre cabecera y pie. Acción: verificar en render y forzar la fórmula canónica; retirar cualquier "por"/"Powered by"/"desarrollado por" si aparece. *Evidencia: Arquitectura §6, §13.*

**🔴 Nombre del producto — inconsistente entre título/meta y catálogo.** El catálogo de marca lo nombra **"Core"** (Arquitectura §2, §11 tarjeta), pero el `<title>` real de `/core` es **"Yachay Deep — Convertimos datos en conocimiento"** (el de la casa), sin la palabra "Core". Además coexiste el nombre largo académico *"…for Student Retention"* que §13 marca como pendiente de fijar. El nombre del producto **no aparece** en title, meta ni (probable) favicon de su propia ruta. *Evidencia: `web_fetch` yachaydeep.com/core (title/meta idénticos al home); Arquitectura §13 ("nombre con/sin 'for Student Retention'").*

**🟡 Lockup (logo propio + endoso ≤30%) — no verificable + señal de conflicto.** El *shell* de `/core` sirve el logo de la **casa** (`/brand/logo-stacked.svg`), no un logo propio de Core; el logo/endoso final los pinta el JS. Como Core comparte además el `brand-gold` de la casa (§8), hay riesgo de que el lockup no distinga a Core como marca endosada con identidad propia. Acción: confirmar en render que existe logo propio de Core con endoso subordinado. *Evidencia: `web_fetch` (asset `logo-stacked.svg`); Arquitectura §8.*

---

## 2. Color e identidad visual

**🟡 Color primario — usa el oro de la casa, sin color propio diferenciado.** El bundle del sitio asigna a Core **`brand-gold`**, que es la gama institucional de la casa; la arquitectura pide para Core un **"color diferenciado propio"** y marca el estado como **"Revisar"**. Hoy Core no es cromáticamente separable de Yachay Deep-casa. *Evidencia: Arquitectura §8 (fila Core: "brand-gold → Color diferenciado propio · Revisar").*

**🟢 Violeta (reservado a competidores/terceros) — no lo usa.** Core usa oro, no violeta; cumple la regla. *Evidencia: Arquitectura §8.*

**🟢 / 🟡 Tipografía, iconografía y favicon — consistentes con la casa, sin activo propio.** Comparte OG (`/brand/og-cover.png`), logo (`logo-stacked.svg`) y favicon de la casa: coherente con el sistema (🟢), pero sin favicon/marca propios que lo identifiquen como producto endosado (🟡). *Evidencia: `web_fetch` (assets `/brand/*`).*

**🟡 Emoji/símbolo del producto — no verificable.** La arquitectura no asigna emoji a Core (a diferencia del caso FitBro 🏋️/🐆 en §13) y no puedo leer el render. Sin evidencia para confirmar un símbolo único y consistente entre landing, app y catálogo. *Evidencia: ausencia en Arquitectura §3/§11/§13.*

---

## 3. Badge de ciclo de vida

**🔴 Muestra un rótulo de marketing, no el badge del sistema.** La arquitectura §13 registra que en el sitio Core aparece como **"Producto estrella"**, cuando el badge canónico es **`INSIGNIA`** (§7). Es un estado genérico fuera de la taxonomía de badges, lo mismo que "Activa" en otros productos: rompe la lectura de sistema. *Evidencia: Arquitectura §13 (fila Core: "'Producto estrella' → `INSIGNIA`"); §7 tabla de badges.*

**🟢 / 🟡 Versión separada del badge.** No hay evidencia de que Core exhiba una versión técnica como badge (a diferencia del `v5.0` de FitBro, §7/§13) → 🟢. Matiz 🟡: §7 exige comunicar externamente que **la Fase 6 sigue en curso** ("no comunicar 100% terminado"); verificar que la ficha lo refleje y que "insignia" no se lea como "producto terminado". *Evidencia: Arquitectura §7 (aplicación al catálogo, Core).*

---

## 4. Voz y tono (matriz §9)

**🟢 Registro alineado (con matiz de fuente).** El esperado para Core/instituciones es **"técnico-institucional, evidencia y métricas"** (§9). La copy documentada del producto encaja: *"Sistema de inteligencia académica preventiva"* que cierra el ciclo *"detectar → predecir → explicar → recomendar → intervenir → medir impacto"*, y *"convierte los datos dispersos del aula virtual … en una lista priorizada y explicada de a qué estudiante intervenir y por qué"*. Tono institucional, apoyado en métricas (3.040+ estudiantes / 25 programas). *Evidencia: `Ficha-Producto-Yachay-Deep.md` §3 y resumen de catálogo; Arquitectura §3, §9.* **Matiz:** son frases de la ficha/README, no de la landing renderizada (no verificable en vivo esta pasada).

**🟢 Bilingüe kichwa — N/A para Core.** El requisito bilingüe aplica a Kullki, no a Core (§9 fila Comunidades). Sin desviación. *Evidencia: Arquitectura §9, §13.*

---

## 5. Consistencia de dominio y meta

**🟡 Subdominio vs ruta — desviación consciente, decisión pendiente.** El patrón de la casa es subdominio (`ancora.`, `kullki.`); Core vive en **ruta `/core`** para marketing y su **app corre en subdominios de tenant** (`ups.yachaydeep.com`), sin un canónico `core.yachaydeep.com`. La arquitectura §5 lo reconoce como decisión abierta (mantener `/core` por ser insignia integrada, o alinear al patrón). Identidad pública partida en dos. *Evidencia: Arquitectura §5, §13; Auditoría Técnica §1 (flujo: "Navegador … ups.yachaydeep.com").*

**🔴 Metadatos SEO genéricos heredados de la casa.** Confirmado en vivo: `/core` sirve **exactamente el mismo** `title`, `meta description`, `og:title/description/image` que el home, y peor, **`og:url` apunta a `https://www.yachaydeep.com/`** (la home, no a `/core`). Core no tiene title/description/OG propios. *Evidencia: `web_fetch` yachaydeep.com/core → `title: "Yachay Deep — Convertimos datos en conocimiento"`, `meta-og:url: https://www.yachaydeep.com/`.*

**🟡 Correo de contacto canónico — no verificable.** No hay evidencia de un correo de contacto propio de Core en los documentos ni en el *shell*; la auditoría técnica solo cita correos operativos (a Bienestar, admin). Sin confirmación de "uno canónico por producto, sin duplicados". *Evidencia: ausencia en fuentes disponibles.*

---

## 6. Cifras de marca

**🟡 Cifra de impacto sin fuente canónica única.** La cifra de Core es **"3.040+ estudiantes en 25 programas"** (Arquitectura §3), pero §13 anota que aparece **solo en la tarjeta de Labs** y pide "fijar cifra canónica única". No está reflejada en la ficha técnica de Core (que reporta otras métricas: 125 endpoints, 772 tests) → riesgo de cifras dispersas. **Formato de miles:** "3.040+" usa punto como separador (locale `es_EC`, confirmado en `og:locale`), consistente con el español de la casa. El problema es de **fuente/consistencia**, no de formato. *Evidencia: Arquitectura §3, §13; `Ficha-Producto-Yachay-Deep.md` §2; `web_fetch` (`og:locale: es_EC`).*

---

## 7. Salida — tabla de desviaciones

Ordenada por impacto en la percepción de "ecosistema coherente" (mayor primero).

| # | Punto | Estado | Actual | Esperado (arquitectura) | Corrección | Esfuerzo |
|---|---|---|---|---|---|---|
| 1 | Badge de ciclo de vida (§3) | 🔴 | "Producto estrella" | `INSIGNIA` (§7) | Reemplazar el rótulo por el badge del sistema `INSIGNIA` | Bajo |
| 2 | Endoso cabecera+pie (§1) | 🟡 | No verificable / a verificar (§13) | "un producto de Yachay Deep Labs" en ambos, sin variantes | Confirmar en render y forzar fórmula canónica; retirar "por/Powered by/desarrollado por" | Bajo |
| 3 | Meta SEO propios (§5) | 🔴 | title/description/OG idénticos al home; `og:url`→home | title/description/OG propios de Core; `og:url`=`/core` | Escribir head propio de la ruta `/core` (title "Core — …", description, OG, canonical) | Bajo-Medio |
| 4 | Nombre en título/favicon (§1) | 🔴 | `<title>` = "Yachay Deep — …"; sin "Core" | Nombre "Core" consistente en título, meta, footer, favicon | Incluir "Core" en title/meta de la ruta; fijar uso de nombre largo | Bajo |
| 5 | Color primario propio (§2) | 🟡 | `brand-gold` (oro de la casa) | Color diferenciado propio (parte del rito de graduación) | Definir y aplicar color propio de Core distinto del oro-casa | Medio |
| 6 | Dominio (§5) | 🟡 | Ruta `/core` + app en `ups.yachaydeep.com` | Subdominio `core.yachaydeep.com` (o decisión explícita de excepción) | Resolver la decisión §5 y unificar identidad de dominio | Medio |
| 7 | Cifra canónica de impacto (§6) | 🟡 | "3.040+/25" solo en tarjeta Labs | Cifra canónica única, misma en toda la casa | Fijar la cifra en una fuente única y referenciarla | Bajo |
| 8 | Lockup / logo propio (§1) | 🟡 | *Shell* usa logo de la casa; propio no verificable | Logo propio + endoso subordinado ≤30% | Verificar en render que Core tiene logo-lockup propio | Bajo-Medio |
| 9 | Emoji/símbolo único (§2) | 🟡 | No verificable / no asignado | Un emoji/símbolo consistente landing-app-catálogo | Asignar y aplicar símbolo de Core | Bajo |
| 10 | Correo de contacto canónico (§5) | 🟡 | No verificable | Uno canónico por producto, sin duplicados | Definir/verificar correo canónico de Core | Bajo |
| 11 | Violeta reservado (§2) | 🟢 | Oro, no violeta | No usar violeta | — (cumple) | — |
| 12 | Voz y tono (§4) | 🟢 | Técnico-institucional con métricas | Técnico-institucional, evidencia y métricas | — (verificar contra render) | — |
| 13 | Bilingüe kichwa (§4) | 🟢 | N/A | N/A (aplica a Kullki) | — | — |

### Las 3 correcciones de mayor impacto y menor esfuerzo (quick wins)

1. **Badge `INSIGNIA`** en lugar de "Producto estrella" — cambio de copy que reengancha a Core con el sistema de badges compartido; es lo que más hace que la vitrina se lea como un ecosistema y no como productos sueltos. *(fila 1)*
2. **Endoso canónico "un producto de Yachay Deep Labs"** visible en cabecera y pie de `/core`, retirando cualquier variante — el endoso es, según §6, el dispositivo que unifica la lectura de casa. *(fila 2)*
3. **Meta propios de la ruta `/core`** (title con "Core", description y OG propios, `og:url` correcta) — hoy `/core` se anuncia a buscadores y redes como si fuera el home; corregir el head da identidad propia y SEO sin tocar diseño. *(filas 3 y 4, mismo cambio de head)*

---

*Nota de método: auditoría contra Arquitectura de Marca v2.0 con evidencia de (a) captura en vivo de `yachaydeep.com/core`, (b) los dos documentos técnicos de Core, y (c) los registros de sitio de la §8/§13 de la propia arquitectura. Repo privado y render JS de la SPA quedaron fuera de alcance y sus puntos se marcaron como no verificables en vez de inferirse.*
