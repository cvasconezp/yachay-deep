# Auditoría técnica — Yachay Deep

**Repositorio:** `cvasconezp/yachay-deep` · rama `main` @ `41a0ea4` (Contract 2.3a mergeado)
**Alcance:** basado exclusivamente en el código presente. Donde algo no existe se indica **NO ENCONTRADO**.
**Contexto declarado:** datos personales · en producción.
**Fecha:** julio 2026.

> Nota de estado: el cifrado en reposo está en fase Contract 2.3a (la app ya lee de columnas cifradas). El borrado del texto plano (2.3b) es un PR aún **no mergeado**, por lo que **las columnas de texto plano siguen existiendo físicamente en la BD** al momento de esta auditoría (ver §4).

---

## 1. Inventario y arquitectura

### Stack real detectado (con versiones — `backend/requirements.txt`, `frontend/package.json`)

**Backend (Python 3.11, `Dockerfile`):**
- FastAPI `0.136.3`, Uvicorn `0.49.0`
- SQLAlchemy `2.0.50` (ORM), psycopg2-binary `2.9.12` (PostgreSQL)
- pydantic `2.13.4` + pydantic-settings `2.14.0`
- Auth: python-jose[cryptography] `3.5.0` (JWT), passlib[argon2] `1.7.4`, argon2-cffi `23.1.0`, bcrypt `3.2.2`, pyotp `2.9.0` (2FA), qrcode `7.4.2`
- Cifrado: cryptography `43.0.1` (Fernet)
- Datos/ML: pandas `2.2.3`, numpy `2.4.6`, scikit-learn `1.8.0`, joblib `1.5.3`, openpyxl `3.1.5`
- Scraping: selenium `4.44.0`, beautifulsoup4 `4.15.0`, lxml `6.1.1`, requests `2.34.2`, httpx `0.28.1`
- Otros: slowapi `0.1.9` (rate limit), reportlab `4.5.1`, aiofiles `25.1.0`, alembic `1.18.4` (**instalado pero no usado**, ver §4)

**Frontend (`frontend/package.json`):**
- React `18.3.1`, react-dom `18.3.1`, react-router-dom `7.15.0`, Vite `5.4.9`, TailwindCSS `3.4.14`
- leaflet/react-leaflet, recharts `3.8.1`, xlsx `0.18.5`, file-saver
- Dep privada por git: `@yachaydeep/brand: github:cvasconezp/yachaydeep-brand`
- Tests: vitest `4.1.6`, @testing-library, jsdom

### Estructura y puntos de entrada
```
backend/   auth/ models/ routes/ services/ etl/ ml/ scraping/ integrations/ scripts/ tests/
           main.py (entrypoint FastAPI), config.py, database.py, crypto.py, crypto_sync.py
frontend/  src/ (pages/ components/ hooks/ services/api.js), public/, vite
docs/, scripts/
```
- **Backend entrypoint:** `backend/main.py` — `app = FastAPI(... lifespan=lifespan)` (main.py:258-262); arranque en `lifespan()` (main.py:67) llama `validate_security_settings()`, `create_tables()`, `upgrade_tables()` (main.py:70-72).
- **Frontend entrypoint:** SPA React (Vite); `frontend/src/services/api.js` centraliza llamadas.
- **Workers/scripts:** scraping AVAC (`backend/scraping/`), ETL (`backend/etl/`), CLI (`backend/scripts/migrar_cifrado.py`), GitHub Action `daily_scraping.yml`.

### Build / run / deploy
- **Docker:** `Dockerfile` (python:3.11-slim, `uvicorn backend.main:app`). `railway.json` builder=DOCKERFILE. Secretos **en runtime por env** (comentario Dockerfile:2).
- **Deploy:** Backend en Railway (`https://yachay-deep-production.up.railway.app`, ver `frontend/vercel.json`), Frontend en Vercel (proxy `/api/*` → Railway).
- **CI/CD (`.github/workflows/`):** `ci.yml` (lint ruff, test-backend con cobertura, test-frontend vitest, security-audit pip-audit+npm-audit), `daily_scraping.yml` (scraping programado), `brand-sync.yml`.
- **Config por env:** `backend/config.py` (pydantic-settings); `.env.example` versionado, `.env`/`.env.local` ignorados (`.gitignore:16-17,55-56`).

