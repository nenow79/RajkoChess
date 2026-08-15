#!/usr/bin/env bash

set -Eeuo pipefail

ENV_FILE="${ENV_FILE:-}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/rajko-chess}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"

if [[ -z "$ENV_FILE" && -r /etc/rajko-chess/backend.env ]]; then
  ENV_FILE=/etc/rajko-chess/backend.env
fi

if [[ ! "$BACKUP_RETENTION_DAYS" =~ ^[0-9]+$ ]] || ((BACKUP_RETENTION_DAYS < 1)); then
  echo "BACKUP_RETENTION_DAYS musi być dodatnią liczbą całkowitą" >&2
  exit 1
fi

for command in pg_dump pg_restore sha256sum install mktemp find; do
  command -v "$command" >/dev/null || {
    echo "Brak wymaganej komendy: $command" >&2
    exit 1
  }
done

if [[ -n "$ENV_FILE" ]]; then
  if [[ ! -r "$ENV_FILE" ]]; then
    echo "Nie można odczytać konfiguracji: $ENV_FILE" >&2
    exit 1
  fi
  set -a
  # Plik jest zarządzany przez administratora serwera i powinien mieć tryb 0600.
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

for variable_name in POSTGRES_HOST POSTGRES_PORT POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD; do
  if [[ -z "${!variable_name:-}" ]]; then
    echo "Brak wymaganej zmiennej: $variable_name" >&2
    exit 1
  fi
done

install -d -m 0700 "$BACKUP_DIR"
umask 077

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive="$BACKUP_DIR/rajko-chess-$timestamp.dump"
temporary_archive="$(mktemp "$BACKUP_DIR/.rajko-chess-$timestamp.XXXXXX")"
temporary_checksum="$temporary_archive.sha256"

cleanup() {
  rm -f -- "$temporary_archive" "$temporary_checksum"
}
trap cleanup EXIT

export PGPASSWORD="$POSTGRES_PASSWORD"
export PGSSLMODE="${POSTGRES_SSLMODE:-prefer}"

pg_dump \
  --host "$POSTGRES_HOST" \
  --port "$POSTGRES_PORT" \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --format custom \
  --compress 9 \
  --no-owner \
  --no-privileges \
  --file "$temporary_archive"

# Nie uznajemy pliku za backup, dopóki pg_restore nie potrafi odczytać katalogu.
pg_restore --list "$temporary_archive" >/dev/null
mv -- "$temporary_archive" "$archive"
sha256sum "$archive" >"$temporary_checksum"
mv -- "$temporary_checksum" "$archive.sha256"

find "$BACKUP_DIR" -maxdepth 1 -type f \
  \( -name 'rajko-chess-*.dump' -o -name 'rajko-chess-*.dump.sha256' \) \
  -mtime "+$BACKUP_RETENTION_DAYS" -delete

echo "Utworzono i sprawdzono backup: $archive"
