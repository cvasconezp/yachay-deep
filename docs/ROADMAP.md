# ROADMAP — Core (Yachay Deep)

Dónde está Core y hacia dónde va. Se lee junto a [PRODUCT.md](./PRODUCT.md). Estado honesto: **INSIGNIA con Fase 6 en curso** — no es un producto "100 % terminado".

Convención: ✅ hecho · 🔄 en curso · ⏳ planificado · 🔒 requiere confirmación/gate.

---

## Fases del producto

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Analítica descriptiva/diagnóstica (dashboards, ficha 360°) | ✅ |
| 2 | Analítica predictiva ML (deserción/reprobación por carrera) | ✅ |
| 3 | Explicabilidad (XAI) + contrafactuales | ✅ (con fallback; SHAP real ⏳) |
| 4 | Recomendaciones automáticas | ✅ |
| 5 | Intervenciones y ciclo cerrado + efectividad | ✅ |
| 6 | Integración LMS en tiempo real (Moodle/Canvas), notificaciones push/WhatsApp | 🔄 |

## Estandarización de la casa (`chore/estandar-casa`)

Aplicado en esta iteración (ver [../CHANGELOG.md](../CHANGELOG.md) y [AUDITS/](./AUDITS/)):

- ✅ Error genérico al cliente; logging con correos enmascarados.
- ✅ CI: `pip-audit`/`npm audit` bloqueantes.
- ✅ Fuente única de impacto (`GET /metrics/impact`); la landing la lee.
- ✅ Diccionario de métricas versionado (DATA_DICTIONARY §8).
- ✅ Telemetría de uso pseudonimizada (`usage_events`).

Pendiente (preparado, no aplicado):

- ⏳ **Alembic** — retirar `create_all`/`upgrade_tables` artesanal; migración inicial + rollback.
- ⏳ **Rate limiting** completo (refresh, uploads, escritura admin) con store persistente (Postgres/Redis).
- ❌ **Google OAuth** — **descartado en Core por diseño**. Las cuentas las provisiona el admin y la auth es contraseña + 2FA + PIN; el login con Google es patrón de Áncora (docentes), no de Core.
- ⏳ **Reproducibilidad ML** — versionar los `.pkl` por carrera; instalar SHAP real o fijar el fallback con test de regresión.
- 🔒 **Contract 2.3b** — drop del texto plano de PII (cédula, etnia, domicilio). Requiere backup verificado + confirmación explícita. NO ejecutar sin OK.

## Corto plazo (mismo motor)

- ⏳ Narrativa automática con LLM sobre las salidas XAI ("este estudiante está en riesgo porque…") con pseudonimización LOPDP.
- ⏳ Tablero de **impacto de intervenciones** explotando los snapshots antes/después ya guardados.
- ⏳ Recuperación de cuenta self-service + verificación de correo.

## Medio plazo

- ⏳ **Multi-tenant real** (tenant_id + Row-Level Security) + onboarding self-service → servir varios clientes desde una instancia.
- ⏳ Conectores de ingesta más allá de AVAC (Moodle API estándar, Canvas, formularios) → desacoplar del scraping frágil.
- ⏳ Backups con *restore drill* documentado y custodia offline de llaves de cifrado.

## Ambicioso

- ⏳ Plataforma regional de *learning analytics* de retención con **benchmarking anonimizado** entre instituciones, modelos de riesgo transferibles y recomendaciones adaptativas que aprenden de qué intervención funcionó.

## Fuera de alcance (por decisión)

- ❌ Convertirse en LMS o tutor de contenidos (compite con Moodle/Canvas).
- ❌ Forzar multi-país antes de consolidar Ecuador.

---

*Última actualización: 2026-07. Ver [PRODUCT.md](./PRODUCT.md) para el "qué es".*
