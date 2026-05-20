# Yachay Deep

**Sistema de Alerta Temprana Académica basado en Learning Analytics**

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
| Calidad | Ruff · pre-commit · pytest (330+ tests) |

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
                     (11 pasos)    (XAI+Rec)   (AVAC/Moodle)
```

---

## Estructura del proyecto

```
yachay-deep/
├── backend/
│   ├── auth/           # Autenticación JWT + RBAC (4 roles)
│   ├── etl/            # Pipeline ETL (4,046 líneas, 11 pasos)
│   ├── ml/             # ML: entrenamiento, predicción, XAI, contrafactuales (2,503 líneas)
│   ├── models/         # 16+ modelos SQLAlchemy ORM
│   ├── routes/         # 14 módulos de rutas (125 endpoints)
│   │   └── analytics/  # 13 sub-módulos de analítica
│   ├── scraping/       # Scraping AVAC con Selenium (1,158 líneas)
│   └── services/       # Email, utilidades
├── frontend/
│   └── src/
│       ├── pages/      # 16 páginas (Dashboard, Ficha 360°, Admin, Analytics…)
│       ├── components/ # Componentes React reutilizables
│       ├── hooks/      # useAuth, useIdleTimer, useDebounce, useUrlFilters
│       └── services/   # Cliente API
├── docs/               # Documentación técnica completa
│   ├── ARCHITECTURE.md
│   ├── API.md
│   ├── DATA_DICTIONARY.md
│   ├── MODULES.md
│   ├── SECURITY_FRAMEWORK.md
│   └── DEPLOY.md
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
| `AVAC_USERNAME` | Usuario AVAC para scraping | Solo scraping |
| `AVAC_PASSWORD` | Password AVAC | Solo scraping |
| `AVAC_TOTP_SECRET` | Secret TOTP para MFA | Solo scraping |

---

## Testing

```bash
pytest -v                     # Suite completa (330+ tests)
pytest tests/test_security*   # Solo tests de seguridad (5 suites)
pytest --cov=backend          # Con cobertura
```

---

## Documentación

La documentación técnica completa está en [`docs/`](./docs/):

| Documento | Contenido |
|---|---|
| [ARCHITECTURE.md](./docs/ARCHITECTURE.md) | Arquitectura del sistema, stack, esquema BD, decisiones técnicas |
| [API.md](./docs/API.md) | Referencia de los 125 endpoints con métodos, rutas y roles |
| [DATA_DICTIONARY.md](./docs/DATA_DICTIONARY.md) | 18 tablas documentadas columna por columna |
| [MODULES.md](./docs/MODULES.md) | 17 módulos funcionales con páginas, APIs y features |
| [SECURITY_FRAMEWORK.md](./docs/SECURITY_FRAMEWORK.md) | Autenticación, RBAC, cifrado, protección contra ataques |
| [DEPLOY.md](./docs/DEPLOY.md) | Guía paso a paso para Railway + Vercel |

---

## Seguridad

- JWT en cookies `HttpOnly` + `Secure` + `SameSite`
- BCrypt para hashing de contraseñas y PINs
- RBAC con 4 roles y aislamiento de datos por contexto
- Rate limiting en endpoints de autenticación
- Security headers (CSP, HSTS, X-Frame-Options)
- PIN de bloqueo por inactividad (5 min)
- 5 suites de tests de seguridad automatizados

Ver [SECURITY_FRAMEWORK.md](./docs/SECURITY_FRAMEWORK.md) para detalles completos.

---

## Licencia

Software propietario. © 2026 [PachaTech](mailto:cvasconezp@gmail.com). Todos los derechos reservados.
