# Proof of Alibaba Cloud Deployment

**Status:** Scaffolding ready · **Live deploy:** Pending (fill placeholders after ECS run)

Continuum targets Alibaba Cloud International for hackathon PoD. This doc is the checklist and fill-in template after you deploy.

## Code proof (Devpost — code file link)

Model calls use DashScope compatible mode. Base URL is visible in:

**File:** `packages/agent/continuum_agent/client.py`

```
https://dashscope-intl.aliyuncs.com/compatible-mode/v1
```

Paste a public GitHub blob URL to that file on Devpost (Proof of Deployment → code link).

## Alibaba services

| Service | Role | Status |
|---------|------|--------|
| **ECS** | Run Continuum Docker container (API + UI on :8000) | MVP — primary path |
| **DashScope (Qwen Cloud)** | Chat + embeddings via compatible-mode API | Required — in code |
| **ACR** | Optional container image registry | Optional — [infra/acr/push.md](../infra/acr/push.md) |
| **Elastic IP** | Stable public URL | Recommended |
| API Gateway | HTTPS front door | Planned (Phase B) |
| Function Compute / ACK | Serverless / K8s | Planned — see [infra/fc/README.md](../infra/fc/README.md) |
| Tablestore / RDS | Replace SQLite at scale | Planned |
| Redis | Pack cache | Planned |
| OSS | Artifact storage | Planned |
| ARMS / SLS | Observability | Planned |

Deploy guide: [infra/README.md](../infra/README.md) · ECS steps: [infra/ecs/DEPLOY.md](../infra/ecs/DEPLOY.md)

## Deployment checklist

- [ ] Build Docker image locally (`infra/scripts/build.ps1` or `build.sh`)
- [ ] Local smoke: `docker compose up` + `infra/scripts/smoke-health.sh`
- [ ] (Optional) Push image to ACR
- [ ] Create ECS instance (Ubuntu 22.04, public IP, security group :8000)
- [ ] Create `/etc/continuum.env` on instance with `DASHSCOPE_API_KEY` (not in git)
- [ ] Run container with volume `/app/data`
- [ ] Public URL responds: `GET /v1/health` → `{"status":"ok",...}`
- [ ] Demo UI loads at `/`
- [ ] Capture Alibaba Workbench screenshot

## Placeholders (fill after live deploy)

| Field | Value |
|-------|-------|
| `PUBLIC_URL` | `http://YOUR_ELASTIC_IP:8000` |
| `INSTANCE_ID` | `i-xxxxxxxx` |
| `REGION` | `ap-southeast-1` (or your region) |
| Workbench screenshot | `docs/screenshots/alibaba_workbench.png` |

## How to fill Devpost fields

1. **Proof of deployment — code link:** GitHub URL to `packages/agent/continuum_agent/client.py` showing DashScope base URL.
2. **Proof of deployment — screenshot:** Upload `docs/screenshots/alibaba_workbench.png` (ECS instance Running in Workbench).
3. **Demo / test access:** `PUBLIC_URL` above; if auth enabled, document `X-API-Key` value for judges.
4. **Built With:** Qwen Cloud, Alibaba Cloud ECS, DashScope, Python, FastAPI.
5. **Testing instructions:** `curl PUBLIC_URL/v1/health` and open `PUBLIC_URL/` in browser.

See [HACKATHON_SUBMIT.md](HACKATHON_SUBMIT.md) for full submission checklist.

## Qwen Cloud

Model calls use DashScope compatible mode:

`https://dashscope-intl.aliyuncs.com/compatible-mode/v1`

Configure via `.env` / `/etc/continuum.env`:

- `DASHSCOPE_API_KEY` or `QWEN_API_KEY`
- `QWEN_MODEL` (default `qwen-flash`)
- `QWEN_EMBED_MODEL` (default `text-embedding-v3`)

See `.env.example` and `continuum_agent.client.QwenClient`.

## Next human steps (summary)

1. `.\infra\scripts\build.ps1` → `docker compose up` → smoke health locally.
2. Create ECS + security group (port 8000) per [infra/ecs/DEPLOY.md](../infra/ecs/DEPLOY.md).
3. Set `/etc/continuum.env` on the instance; run container.
4. Verify public URL; save Workbench screenshot; update placeholders in this file.
5. Submit Devpost with code link + screenshot + demo URL.
