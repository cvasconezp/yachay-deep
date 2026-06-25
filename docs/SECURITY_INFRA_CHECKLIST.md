# Checklist de Infraestructura de Seguridad — Yachay Deep

Pasos que se realizan en los **paneles de Railway / Vercel / Cloudflare**, no en código.
Complementa `SECURITY_FRAMEWORK.md` y el Runbook. Marca cada casilla al completarla.

> Lo implementable en código (hashing argon2, 2FA, refresh tokens, CORS, multi-tenant)
> ya vive en el repo. Este documento cubre **solo lo que requiere acción manual en consola**.

---

## WF1A — Cifrado en reposo (Railway)

Railway cifra en reposo los volúmenes de base de datos. La tarea es **confirmar y cerrar fugas**.

- [ ] Confirmar **plan de pago** en Railway (Settings -> Usage/Billing).
- [ ] Activar **Private Networking** entre el servicio FastAPI y Postgres.
- [ ] Verificar conexión a Postgres por hostname privado (`*.railway.internal`), no por URL pública.
- [ ] Confirmar que `DATABASE_URL`, `SECRET_KEY` y demás secretos viven en **Railway Variables**.

Verificación (sobre el repo):

```bash
grep -ri "postgresql://" . --include=*.py --include=*.env* | grep -v example
grep -rin "print.*environ\|log.*DATABASE_URL\|console.log.*env" backend/ frontend/src
```

**DoD:** plan de pago · private networking · cero secretos en repo/logs · conexión por host privado.

> Nota cédula: no cifrarla reversiblemente (rompe los lookups). Si hay que protegerla, usar
> `cedula_hash` (SHA-256 con sal por entorno) e indexar esa columna; mostrar enmascarada en UI.

---

## WF2 — Backups automáticos + restauración probada

Scripts en el repo: `scripts/backup_manual.sh` y `scripts/restore_test.sh`.

### Backups gestionados (panel)
- [ ] Activar **backups gestionados** de Railway en Postgres. Anotar frecuencia y retención.

### Segunda copia independiente
- [ ] Crear bucket S3-compatible (recomendado **Cloudflare R2**).
- [ ] Plantilla *postgres-s3-backup* / *Postgresus*: `pg_dump` programado -> comprime -> cifra AES-256 -> sube a R2/S3.
  - [ ] Configurar `DATABASE_URL` privada, bucket, clave de cifrado, frecuencia diaria, retención 7-30 días.
  - [ ] Activar verify/restore drill automático cada 24 h a una BD separada.

### Respaldo manual y drill (scripts del repo)
- [ ] Antes de migraciones/despliegues riesgosos:
  ```bash
  DATABASE_URL="postgresql://..." BACKUP_REMOTE="r2:yachay-backups" \
    BACKUP_ENCRYPT_KEY="..." ./scripts/backup_manual.sh
  ```
- [ ] **Drill trimestral documentado**:
  ```bash
  ./scripts/restore_test.sh ./backups/yachay_YYYYMMDD_HHMMSS.sql.gz
  ```
- [ ] Registrar en bitácora: fecha, tamaño, tiempo de restauración, resultado.

**DoD:** backup gestionado · 2ª copia cifrada en R2/S3 · verificación diaria · primer drill trimestral en bitácora.

---

## WF4 (parte infra) — Variables de entorno

- [ ] `SECRET_KEY` fuerte (`openssl rand -hex 32`). El backend ya rechaza arrancar con la clave por defecto si `DEBUG=False`.
- [ ] `CORS_ORIGINS` con dominios exactos por entorno (prod y preview), sin `*`.
- [ ] `ACCESS_TOKEN_EXPIRE_MINUTES` corto (15-30) y `REFRESH_TOKEN_EXPIRE_DAYS` (7-30).

---

## WF5 (parte infra) — Aislamiento por tenant

- [ ] **1-3 clientes:** una instancia Railway + Vercel por cliente, secretos propios, inventario actualizado.
- [ ] **4+ clientes:** migrar a multi-tenant (`tenant_id` + RLS, ya soportado en código) y correr los tests de aislamiento antes de mezclar datos reales.

---

## Bitácora de drills de restauración

| Fecha | Backup probado | Tamaño | Tiempo | Estudiantes | Intervenciones | Resultado |
|-------|----------------|--------|--------|-------------|----------------|-----------|
|       |                |        |        |             |                |           |
