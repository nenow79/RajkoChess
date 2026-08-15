#!/usr/bin/env bash

set -Eeuo pipefail

HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/api/health}"
HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-10}"

response="$(curl \
  --fail \
  --silent \
  --show-error \
  --max-time "$HEALTH_TIMEOUT_SECONDS" \
  "$HEALTH_URL")"

echo "Rajko Chess gotowy: $response"
