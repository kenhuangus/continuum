#!/usr/bin/env bash
# Smoke test: GET /v1/health
set -euo pipefail

BASE_URL="${CONTINUUM_URL:-http://127.0.0.1:8000}"
URL="${BASE_URL}/v1/health"

echo "GET ${URL}"
curl -fsS "${URL}"
echo
