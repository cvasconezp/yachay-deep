# ADMIN GUIDE — Core (Yachay Deep)

Guía para **administradores** de una instancia de Core: usuarios, ingesta de datos, configuración del semestre y operación. Para el uso diario ver [USER_GUIDE.md](./USER_GUIDE.md); para despliegue ver [DEPLOYMENT.md](./DEPLOYMENT.md).

---

## Roles (RBAC)

| Rol | Puede |
|---|---|
| `admin` | Todo: usuarios, ETL, configuración, derivaciones |
| `coordinador` | Analítica de su carrera, intervenciones, reportes |
| `docente` | Vistas de sus asignaturas |
| `monitor` | Dashboard, fichas, alertas, intervenciones |

Buenas prácticas: activa `REQUIRE_ADMIN_2FA=true`; usa cuentas nominales (no compartidas).

## Gestión de usuarios

- Crear/editar/desactivar usuarios y asignar rol y permisos (tabs).
- **Reseteo de contraseña / 2FA:** hoy lo hace el admin (autoservicio en el roadmap). Para forzar reseteo del admin desde el entorno: `ADMIN_RESET=true` + `ADMIN_EMAIL`/`ADMIN_PASSWORD`.

## Ingesta de datos (ETL)

Fuentes: **scraping AVAC/Moodle** (Selenium), **uploads** Excel/CSV/ZIP, y formularios. Pasos:

1. Sube los archivos del periodo (reportes, calificaciones, datos específicos, prácticas) o dispara el scraping.
2. El **pipeline ETL** limpia, normaliza (cédula, correos, montos, NaN) y calcula indicadores de riesgo.
3. Tras N ejecuciones de ETL, los modelos ML se **reentrenan** (configurable).
4. Revisa `scraping_runs` para el estado de cada corrida.

> Cuidado: la ingesta asume plantillas AVAC/UPS. Portar a otra institución requiere ajuste (ver ROADMAP: conectores estándar).

## Configuración del semestre

- `SemesterConfig` activo: fechas de bloques, calendario académico, umbrales (nota de aprobación, días de inactividad, tareas mínimas, compromiso mínimo) y cadencia de reentrenamiento.
- `CourseConfig`: qué cursos scrapear cada semestre.

## Métricas y telemetría

- **Impacto:** `GET /metrics/impact` es la fuente única (`estudiantes_monitoreados`, `programas_activos`).
- **Telemetría de uso:** eventos pseudonimizados en `usage_events` (sin PII). Ver [DATA_DICTIONARY.md](./DATA_DICTIONARY.md) §8.

## Datos sensibles y cumplimiento (LOPDP)

- PII sensible cifrada en reposo (cédula, etnia, domicilio…). **Custodia las llaves** `ENC_KEYS`/`BLIND_INDEX_KEY` offline: si se pierden, los datos cifrados y los backups son irrecuperables.
- **Contract 2.3b (drop de texto plano):** operación sensible; ejecutar solo con backup verificado y confirmación. Ver [SECURITY.md](./SECURITY.md).
- Usa el **demo con datos sintéticos** para mostrar el producto sin exponer PII real.

## Operación

- Backups: `pg_dump` (plataforma). Verifica restauración periódicamente.
- Healthcheck: `GET /health`. Diagnóstico de conectividad AVAC: `GET /health/avac`.
- Errores: se registran en logs (y Sentry si está configurado); el cliente solo recibe mensajes genéricos.

---

*Ver también: [SECURITY.md](./SECURITY.md) · [DEPLOYMENT.md](./DEPLOYMENT.md) · [AUDITS/](./AUDITS/).*