### Flujo (cliente → API → lógica → BD → externos)
```
Navegador (Vercel SPA, ups.yachaydeep.com)
   │  fetch /api/* con cookie HttpOnly (credentials: include)
   ▼
Vercel rewrite /api/* → Railway (FastAPI)   [vercel.json]
   ▼
FastAPI: CORSMiddleware + add_security_headers + set_tenant (X-Tenant)
   ▼  Depends(get_current_user)/require_admin  (JWT en cookie)
Routers (routes/*) → services/ / ml/ / etl/
   ▼
SQLAlchemy ORM → PostgreSQL (Railway)   [EncryptedString descifra PII al leer]
   ▲
Externos: AVAC (Selenium/httpx, avac.ups.edu.ec), Microsoft OAuth (scraping),
          SMTP (email a Bienestar), GitHub API (disparar scraping)
```

### Dependencias desactualizadas / riesgo
- **Frontend con majors atrás:** react/react-dom `18.3.1` (19 disponible), vite `5.4.9` (8), tailwindcss `3.4.14` (4), @vitejs/plugin-react `4.3.4` (6). Hay PRs Dependabot abiertos.
- **`bcrypt==3.2.2`** — versión antigua (rama 4.x disponible). Uso secundario (solo verificación legacy; argon2 es el principal en `jwt.py:22`), riesgo bajo pero conviene actualizar.
- **`scikit-learn==1.8.0`** — bump a 1.9 pendiente (riesgo de compatibilidad al cargar `.pkl`).
- **CVEs conocidos:** NO ENCONTRADO análisis SCA en el repo más allá de `pip-audit`/`npm audit` en `ci.yml` (con `|| true`, no bloquean el build).

---

## 2. Autenticación y autorización

| Punto | Estado | Evidencia |
|---|---|---|
| Login (password) | **Implementado** | `auth/routes.py:141` `OAuth2PasswordRequestForm`; JWT HS256 firmado con `SECRET_KEY` (`jwt.py:53,63`), `ALGORITHM="HS256"` (`config.py:14`) |
| **Login con Google (OAuth 2.0)** | **NO ENCONTRADO** | No hay flujo de Google/OpenID para login de usuario. Las refs OAuth/Microsoft son del **scraping de AVAC** (`scraping/ingresos_avac.py:249,613`), no del login de la app |
| 2FA / MFA | **Implementado (TOTP)** | pyotp (`routes.py:532`), `_verify_2fa_code` (`routes.py:539`), exigido en login si `totp_enabled` (`routes.py:154-158`); códigos de recuperación hasheados; flags `REQUIRE_2FA`/`REQUIRE_ADMIN_2FA` (`config.py`) |
| Hash de contraseñas | **Implementado (fuerte)** | argon2id `time_cost=3, memory=64MB, parallelism=4` + bcrypt legacy con rehash (`jwt.py:21-26`) |
| Sesión: expiración/refresh/logout | **Implementado** | access 30 min (`config.py:22`), refresh 30 días persistido con **rotación + detección de reuso** (`models/refresh_token.py`, `routes.py:_issue_refresh_token`), logout borra cookies (`routes.py:258-262`) |
| "Recordarme" / persistencia | **Parcial (por diseño)** | Cookies de **sesión** por defecto: `PERSIST_COOKIES=False` → `_cookie_max_age` devuelve None (`routes.py:111-113`); al cerrar el navegador se cierra la sesión |
| Bloqueo por inactividad (PIN) | **Implementado (server-side)** | `pin_locked`; `get_current_user` responde 423 en rutas protegidas hasta verificar PIN (`auth/jwt.py`) |
| RBAC | **Implementado** | Roles `admin/coordinador/docente/monitor` (`models/user.py` `UserRole`); `require_admin` (`jwt.py:135`), `require_super_admin` (`jwt.py:151`), aislamiento multi-tenant por `tenant` |
| Endpoints sin protección | **Revisión parcial** | Todos los módulos de `routes/` referencian dependencias de auth (grep `-L` solo devuelve `routes/__init__.py`). **Recomendado:** auditar endpoint por endpoint (algunos `demo_seed`/`debug` podrían necesitar revisión) |
| Recuperación de cuenta / verificación de correo | **Ausente (self-service)** | Solo reset **por admin** (`routes.py` `admin_reset_password`, `main.py:238`). Reset self-service y verificación de email: **NO ENCONTRADO** |

**Cookies (evidencia `auth/routes.py:117-262`):** `httponly=True`, `secure=COOKIE_SECURE` (`config.py:68` default True), `samesite=COOKIE_SAMESITE` (`config.py:69` = "lax"), `domain=".yachaydeep.com"`. Correcto.

