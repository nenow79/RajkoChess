#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="$ROOT_DIR/.venv"

BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
SKIP_INSTALL="${SKIP_INSTALL:-0}"

pids=()

cleanup() {
  echo
  echo "Zatrzymuję frontend i backend..."
  for pid in "${pids[@]:-}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Brakuje komendy: $1"
    exit 1
  fi
}

trap cleanup INT TERM EXIT

require_command python3
require_command npm

LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
if [[ -z "$LAN_IP" ]]; then
  LAN_IP="ADRES_IP_TEGO_KOMPUTERA"
fi

if [[ "$SKIP_INSTALL" != "1" ]]; then
  if [[ ! -d "$VENV_DIR" ]]; then
    echo "Tworzę środowisko Python: $VENV_DIR"
    python3 -m venv "$VENV_DIR"
  fi

  echo "Instaluję zależności backendu..."
  "$VENV_DIR/bin/python" -m pip install -r "$BACKEND_DIR/requirements.txt"

  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    echo "Instaluję zależności frontendu..."
    (cd "$FRONTEND_DIR" && npm install)
  fi
fi

echo "Uruchamiam backend: http://$BACKEND_HOST:$BACKEND_PORT"
(
  cd "$BACKEND_DIR"
  "$VENV_DIR/bin/python" -m uvicorn main:app --reload --host "$BACKEND_HOST" --port "$BACKEND_PORT"
) &
pids+=("$!")

echo "Uruchamiam frontend: http://$FRONTEND_HOST:$FRONTEND_PORT"
(
  cd "$FRONTEND_DIR"
  VITE_BACKEND_PROXY_TARGET="http://127.0.0.1:$BACKEND_PORT" npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"
) &
pids+=("$!")

echo
echo "Gotowe."
echo "Na tym komputerze: http://127.0.0.1:$FRONTEND_PORT"
echo "Z innego urządzenia w tym samym Wi-Fi: http://$LAN_IP:$FRONTEND_PORT"
echo "Naciśnij Ctrl+C, żeby zatrzymać oba serwery."

wait -n "${pids[@]}"
