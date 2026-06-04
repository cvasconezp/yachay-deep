# Yachay Deep — Guía de Deployment

## Resumen del stack

| Componente | Tecnología | Hosting |
|------------|-----------|---------|
| Backend API | FastAPI (Python) | Railway |
| Base de datos | PostgreSQL | Railway |
| Frontend | React + Tailwind | Vercel |
| Scraping automático | GitHub Actions | GitHub |

---

## Paso 1: Preparar el repositorio GitHub

```bash
# En tu máquina local
git init yachay-deep-webapp
cd yachay-deep-webapp
# Copia todos los archivos de este proyecto aquí
git add .
git commit -m "Initial commit: Yachay Deep web app"
git remote add origin https://github.com/TU_USUARIO/yachay-deep.git
git push -u origin main
```

---

## Paso 2: Configurar GitHub Secrets

En tu repo de GitHub → Settings → Secrets and variables → Actions, agrega:

| Secret | Valor |
|--------|-------|
| `MOODLE_USERNAME` | Tu usuario de Moodle |
| `MOODLE_PASSWORD` | Tu contraseña de Moodle |
| `MOODLE_BASE_URL` | `https://moodle.ejemplo.edu.ec` |
| `DATABASE_URL` | Lo obtienes en el Paso 3 |

---

## Paso 3: Desplegar backend en Railway

1. Ir a [railway.app](https://railway.app) → New Project
2. Deploy from GitHub repo → selecciona tu repositorio
3. Agrega un servicio **PostgreSQL** → Railway lo aprovisiona automáticamente
4. En el servicio de tu app, configura las variables de entorno:

```
DATABASE_URL=         (Railway lo conecta automáticamente)
SECRET_KEY=           (genera con: openssl rand -hex 32)
ADMIN_EMAIL=          cvasconezp@gmail.com
ADMIN_PASSWORD=       Tu contraseña segura
MOODLE_USERNAME=        Tu usuario Moodle
MOODLE_PASSWORD=        Tu contraseña Moodle
DATA_PATH_INGRESOS=   ./data/IngresosMoodle
DATA_PATH_TAREAS=     ./data/Tareas
DATA_PATH_CALIFICACIONES= ./data/calificaciones.csv
CORS_ORIGINS=         ["https://yachay-deep.vercel.app"]
```

5. Railway despliega automáticamente. Anota la URL generada (ej: `yachay-deep-api.railway.app`)

---

## Paso 4: Desplegar frontend en Vercel

1. Ir a [vercel.com](https://vercel.com) → New Project → Import desde GitHub
2. Framework preset: **Vite**
3. Root directory: `frontend`
4. Agrega la variable de entorno:
   ```
   VITE_API_URL = https://TU-URL.railway.app
   ```
5. Deploy → Vercel genera una URL (ej: `yachay-deep.vercel.app`)

6. Actualiza `CORS_ORIGINS` en Railway con esa URL de Vercel.

---

## Paso 5: Primera ejecución

1. Abre `https://yachay-deep.vercel.app`
2. Login con las credenciales de admin que configuraste
3. Ve a **Administración** → **Ejecutar ETL Manual** para cargar los primeros datos

Para cargar datos iniciales, copia tus CSV existentes a la carpeta `data/` en Railway
(o sube la carpeta a tu repo temporalmente para el primer ETL).

---

## Paso 6: Automatizar el scraping

El workflow `.github/workflows/daily_scraping.yml` ya está configurado para correr:
- **Automáticamente**: Lunes a viernes a las 06:00 hora Ecuador
- **Manualmente**: GitHub → Actions → Daily Moodle Scraping → Run workflow

El scraping:
1. Corre en GitHub Actions (servidor en la nube)
2. Hace login headless en Moodle con tus credenciales
3. Descarga todos los cursos
4. Llama al ETL para actualizar la BD en Railway
5. Tú abres la app y los datos ya están frescos

---

## Desarrollo local

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edita .env con tus valores
uvicorn backend.main:app --reload

# Frontend (en otra terminal)
cd frontend
npm install
cp .env.example .env.local
# VITE_API_URL=http://localhost:8000
npm run dev
```

API disponible en: http://localhost:8000
Documentación automática: http://localhost:8000/docs
Frontend: http://localhost:3000

---

## Credenciales por defecto

Al iniciar por primera vez, se crea el admin:
- Email: `cvasconezp@gmail.com` (o el que configures en ADMIN_EMAIL)
- Password: el que configures en ADMIN_PASSWORD

**Cambia la contraseña inmediatamente en producción.**
