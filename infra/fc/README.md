# Function Compute (Phase B alternative)

**ECS + Docker is the recommended hackathon path** for Continuum because:

- The demo UI is served as static files from the same FastAPI process (`apps/web`).
- SQLite persistence needs a writable volume (`/app/data`), which maps naturally to an ECS disk mount.
- Single-container deploy is faster to debug than FC custom-container + NAS/OSS wiring.

## When FC might make sense later

- Scale-to-zero API without managing a VM
- Custom container runtime with ACR image
- API Gateway in front for HTTPS and auth

## Not implemented here

Full FC IaC (services, triggers, NAS mounts) is intentionally deferred. If you migrate:

1. Push the same image to ACR (see [../acr/push.md](../acr/push.md)).
2. Create FC custom-container function with port 8000.
3. Replace SQLite with Tablestore/RDS or mount NAS for `/app/data`.
4. Update CORS and public URL env vars.

For Track 1 PoD, follow [../ecs/DEPLOY.md](../ecs/DEPLOY.md) first.
