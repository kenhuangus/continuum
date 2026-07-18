# Deploy Continuum on Alibaba Cloud ECS (primary hackathon path)

> **Free tier only.** Abort if not free-trial eligible. Do not use pay-as-you-go non-trial SKUs.

Fastest proof-of-deployment path: **Ubuntu 22.04 ECS + Docker + public port 8000** on a free-trial instance.

## Prerequisites

- Alibaba Cloud **International** account ([alibabacloud.com](https://www.alibabacloud.com)) with **ECS personal free trial** eligibility
- Claim trial first: [ECS International Personal Trial Center](https://ecs-buy.alibabacloud.com/trialCenter#/internationalPersonalTrial) (prefer **Singapore `ap-southeast-1`**)
- `DASHSCOPE_API_KEY` from DashScope / Qwen Cloud console
- Local Docker (to build image) **or** ACR push (see [../acr/push.md](../acr/push.md))
- SSH key pair for ECS login

## 1. Build image locally (optional)

From repo root:

```powershell
.\infra\scripts\build.ps1
```

```bash
./infra/scripts/build.sh
```

## 2. Create ECS instance (free trial only)

1. Claim a free trial package first at the [ECS International Personal Trial Center](https://ecs-buy.alibabacloud.com/trialCenter#/internationalPersonalTrial). Prefer **Singapore (`ap-southeast-1`)**.
2. Use **ONLY** the instance type shown in the free trial offer (typically the smallest 1 vCPU class). Set `InstanceType = FREE_TRIAL_INSTANCE_TYPE` from the trial center — never from the paid catalog.
3. **ABORT** if the console routes to pay-as-you-go / paid catalog instead of a free-trial claim.
4. Image: **Ubuntu 22.04 LTS 64-bit**.
5. Networking: default VPC, **assign public IPv4 address**. Keep outbound bandwidth within free-trial limits (prefer 1 Mbps).
6. Security group: see [security-group.md](security-group.md) — open **22** (your IP) and **8000** (public demo).
7. Login: SSH key pair.
8. Optional: attach **Elastic IP** only if included in free trial / does not incur paid charges.

## 3. Deploy container

### Path A — Docker pull from ACR (recommended after first push)

On ECS:

```bash
sudo docker login REGISTRY.ap-southeast-1.cr.aliyuncs.com
sudo docker pull REGISTRY.ap-southeast-1.cr.aliyuncs.com/NAMESPACE/continuum:latest
```

Set `CONTINUUM_IMAGE` to that URI in user-data or run manually.

### Path B — Git clone + build on instance

```bash
git clone https://github.com/kenhuangus/continuum.git /opt/continuum
cd /opt/continuum
sudo docker build -t continuum:local .
```

### Path C — cloud-init user-data

Paste [user-data.sh](user-data.sh) into ECS **User Data** at launch (or use as a startup script). Set:

- `CONTINUUM_GIT_URL` — public repo URL, **or**
- `CONTINUUM_IMAGE` — full ACR image URI

## 4. Configure environment on the instance

Start from the example template [continuum.env.example](continuum.env.example), then create `/etc/continuum.env` (mode 600):

```bash
sudo tee /etc/continuum.env <<'EOF'
DASHSCOPE_API_KEY=YOUR_KEY_HERE
QWEN_API_KEY=YOUR_KEY_HERE
CONTINUUM_DB_PATH=/app/data/continuum.db
CONTINUUM_AUTH_DISABLED=0
CONTINUUM_API_KEYS=demo_key_for_judges
CONTINUUM_CORS_ORIGINS=http://YOUR_PUBLIC_IP:8000
EOF
sudo chmod 600 /etc/continuum.env
```

Replace placeholders (`YOUR_KEY_HERE`, `YOUR_PUBLIC_IP`). Never commit the real `/etc/continuum.env`.

## 5. Run container

```bash
sudo mkdir -p /app/data
sudo docker rm -f continuum 2>/dev/null || true
sudo docker run -d \
  --name continuum \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file /etc/continuum.env \
  -v /app/data:/app/data \
  continuum:local
```

For ACR image, replace `continuum:local` with your full image URI.

## 6. Verify

On ECS:

```bash
curl -fsS http://127.0.0.1:8000/v1/health
```

From your laptop (replace `PUBLIC_IP`):

```bash
curl -fsS http://PUBLIC_IP:8000/v1/health
```

Open in browser: `http://PUBLIC_IP:8000/`

## 7. Capture proof for Devpost

1. Note **PUBLIC_URL** = `http://PUBLIC_IP:8000` (or Elastic IP).
2. Alibaba **Workbench** screenshot showing ECS instance **Running** → save as `docs/screenshots/alibaba_workbench.png`.
3. Fill [../../docs/PROOF_OF_ALIBABA_DEPLOYMENT.md](../../docs/PROOF_OF_ALIBABA_DEPLOYMENT.md) placeholders.
4. Devpost code link: `packages/agent/continuum_agent/client.py` (DashScope base URL visible).

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Connection refused on :8000 | Security group inbound 8000; `docker ps`; container logs `docker logs continuum` |
| 401 on API | Set `CONTINUUM_AUTH_DISABLED=1` for open demo or pass `X-API-Key` |
| Qwen errors | Valid `DASHSCOPE_API_KEY`; outbound HTTPS allowed |
| UI blank / CORS | Set `CONTINUUM_CORS_ORIGINS` to your public origin |

## Next steps (optional)

- Push image to ACR for repeatable deploys (within free tier / trial limits)
- SLB + HTTPS: **optional future only** — not part of the free-tier path; HTTP on `:8000` is enough for PoD
- See [../fc/README.md](../fc/README.md) for Function Compute free CU / free trial (Phase B)
