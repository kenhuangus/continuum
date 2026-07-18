# Function Compute (Phase B alternative)

> **FREE TRIAL / free CU only.** Use new-customer free CU (e.g. 150k CU/mo) or FC free trial. Abort if billed beyond free quota. Do not use paid FC plans for this path.

**ECS + Docker (free trial) is the recommended hackathon path** for Continuum because:

- The demo UI is served as static files from the same FastAPI process (`apps/web`).
- SQLite persistence needs a writable volume (`/app/data`), which maps naturally to an ECS disk mount.
- Single-container deploy is faster to debug than FC custom-container + NAS/OSS wiring.

For Track 1 PoD, follow [../ecs/DEPLOY.md](../ecs/DEPLOY.md) first (ECS free trial). Use FC only when free-CU eligible.

## When FC might make sense later

- Scale-to-zero API without managing a VM
- Custom container runtime with ACR image
- API Gateway in front for HTTPS and auth

## Deploy via Serverless Devs (`s.yaml`)

A starter FC3 custom-container definition lives in [s.yaml](s.yaml) (region `ap-southeast-1`, HTTP trigger on port 8000). `cpu: 0.5` / `memorySize: 1024` is the smallest custom-container path — keep it free-CU eligible.

**Caveats:** FC ephemeral storage is a poor fit for SQLite long-term. Prefer keeping ECS free trial for the demo rather than paid NAS/OSS. Cold starts and container image pull latency also apply. Abort if the deploy would bill beyond free quota.

### Steps

1. Push the Continuum image to ACR (see [../acr/push.md](../acr/push.md)). Confirm the image URI in `s.yaml` matches your registry.
2. Install Serverless Devs:

   ```bash
   npm i -g @serverless-devs/s
   ```

3. Configure Alibaba Cloud access (`s config add`) for the International account / region you use.
4. Export the DashScope key in the shell (do not commit secrets):

   ```bash
   export DASHSCOPE_API_KEY=your_key_here
   ```

5. From this directory, deploy:

   ```bash
   s deploy
   ```

6. After deploy, set CORS / public origin env vars to your real FC HTTP endpoint when you have one — do not invent a `PUBLIC_URL` ahead of time.

If you outgrow this starter: replace SQLite with Tablestore/RDS or mount NAS for `/app/data`, and harden auth beyond `CONTINUUM_AUTH_DISABLED=1`.