---

## 3. Postura de seguridad (OWASP)

- **Gestión de secretos — BUENA.** Todo por variables de entorno (`config.py`); `validate_security_settings()` **falla en producción** si `SECRET_KEY` es el default (`config.py:118-127`). `.env.local`/`.env` ignorados (`.gitignore:16-17,55-56`); solo `.env.example` versionado. Dockerfile inyecta en runtime. GitHub Actions usa `secrets.*` (`daily_scraping.yml:82-89`). **Observación menor:** `backend/.env.example` incluye un valor de muestra `ADMIN_PASSWORD=TuPasswordSegura2024!` (placeholder, pero puede inducir a error).
- **Inyección SQL — mayormente segura, con excepciones de bajo riesgo.** El grueso usa ORM parametrizado. Hay **SQL con f-string**: `ml/features.py:414,425` y `ml/predict.py:478,490` interpolan `periodo_cond` (derivado de `SemesterConfig`, **no de input de usuario**; `student_id` va parametrizado `:sid`); `database.py:233` interpola nombre de tabla de una lista fija. Riesgo real **bajo**, pero conviene parametrizar/allowlist.
- **Validación de entradas.** Cuerpos de request validados con modelos pydantic (`routes/*`); búsquedas van por ORM. Sanitización adicional en ETL (`etl/transformers.py:22-111`).
- **XSS — bajo.** Frontend sin `dangerouslySetInnerHTML` (grep vacío); React escapa por defecto. CSP presente (`main.py:365`).
- **CSRF — mitigado por SameSite, sin tokens.** Cookies con `SameSite=lax` (`config.py:69`); **no hay tokens CSRF**. Aceptable para SPA same-origin vía proxy Vercel, pero es una dependencia implícita.
- **SSRF — bajo.** Peticiones `httpx`/`requests` a URLs fijas (AVAC `avac.ups.edu.ec`, `login.microsoftonline.com`; `main.py:395,403`); `AVAC_BASE_URL` de env. No se encontró fetch de URL controlada por el usuario.
- **CORS — correcto.** `allow_origins=CORS_ORIGINS` + `allow_origin_regex=https://[a-zA-Z0-9-]+\.yachaydeep\.com` + `allow_credentials=True` (`main.py:273-277`). No es wildcard `*`.
- **Cabeceras de seguridad — buenas.** `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Content-Security-Policy`, `Strict-Transport-Security` (condicional), `Referrer-Policy`, `Permissions-Policy` (`main.py:349-375`). `/docs` y `/redoc` deshabilitados si no DEBUG (`main.py:263-264`).
- **Rate limiting — PARCIAL.** slowapi `5/minute` **solo** en login (`routes.py:140`) y verify-pin (`routes.py:481`). Refresh, endpoints admin, uploads y demás **sin rate limit**.
- **Exposición de PII en logs — MEDIA.** Se loguean correos de estudiantes/usuarios: `services/email.py:216` (`correo_estudiante`), `services/daily_digest.py:315`, `main.py:241` (email admin). **No** se loguean tokens ni contraseñas (bien).
- **Manejo de errores — fuga de detalle interno (MEDIA).** El handler global devuelve al cliente `{"detail": f"{type(exc).__name__}: {str(exc)[:300]}"}` (`main.py:307`) — expone tipo y mensaje de la excepción (posibles rutas, errores de BD). Loguea traceback server-side (`main.py:293`, correcto), pero **no debería devolver el mensaje interno al cliente**.

---

## 4. Datos: ingesta, limpieza, organización y gobernanza

