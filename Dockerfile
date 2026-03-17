# syntax=docker/dockerfile:1
# Railway deployment: secrets are injected at RUNTIME via env vars only.

FROM python:3.11-slim

WORKDIR /app

# System deps (psycopg2 needs libpq-dev, gcc for compilation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy ALL requirements files (root may reference backend/ via -r)
COPY requirements.txt .
COPY backend/requirements.txt backend/
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# PORT is set by Railway at runtime
EXPOSE 8080
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
