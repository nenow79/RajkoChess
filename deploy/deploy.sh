#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_DIR="$PROJECT_DIR/.venv"

SERVICE_NAME="${SERVICE_NAME:-rajko-chess-backend.service}"
WEB_ROOT="${WEB_ROOT:-/var/www/rajko-chess/chess}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/api/health}"
BACKEND_ENV_FILE="${BACKEND_ENV_FILE:-/etc/rajko-chess/backend.env}"
PULL_CHANGES=1

usage() {
  cat <<'EOF'
Użycie: deploy/deploy.sh [--no-pull]

Aktualizuje repozytorium, zależności, backend i produkcyjny frontend Rajko Chess.

Opcje:
  --no-pull  wdrożenie aktualnego lokalnego kodu bez pobierania zmian z Git
  -h, --help pokazanie tej pomocy

Zmienne środowiskowe:
  SERVICE_NAME  nazwa usługi systemd (domyślnie rajko-chess-backend.service)
  WEB_ROOT      katalog frontendu Nginx (domyślnie /var/www/rajko-chess/chess)
  HEALTH_URL    adres używany do kontroli API
  BACKEND_ENV_FILE  produkcyjny plik env (domyślnie /etc/rajko-chess/backend.env)
EOF
}

while (($#)); do
  case "$1" in
    --no-pull) PULL_CHANGES=0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Nieznana opcja: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

log() {
  printf '\n==> %s\n' "$*"
}

load_backend_environment() {
  if ! sudo test -r "$BACKEND_ENV_FILE"; then
    echo "Brak czytelnej konfiguracji: $BACKEND_ENV_FILE" >&2
    exit 1
  fi

  set -a
  # Plik pozostaje własnością roota z trybem 0600; jego treść nie trafia do repo.
  # shellcheck disable=SC1090
  source <(sudo cat -- "$BACKEND_ENV_FILE")
  set +a
}

for command in git python3 npm rsync curl sudo systemctl nginx pg_dump pg_restore; do
  command -v "$command" >/dev/null || {
    echo "Brak wymaganej komendy: $command" >&2
    exit 1
  }
done

cd "$PROJECT_DIR"

if ((PULL_CHANGES)); then
  if [[ -n "$(git status --porcelain)" ]]; then
    echo "Repozytorium ma niezapisane zmiany. Zacommituj je albo użyj --no-pull." >&2
    exit 1
  fi
  log "Pobieranie i scalanie zmian z Git"
  git pull --ff-only
fi

log "Przygotowanie środowiska backendu"
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/python" -m pip install -r "$PROJECT_DIR/backend/requirements.txt"
"$VENV_DIR/bin/python" -m compileall -q "$PROJECT_DIR/backend"

log "Testy backendu"
(
  cd "$PROJECT_DIR/backend"
  "$VENV_DIR/bin/python" -m unittest discover -s tests
)

log "Kontrola PostgreSQL i Redis"
(
  load_backend_environment
  cd "$PROJECT_DIR/backend"
  "$VENV_DIR/bin/python" -m scripts.check_database
  "$VENV_DIR/bin/python" -m scripts.check_redis
  "$VENV_DIR/bin/python" -m scripts.check_rate_limits
)

log "Instalacja zależności i budowanie frontendu"
npm --prefix "$FRONTEND_DIR" ci
npm --prefix "$FRONTEND_DIR" run lint
npm --prefix "$FRONTEND_DIR" run build

log "Sprawdzanie konfiguracji Nginx"
sudo nginx -t

log "Backup PostgreSQL przed migracją"
sudo ENV_FILE="$BACKEND_ENV_FILE" \
  "$PROJECT_DIR/deploy/backup-postgres.sh"

log "Aktualizacja schematu PostgreSQL"
(
  load_backend_environment
  cd "$PROJECT_DIR/backend"
  "$VENV_DIR/bin/alembic" upgrade head
)

log "Publikowanie frontendu w $WEB_ROOT"
sudo mkdir -p "$WEB_ROOT"
sudo rsync -a --delete "$FRONTEND_DIR/dist/" "$WEB_ROOT/"

log "Restart API"
sudo systemctl restart "$SERVICE_NAME"

log "Sprawdzanie API"
api_ready=0
for attempt in {1..15}; do
  if curl --fail --silent --show-error --max-time 10 "$HEALTH_URL" >/dev/null; then
    api_ready=1
    break
  fi
  sleep 1
done
if ((api_ready == 0)); then
  sudo systemctl --no-pager --full status "$SERVICE_NAME" || true
  echo "API nie odpowiedziało pod adresem $HEALTH_URL" >&2
  exit 1
fi

log "Przeładowanie Nginx"
sudo systemctl reload nginx

log "Wdrożenie zakończone pomyślnie"
git log -1 --oneline