- **Fuentes de ingesta:** (1) **uploads** ZIP de CSVs por admin (`routes/admin.py:111,223,402` `UploadFile`), (2) **scraping AVAC** con Selenium/BeautifulSoup (`scraping/ingresos_avac.py`, `estado_tareas.py`), (3) reportes institucionales y formularios (Microsoft Forms) procesados en ETL.
- **Pipeline/ETL:** limpieza/normalización en `etl/transformers.py` (`strip/upper/lower`, `pd.isna`, normalización de decimales `:68-70`, limpieza de nombres `:101-103`, correo `:109-111`). Sanitización de NaN/tipos en `database.py` (`upgrade_tables`, `:245`). Reglas de negocio en `etl/pipeline.py`.
- **Esquema de BD:** modelos SQLAlchemy con **FKs** (múltiples: `models/intervention.py` 4, `recommendation_log.py` 4, `refresh_token.py` 2, etc.) e **índices/constraints** (`index=True`, `__table_args__`, `unique=True`; 104 coincidencias en `models/*.py`).
- **Migraciones — MEDIA (deuda).** Alembic está en `requirements.txt` pero **NO se usa** (no hay `alembic.ini` ni `env.py`: **NO ENCONTRADO**). El esquema se gestiona con `Base.metadata.create_all()` + una función **artesanal** `upgrade_tables()` que hace `ALTER TABLE ADD COLUMN` idempotente (`database.py:81-245`). Sin control de versiones de esquema ni rollback formal.
- **Calidad de datos:** manejo de NaN/nulos (transformers + `database.py`), normalización de tipos; deduplicación puntual (voto-mayoría de sedes). Validación de rangos: parcial.
- **PII y cifrado — IMPLEMENTADO (en transición):**
  - **En reposo:** cifrado a nivel de campo con Fernet (`crypto.py`: `EncryptedString` TypeDecorator `:98`, `encrypt/decrypt` `:66-72`, `blind_index` HMAC `:83`, `MultiFernet` para rotación `:44`). Campos cifrados: `cedula, genero, autoidentificacion_etnica, pais, provincia, ciudad, parroquia, barrio` (`models/student.py:17,38-47`) y `users.totp_secret`. Búsqueda exacta de cédula por **blind index**.
  - **En claro (por decisión, para búsqueda parcial):** `nombre, correo, correo_institucional, telefono, whatsapp`. `fecha_nacimiento` aún **no cifrado**.
  - ⚠️ **Texto plano aún presente en la BD:** el borrado de columnas huérfanas (Contract 2.3b) está en un PR **no mergeado**; hasta ejecutarlo, la cédula/etnia/domicilio en claro **siguen físicamente en la tabla**. Riesgo residual hasta completar 2.3b.
  - **En tránsito:** HTTPS (Railway/Vercel) + HSTS (`main.py:375`).
  - **Cumplimiento:** aplica **LOPDP (Ecuador)**; `autoidentificacion_etnica` es **dato sensible/categoría especial**. **Política de retención/minimización y registro de tratamiento: NO ENCONTRADO** en el repo.
- **Respaldos y recuperación — NO ENCONTRADO en el repo.** No hay scripts `pg_dump`/restore ni rutina de backup en código (depende de la plataforma Railway, externo al repo). Sin evidencia de *restore drill*.

---

## 5. Calidad y consistencia de código

- **Estructura:** modular y coherente (`auth/ models/ routes/ services/ etl/ ml/ scraping/`). Config centralizada por entorno (pydantic-settings). Logging con módulo `logging`. Manejo de errores centralizado (handler global) + `try/except` en servicios (p.ej. cifrado defensivo `crypto_sync.py:30`).
- **Pruebas:** **49** archivos de test backend (`backend/tests/test_*.py`) + **19** frontend (`*.test.jsx`). Cobertura **mínima forzada 60%** (`pytest.ini:6` `--cov-fail-under=60`). CI corre lint + tests + audit. Sin probar de forma evidente: rutas de scraping Selenium (dependen de navegador), algunos flujos ML.
- **Deuda técnica / puntos frágiles:**
  - Migraciones artesanales sin Alembic (riesgo de deriva de esquema; `database.py` tenía además una **clave `"students"` duplicada** en el dict de `upgrade_tables` — la última gana).
  - Acoplamiento del ETL a nombres de columnas/plantillas de AVAC.
  - SQL con f-string en ML (§3).
  - Fuga de detalle de excepción al cliente (§3).
  - Dependencias frontend con majors atrás.

---

## 6. Hallazgos priorizados

