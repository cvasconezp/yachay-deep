# Core — Yachay Deep

**Sistema de Alerta Temprana Académica basado en Learning Analytics**

> **Core** · un producto de Yachay Deep Labs · Badge de ciclo de vida: **`INSIGNIA`** — *Fase 6 (integración LMS en tiempo real) en curso; no es un producto "100 % terminado".*

[![CI/CD](https://github.com/cvasconezp/yachay-deep/actions/workflows/daily_scraping.yml/badge.svg)](https://github.com/cvasconezp/yachay-deep/actions)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![React 18](https://img.shields.io/badge/react-18-61dafb.svg)](https://react.dev/)
[![License: Proprietary](https://img.shields.io/badge/license-proprietary-red.svg)](#licencia)

---

## Descripción

Yachay Deep es un sistema de inteligencia académica preventiva diseñado para la permanencia estudiantil en educación superior virtual. Integra cinco capas de Learning Analytics para detectar estudiantes en riesgo, predecir deserción y reprobación, explicar las causas, recomendar acciones y medir el impacto de las intervenciones.

### Las 5 capas

1. **Analítica descriptiva y diagnóstica** — Dashboard, fichas, indicadores por carrera, asignatura y docente
2. **Analítica predictiva** — Modelos ML de deserción y reprobación por carrera (LogisticRegression vs RandomForest)
3. **Explicabilidad (XAI)** — Contribuciones por feature tipo SHAP + contrafactuales ("¿qué pasaría si…?")
4. **Recomendaciones automáticas** — Motor de 10 categorías de acción con prioridad y medio de contacto sugerido
5. **Intervenciones y ciclo cerrado** — Registro, workflow, snapshots antes/después y medición de impacto

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Backend API | FastAPI · Python 3.11 |
| Base de datos | PostgreSQL 15 · SQLAlchemy ORM |
| Frontend | React 18 · Vite 5 · Tailwind CSS |
| Machine Learning | scikit-learn (LogisticRegression, RandomForest) |
| Scraping | Selenium · BeautifulSoup · SSO + TOTP |
| CI/CD | GitHub Actions (tests + scraping diario) |
| Hosting | Railway (backend + BD) · Vercel (frontend) |
| Calidad | Ruff · pre-commit · pytest (cobertura mínima 60% forzada) · `pip-audit`/`npm audit` bloqueantes en CI |

---

## Arquitectura

```
┌─────────────┐     HTTPS      ┌──────────────┐     TLS     ┌────────────┐
│  React SPA  │ ──────────────▶ │  FastAPI API  │ ──────────▶ │ PostgreSQL │
│  (Vercel)   │                 │  (Railway)    │             │ (Railway)  │
└─────────────┘                 └──────┬───────┘             └────────────┘
                                       │
                          ┌────────────┼────────────┐
                          │            │            │
                     ETL Pipeline   ML Engine   Scraping
                     (11 pasos)    (XAI+Rec)   (Moodle)
```

---

## Estructura del proyecto

```
yachay-deep/
├── backend/
│   ├── auth/           # Autenticación JWT + RBAC (4 roles)
│   ├── etl/            # Pipeline ETL (4,046 líneas, 11 pasos)
│   ├── ml/             # ML: entrenamiento, predicción, XAI, contrafactuales (2,503 líneas)
│   ├── models/         # Modelos SQLAlchemy ORM (conteo autogenerado en CI)
│   ├── routes/         # Módulos de rutas REST (conteo autogenerado en CI)
│   │   └── analytics/  # 13 sub-módulos de analítica
│   ├── scraping/       # Scraping Moodle con Selenium (1,158 líneas)
│   └── services/       # Email, utilidades
├── frontend/
│   └── src/
│       ├── pages/      # 16 páginas (Dashboard, Ficha 360°, Admin, Analytics…)
│       ├── components/ # Componentes React reutilizables
│       ├── hooks/      # useAuth, useIdleTimer, useDebounce, useUrlFilters
│       └── services/   # Cliente API
├── docs/               # Documentación (ver carta de navegación en PRODUCT.md)
│   ├── PRODUCT.md · ROADMAP.md
│   ├── ARCHITECTURE.md · API.md · MODULES.md · DATA_DICTIONARY.md
│   ├── SECURITY.md · SECURITY_INFRA_CHECKLIST.md · DEPLOYMENT.md
│   ├── USER_GUIDE.md · ADMIN_GUIDE.md
│   ├── AUDITS/          # auditorías e inventarios
├── Dockerfile          # Build de producción (Railway)
├── docker-compose.yml  # Entorno de desarrollo local
├── requirements.txt    # Dependencias Python
├── pytest.ini          # Configuración de tests
├── ruff.toml           # Configuración del linter
└── .pre-commit-config.yaml
```

---

## Inicio rápido

### Requisitos previos

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+ (o Docker)

### Con Docker (recomendado)

```bash
git clone https://github.com/cvasconezp/yachay-deep.git
cd yachay-deep
docker-compose up -d
# API: http://localhost:8000
# Frontend: http://localhost:3000
```

### Setup manual

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env.local   # Editar con tus valores
cd ..
uvicorn backend.main:app --reload --port 8000

# Frontend (otra terminal)
cd frontend
npm install
npm run dev
```

---

## Variables de entorno

| Variable | Descripción | Requerida |
|---|---|---|
| `DATABASE_URL` | Connection string PostgreSQL | Sí (prod) |
| `SECRET_KEY` | JWT secret (`openssl rand -hex 32`) | Sí |
| `ADMIN_EMAIL` | Email del administrador inicial | Sí |
| `ADMIN_PASSWORD` | Password del administrador | Sí |
| `DEBUG` | Modo desarrollo (`True`/`False`) | No |
| `CORS_ORIGINS` | Orígenes permitidos (JSON array) | No |
| `MOODLE_USERNAME` | Usuario Moodle para scraping | Solo scraping |
| `MOODLE_PASSWORD` | Password Moodle | Solo scraping |
| `MOODLE_TOTP_SECRET` | Secret TOTP para MFA | Solo scraping |

---

## Testing

```bash
pytest -v                     # Suite completa
pytest tests/test_security*   # Solo tests de seguridad
pytest --cov=backend --cov-fail-under=60   # Con cobertura (umbral mínimo 60%)
```

---

## Documentación — carta de navegación

Punto de entrada: **[docs/PRODUCT.md](./docs/PRODUCT.md)** (qué es Core y a futuro).

| Documento | Contenido | Estado |
|---|---|---|
| [PRODUCT.md](./docs/PRODUCT.md) | Qué es el producto, motor, capas, límites | ✅ vigente |
| [ROADMAP.md](./docs/ROADMAP.md) | Fases, pendientes y visión | ✅ vigente |
| [ARCHITECTURE.md](./docs/ARCHITECTURE.md) | Arquitectura, stack, esquema BD, decisiones | ✅ vigente |
| [API.md](./docs/API.md) | Referencia de endpoints (métodos, rutas, roles) | ✅ vigente |
| [MODULES.md](./docs/MODULES.md) | Módulos funcionales | ✅ vigente |
| [GUIA_MODULOS_Y_HALLAZGOS.md](./docs/GUIA_MODULOS_Y_HALLAZGOS.md) | **Guía maestra**: patrones, convenciones y hallazgos de datos para construir módulos nuevos | ✅ vigente |
| [DATA_DICTIONARY.md](./docs/DATA_DICTIONARY.md) | Tablas + §8 diccionario de métricas | ✅ vigente |
| [SECURITY.md](./docs/SECURITY.md) | Seguridad, auth, cifrado, OWASP, LOPDP | ✅ vigente |
| [SECURITY_INFRA_CHECKLIST.md](./docs/SECURITY_INFRA_CHECKLIST.md) | Checklist de infraestructura | ✅ vigente |
| [DEPLOYMENT.md](./docs/DEPLOYMENT.md) | Despliegue Railway + Vercel + env vars | ✅ vigente |
| [USER_GUIDE.md](./docs/USER_GUIDE.md) | Guía de monitores/coordinadores/docentes | ✅ vigente |
| [ADMIN_GUIDE.md](./docs/ADMIN_GUIDE.md) | Guía de administradores (usuarios, ETL, config) | ✅ vigente |
| [AUDITS/](./docs/AUDITS/) | Auditorías (técnica, marca) e inventario de métricas | ✅ vigente |
| [CHANGELOG.md](./CHANGELOG.md) · [CONTRIBUTING.md](./CONTRIBUTING.md) · [LICENSE](./LICENSE) | Cambios · contribución · licencia | ✅ vigente |

---

- JWT en cookies `HttpOnly` + `Secure` + `SameSite`; access 30 min + refresh 30 días rotativo con detección de reuso
- **argon2id** para hashing de contraseñas (bcrypt legacy con rehash transparente); PIN de bloqueo por inactividad
- **2FA TOTP** con códigos de recuperación hasheados (`REQUIRE_2FA` / `REQUIRE_ADMIN_2FA`)
- **Cifrado en reposo** de PII sensible (Fernet field-level + blind index): cédula, etnia, domicilio, `totp_secret`. ⚠️ Contract 2.3b (drop del texto plano huérfano) **pendiente** — requiere backup verificado.
- RBAC con 4 roles y aislamiento multi-tenant por contexto
- Security headers (CSP, HSTS, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy)
- Rate limiting en endpoints de autenticación *(pendiente: extender a refresh/uploads con store persistente)*
- **Logging seguro:** correos enmascarados en logs; el cliente recibe error genérico (`{"detail":"Error interno"}`), la traza solo va a logs
- **CI:** `pip-audit` / `npm audit` bloqueantes

Ver [SECURITY.md](./docs/SECURITY.md) para detalles completos.

---

## Métricas (estándar de la casa)

- **Cifra de impacto (fuente única):** `GET /metrics/impact` computa `estudiantes_monitoreados` y `programas_activos` desde la BD. La landing **lee** esa cifra (`frontend/src/pages/Landing.jsx`); no hay número de impacto hardcodeado como "cifra oficial".
- **Telemetría de uso:** pseudonimizada (actor por HMAC, sin PII), en tabla aislada `usage_events` (`backend/services/telemetry.py`). Eventos: `login`, `dashboard_view`, `ficha360_view`, `alerta_vista`, `recomendacion_vista`, `intervencion_creada`, `intervencion_cerrada`, `export_generado`.
- **Diccionario de métricas versionado:** `docs/DATA_DICTIONARY.md` §8 (nombre · definición · fórmula · fuente · cadencia · dueño · clase · versión).

---

## Licencia

Software propietario. © 2026 [Yachay Deep](mailto:cvasconezp@gmail.com). Todos los derechos reservados.
