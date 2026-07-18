#!/usr/bin/env bash
# Tag and push continuum:local to Alibaba Container Registry.
# Set env vars before running (no secrets in this script):
#   REGISTRY, NAMESPACE, REGION, TAG (optional)
set -euo pipefail

REGISTRY="${REGISTRY:?Set REGISTRY to your ACR instance id}"
NAMESPACE="${NAMESPACE:?Set NAMESPACE to your ACR namespace}"
REGION="${REGION:-ap-southeast-1}"
IMAGE="${IMAGE:-continuum}"
TAG="${TAG:-latest}"
LOCAL_TAG="${LOCAL_TAG:-continuum:local}"

REMOTE="${REGISTRY}.${REGION}.cr.aliyuncs.com/${NAMESPACE}/${IMAGE}:${TAG}"

echo "Tagging ${LOCAL_TAG} -> ${REMOTE}"
docker tag "${LOCAL_TAG}" "${REMOTE}"

echo "Pushing ${REMOTE}"
docker push "${REMOTE}"

echo "Done. Pull on ECS with:"
echo "  docker pull ${REMOTE}"
