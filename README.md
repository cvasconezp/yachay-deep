# Yachay Deep

**Learning Analytics-Driven Early Warning Decision Support System**

Sistema de inteligencia academica preventiva para la permanencia estudiantil en educacion superior virtual. Desarrollado por [Pacha Tech](mailto:cvasconezp@gmail.com).

## Descripcion

Yachay Deep integra cinco capas: Learning Analytics, Early Warning, Prediccion (ML), Explicabilidad (XAI) y Soporte a la Decision. Soporta 2,300+ estudiantes en 18 carreras virtuales.

## Stack Tecnologico

| Capa | Tecnologia |
|------|-----------|
| Backend API | FastAPI (Python 3.11) |
| Base de datos | PostgreSQL + SQLAlchemy |
| Frontend | React 18 + Vite 5 + Tailwind CSS |
| ML | scikit-learn (RandomForest, GradientBoosting) |
| Scraping | Selenium + BeautifulSoup |
| CI/CD | GitHub Actions |
| Hosting | Railway (backend) + Vercel (frontend) |

## Requisitos Previos

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+ (o SQLite para desarrollo rapido)

## Setup Local

### 1. Clonar

```bash
git clone https://github.com/cvasconezp/yachay-deep.git
cd yachay-deep
```

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac

pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env.local
# Editar .env.local con tus valores (ver tabla abajo)

cd ..
uvicorn backend.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
# http://localhost:3000
```

### 4. Docker Compose (desarrollo completo)

```bash
docker-compose up -d
```

## Variables de Entorno

| Variable | Descripcion | Requerida |
|----------|-------------|-----------|
| `DATABASE_URL` | PostgreSQL connection string | Si (prod) |
| `SECRET_KEY` | JWT secret (`openssl rand -hex 32`) | Si |
| `ADMIN_EMAIL` | Email del administrador | Si |
| `ADMIN_PASSWORD` | Password del administrador | Si |
| `DEBUG` | Modo desarrollo (True/False) | No |
| `CORS_ORIGINS` | Origenes permitidos (JSON array) | No |
| `AVAC_USERNAME` | Usuario AVAC (scraping) | Solo scraping |
| `AVAC_PASSWORD` | Password AVAC | Solo scraping |
| `AVAC_TOTP_SECRET` | TOTP secret MFA | Solo scraping |

## Estructura

```
backend/
  auth/       # JWT authentication
  etl/        # ETL pipeline
  ml/         # Machine Learning (train, predict, XAI)
  models/     # SQLAlchemy ORM models
  routes/     # API REST endpoints
  scraping/   # AVAC web scraping
  services/   # Email, etc.
frontend/
  src/
    pages/      # Dashboard, Ficha, Analytics...
    components/ # Reusable React components
    hooks/      # useAuth, useDebounce, useUrlFilters
    services/   # API client
```

## Testing

```bash
pip install pytest pytest-asyncio httpx
pytest -v
```

## Linting

```bash
pip install ruff pre-commit
ruff check backend/
pre-commit install
```

## Despliegue

Ver [DEPLOY.md](./DEPLOY.md) para Railway + Vercel.

## Licencia

Software propietario. Pacha Tech 2026.
