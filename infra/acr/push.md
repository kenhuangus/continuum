# Push Continuum image to Alibaba Container Registry (ACR)

Optional but recommended for repeatable ECS deploys.

## Placeholders

| Variable | Example | Description |
|----------|---------|-------------|
| `REGISTRY` | `cr.aliyuncs.com` or your instance hostname prefix | ACR registry host prefix |
| `NAMESPACE` | `continuum-hackathon` | ACR namespace |
| `IMAGE` | `continuum` | Repository name |
| `TAG` | `latest` | Image tag |
| `REGION` | `ap-southeast-1` | Region where ACR instance lives |

Full image URI pattern:

```
REGISTRY.ap-southeast-1.cr.aliyuncs.com/NAMESPACE/continuum:latest
```

Example:

```
myregistry.ap-southeast-1.cr.aliyuncs.com/continuum-hackathon/continuum:latest
```

## Console setup

1. Alibaba Cloud Console → **Container Registry** → Create **Personal Edition** or **Enterprise** instance.
2. Region: e.g. **Singapore (ap-southeast-1)**.
3. Create **namespace** and **repository** `continuum`.
4. Set repository type to **Private** (recommended).
5. Note login server: `<instance-id>.<region>.cr.aliyuncs.com`.

## Login

Use your Alibaba Cloud account or RAM user with ACR push permission:

```bash
docker login <instance-id>.ap-southeast-1.cr.aliyuncs.com
# Username: Alibaba Cloud account email or RAM user
# Password: from ACR console → Access Credential → Set/Reset Docker login password
```

## Tag and push

After building locally (`continuum:local`):

```bash
export REGISTRY="<instance-id>"
export NAMESPACE="continuum-hackathon"
export REGION="ap-southeast-1"
export TAG="latest"

docker tag continuum:local \
  ${REGISTRY}.${REGION}.cr.aliyuncs.com/${NAMESPACE}/continuum:${TAG}

docker push \
  ${REGISTRY}.${REGION}.cr.aliyuncs.com/${NAMESPACE}/continuum:${TAG}
```

Scripts: [push.sh](push.sh) (bash) and [push.ps1](push.ps1) (PowerShell).

## Deploy on ECS

On the instance:

```bash
docker pull ${REGISTRY}.${REGION}.cr.aliyuncs.com/${NAMESPACE}/continuum:${TAG}
docker run -d --name continuum -p 8000:8000 \
  --env-file /etc/continuum.env \
  -v /app/data:/app/data \
  ${REGISTRY}.${REGION}.cr.aliyuncs.com/${NAMESPACE}/continuum:${TAG}
```

See [../ecs/DEPLOY.md](../ecs/DEPLOY.md).
