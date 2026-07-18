#!/usr/bin/env bash
# Build Continuum Docker image locally
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

TAG="${IMAGE_TAG:-continuum:local}"

echo "Building ${TAG} from ${ROOT}"
docker build -t "${TAG}" .

echo "Done. Run: ./infra/scripts/run-local.sh"
