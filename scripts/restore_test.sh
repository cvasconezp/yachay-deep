#!/usr/bin/env bash
# WF2 — Drill de restauración (NUNCA contra producción).
# Restaura un backup a una BD de prueba aislada y corre 3 consultas de control.
#
# Uso:  ./scripts/restore_test.sh yachay_YYYYMMDD_HHMMSS.sql.gz
#
# Variables:
#   TEST_DB_URL   (opcional) URL postgres de la BD de prueba.
#                 Default: postgresql://localhost/yachay_restore_test (createdb local)
#   BACKUP_ENCRYPT_KEY  (opcional) clave si el dump está cifrado (.enc)
set -euo pipefail

BACKUP_FILE="${1:?Pasa la ruta del backup: ./scripts/restore_test.sh archivo.sql.gz}"
[ -f "$BACKUP_FILE" ] || { echo "❌ No existe $BACKUP_FILE"; exit 1; }

TEST_DB="${TEST_DB_URL:-}"
LOCAL_DB="yachay_restore_test"

echo "🧪 Drill de restauración — $(date)"

# Descifrar si aplica
WORK="$BACKUP_FILE"
if [[ "$BACKUP_FILE" == *.enc ]]; then
  : "${BACKUP_ENCRYPT_KEY:?Backup cifrado: define BACKUP_ENCRYPT_KEY}"
  WORK="${BACKUP_FILE%.enc}"
  openssl enc -d -aes-256-cbc -pbkdf2 -in "$BACKUP_FILE" -out "$WORK" -pass "pass:${BACKUP_ENCRYPT_KEY}"
fi

if [ -z "$TEST_DB" ]; then
  echo "🆕 Creando BD local de prueba: $LOCAL_DB"
  dropdb --if-exists "$LOCAL_DB"
  createdb "$LOCAL_DB"
  TEST_DB="$LOCAL_DB"
fi

echo "♻️  Restaurando en BD de prueba…"
gunzip -c "$WORK" | psql "$TEST_DB" >/dev/null

echo "🔎 Consultas de control:"
psql "$TEST_DB" -c "SELECT count(*) AS estudiantes      FROM students;"
psql "$TEST_DB" -c "SELECT count(*) AS intervenciones   FROM interventions;"
psql "$TEST_DB" -c "SELECT max(periodo) AS ultimo_periodo FROM grades;"

echo "🧹 Limpieza"
if [ "$TEST_DB" = "$LOCAL_DB" ]; then dropdb --if-exists "$LOCAL_DB"; fi
[ "$WORK" != "$BACKUP_FILE" ] && rm -f "$WORK" || true

echo "✅ Drill completado. Registra fecha, tamaño, tiempo y resultado en la bitácora."
