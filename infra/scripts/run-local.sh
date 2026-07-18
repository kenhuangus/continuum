#!/usr/bin/env bash
# Run Continuum via docker compose (local smoke)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  echo "WARNING: .env not found — copy .env.example to .env first" >&2
fi

echo "Starting Continuum on http://127.0.0.1:8000/"
docker compose up --build