| Severidad | Hallazgo | Archivo:línea | Riesgo | Corrección concreta |
|---|---|---|---|---|
| **Alta** | Texto plano de PII (cédula, etnia, domicilio) aún presente físicamente en la BD (Contract 2.3b sin ejecutar) | `models/student.py:17` (columnas `*_cif` mapeadas; huérfanas plano existen) | PII sensible legible en un dump/DB comprometida pese al cifrado | Hacer backup y ejecutar el drop de columnas plano (endpoint `/admin/cifrado/drop-plaintext?mode=apply&confirm=BORRAR`) para completar 2.3b |
| **Media** | El handler de errores devuelve el mensaje/tipo de excepción al cliente | `main.py:307` | Divulgación de detalles internos (rutas, errores de BD) | Devolver `{"detail":"Error interno"}` genérico al cliente; conservar el traceback solo en logs |
| **Media** | PII (correos) escrita en logs | `services/email.py:216`, `services/daily_digest.py:315`, `main.py:241` | Exposición de PII en agregadores de logs | Enmascarar/omitir correos en logs (p.ej. `u***@dominio`); nivel DEBUG y no en prod |
| **Media** | Rate limiting solo en login y verify-pin | `auth/routes.py:140,481` | Fuerza bruta/abuso en refresh, uploads, endpoints admin | Añadir `@limiter.limit` a `/auth/refresh`, endpoints de escritura y uploads; considerar bloqueo por cuenta |
| **Media** | Sin framework de migraciones (Alembic instalado pero no usado) | `database.py:81-245`; alembic.ini **NO ENCONTRADO** | Deriva de esquema, sin rollback formal, riesgo en cambios de datos | Adoptar Alembic (autogenerate + revisión) o formalizar/versionar `upgrade_tables` con control y pruebas |
| **Media** | Respaldos y *restore drill* no evidenciados en el repo | Backups **NO ENCONTRADO** | Pérdida de datos irrecuperable (agravado por cifrado: si se pierde `ENC_KEYS`) | Documentar backups de Railway + custodia offline de `ENC_KEYS`/`BLIND_INDEX_KEY`; ejecutar y documentar un restore de prueba |
| **Media** | Sin recuperación de cuenta self-service ni verificación de email | reset self-service **NO ENCONTRADO** | Dependencia de admin; sin verificación de titularidad de correo | Implementar flujo de reset con token de un solo uso por email + verificación |
| **Baja** | SQL con f-string (no input de usuario, pero frágil) | `ml/features.py:414,425`, `ml/predict.py:478,490`, `database.py:233` | Riesgo de inyección si `periodo_cond` dejara de ser confiable | Parametrizar la condición de periodo o validarla contra un allowlist |
| **Baja** | CSRF sin tokens (solo SameSite=lax) | `config.py:69` | CSRF si cambia el modelo same-origin o SameSite | Añadir token anti-CSRF (double-submit) para POST de escritura, o documentar la dependencia de SameSite |
| **Baja** | Dependencias frontend con versiones mayores atrás; `bcrypt 3.2.2` antiguo | `frontend/package.json`; `requirements.txt` | Falta de parches/soporte | Actualizar por PR con pruebas (react/vite/tailwind uno a uno); subir bcrypt a 4.x |
| **Baja** | `ADMIN_PASSWORD` de muestra en `.env.example` | `backend/.env.example` | Copia accidental de credencial débil | Dejar el valor vacío en el ejemplo |

> No se detectaron hallazgos **Críticos** vigentes: la base de auth (argon2id, 2FA TOTP, JWT rotativo con reuse-detection, RBAC), cabeceras, gestión de secretos y cifrado de campo están implementados y son sólidos.

---

## 7. Ficha de estandarización de ESTE repo

- **Auth:** JWT HS256 en cookie HttpOnly (access 30 min + refresh 30 días rotativo con detección de reuso) + PIN idle-lock server-side | **Google OAuth:** **no** (login por password; OAuth solo para scraping AVAC/Microsoft) | **2FA:** **sí** (TOTP pyotp + códigos de recuperación hasheados)
- **DB:** PostgreSQL (Railway) / SQLAlchemy 2.0.50; dev default SQLite | **Migraciones:** artesanal `create_all` + `upgrade_tables()` (Alembic instalado pero **sin usar**) | **Cifrado en reposo:** **sí** (Fernet field-level + blind index; en transición 2.3a→2.3b)
- **Secrets:** variables de entorno (pydantic-settings) + validación en prod; `.env` no versionado; GitHub Actions secrets | **CI/CD:** **sí** (GitHub Actions: lint/tests/audit + deploy Railway/Vercel) | **Tests:** backend 49 archivos + frontend 19; cobertura mínima **60%** forzada
- **Limpieza de datos:** en ETL (`etl/transformers.py`) + sanitización NaN en `database.py`; ingesta por upload ZIP + scraping Selenium/BS4 | **Sensibilidad:** **Alta** — PII de estudiantes con **dato sensible** (autoidentificación étnica) bajo **LOPDP (Ecuador)**

---

### Apéndice — verificación
Auditoría estática sobre `main@41a0ea4`. Evidencia por `grep`/lectura de archivos citados. Elementos marcados **NO ENCONTRADO** se buscaron explícitamente y no existen en el código. No se ejecutó análisis dinámico ni pentest.
