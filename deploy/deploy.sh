#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_DIR="$PROJECT_DIR/.venv"

SERVICE_NAME="${SERVICE_NAME:-rajko-chess-backend.service}"
WEB_ROOT="${WEB_ROOT:-/var/www/rajko-chess/chess}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/api/position}"
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

for command in git python3 npm rsync curl sudo systemctl nginx; do
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
  git pull --no-rebase
fi

log "Przygotowanie środowiska backendu"
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/python" -m pip install -r "$PROJECT_DIR/backend/requirements.txt"
"$VENV_DIR/bin/python" -m compileall -q "$PROJECT_DIR/backend"

log "Instalacja zależności i budowanie frontendu"
npm --prefix "$FRONTEND_DIR" ci
npm --prefix "$FRONTEND_DIR" run build

log "Publikowanie frontendu w $WEB_ROOT"
sudo mkdir -p "$WEB_ROOT"
sudo rsync -a --delete "$FRONTEND_DIR/dist/" "$WEB_ROOT/"

log "Restart API"
sudo systemctl restart "$SERVICE_NAME"

log "Sprawdzanie API"
api_ready=0
for attempt in {1..15}; do
  if curl --fail --silent --show-error --max-time 3 "$HEALTH_URL" >/dev/null; then
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

log "Sprawdzanie i przeładowanie Nginx"
sudo nginx -t
sudo systemctl reload nginx

log "Wdrożenie zakończone pomyślnie"
git log -1 --oneline

