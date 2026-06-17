#!/usr/bin/env bash
# WF2 — Respaldo manual de la base de datos Yachay Deep.
# Úsalo ANTES de migraciones grandes o despliegues riesgosos.
#
# Requisitos: pg_dump (cliente postgres) y, opcionalmente, rclone o aws-cli
# para subir la copia a R2/S3.
#
# Variables de entorno:
#   DATABASE_URL         (obligatoria) cadena de conexión postgres
#   BACKUP_DIR           (opcional) carpeta destino local (default: ./backups)
#   BACKUP_REMOTE        (opcional) destino rclone, ej: "r2:yachay-backups"
#   BACKUP_ENCRYPT_KEY   (opcional) si se define, cifra el dump con AES-256 (openssl)
set -euo pipefail

: "${DATABASE_URL:?Define DATABASE_URL}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$BACKUP_DIR"

TS="$(date +%Y%m%d_%H%M%S)"
OUT="$BACKUP_DIR/yachay_${TS}.sql.gz"

echo "📦 Generando dump → $OUT"
pg_dump "$DATABASE_URL" | gzip > "$OUT"

if [ -n "${BACKUP_ENCRYPT_KEY:-}" ]; then
  echo "🔐 Cifrando (AES-256)…"
  openssl enc -aes-256-cbc -salt -pbkdf2 -in "$OUT" -out "${OUT}.enc" -pass "pass:${BACKUP_ENCRYPT_KEY}"
  rm -f "$OUT"
  OUT="${OUT}.enc"
fi

SIZE="$(du -h "$OUT" | cut -f1)"
echo "✅ Backup local listo: $OUT ($SIZE)"

if [ -n "${BACKUP_REMOTE:-}" ]; then
  echo "☁️  Subiendo a $BACKUP_REMOTE …"
  rclone copy "$OUT" "$BACKUP_REMOTE" --progress
  echo "✅ Copia remota subida."
else
  echo "ℹ️  BACKUP_REMOTE no definido: solo copia local. Define una 2ª copia en R2/S3."
fi
