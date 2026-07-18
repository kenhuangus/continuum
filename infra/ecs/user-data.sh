#!/bin/bash
# cloud-init user-data for Ubuntu 22.04 ECS — installs Docker and runs Continuum.
# Replace placeholders before use: IMAGE_URI, or build from git clone URL.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y ca-certificates curl gnupg lsb-release git

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

systemctl enable docker
systemctl start docker

mkdir -p /app/data
chmod 755 /app/data

# Operator must create /etc/continuum.env on the instance (see DEPLOY.md).
# Example:
#   DASHSCOPE_API_KEY=your_key_here
#   CONTINUUM_AUTH_DISABLED=0
#   CONTINUUM_API_KEYS=your_public_demo_key
#   CONTINUUM_CORS_ORIGINS=https://your-public-host:8000

if [ ! -f /etc/continuum.env ]; then
  cat > /etc/continuum.env <<'EOF'
# Replace with real values before exposing the instance publicly.
DASHSCOPE_API_KEY=
CONTINUUM_AUTH_DISABLED=1
CONTINUUM_DB_PATH=/app/data/continuum.db
EOF
  chmod 600 /etc/continuum.env
fi

IMAGE_URI="${CONTINUUM_IMAGE:-continuum:local}"

# Option A: pull from ACR (set CONTINUUM_IMAGE in user-data or cloud-init vars)
if [[ "$IMAGE_URI" == *".aliyuncs.com/"* ]]; then
  docker pull "$IMAGE_URI"
else
  # Option B: build from git (set CONTINUUM_GIT_URL)
  if [ -n "${CONTINUUM_GIT_URL:-}" ]; then
    git clone --depth 1 "$CONTINUUM_GIT_URL" /opt/continuum
    docker build -t continuum:local /opt/continuum
    IMAGE_URI="continuum:local"
  fi
fi

docker rm -f continuum 2>/dev/null || true

docker run -d \
  --name continuum \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file /etc/continuum.env \
  -v /app/data:/app/data \
  "$IMAGE_URI"

echo "Continuum started on port 8000. Verify: curl -fsS http://127.0.0.1:8000/v1/health"
