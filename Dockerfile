# syntax=docker/dockerfile:1
# Railway deployment: secrets are injected at RUNTIME via env vars only.
# No ARG/ENV for sensitive values to avoid Docker build scanner warnings.

FROM python:3.11-slim

WORKDIR /app

# System deps (psycopg2 needs libpq-dev, gcc for compilation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python deps (leverage layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# PORT is set by Railway at runtime - expose default
EXPOSE 8080

# Start command is set via railway.json startCommand (overrides CMD)
# Fallback for local docker run
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
