# Proof of Alibaba Cloud Deployment

**Constraint:** Free-trial / free SKUs only. Do **not** create paid pay-as-you-go or subscription ECS for this hackathon path.

**Status (2026-07-20):** Scaffolding ready · **Live Alibaba deploy: NOT LIVE**

**Why not Alibaba:** Prior Singapore ECS gone; Trial Center → paid Custom Launch; free claim needs human Start for Free / eligibility; no free running compute; paid paths aborted. See [OVERNIGHT_STATUS.md](OVERNIGHT_STATUS.md).

**Fallback Try-it (not this PoD):** Continuum on Render free — https://continuum-8hwx.onrender.com/ — see [RENDER_DEVPOST_STATUS.md](RENDER_DEVPOST_STATUS.md). Does **not** replace Alibaba deployment proof.

## Devpost fields

| Field | Value |
|-------|-------|
| **Code file (DashScope / Qwen Cloud)** | [`packages/agent/continuum_agent/client.py`](https://github.com/kenhuangus/continuum/blob/master/packages/agent/continuum_agent/client.py) — `DEFAULT_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"` |
| **Workbench screenshot path** | `docs/screenshots/alibaba_workbench.png` — **stale** (shows former Running `continuum` / `i-t4n56ciqqnpj9pzemhnb`). Current console: **0 instances** (see `overnight_a6_instances_final.png`). Replace after free reclaim. |
| **Deployed endpoint (`PUBLIC_URL`)** | **NONE on Alibaba** — former `http://47.237.148.192:8000` unreachable. Demo-only Render: https://continuum-8hwx.onrender.com/ |
| **Instance / region** | Former: `i-t4n56ciqqnpj9pzemhnb` · Singapore `ap-southeast-1` · name `continuum` — **deleted/expired as of overnight check**. Leftover SG: `sg-t4n6m0z3fekvizng9ho1` (`continuum-sg`, 0 In Use) |

## Architecture (deploy plane)

```
Internet / judges
    → ECS:8000 or FC HTTP trigger (Continuum FastAPI + demo UI)   ← NOT LIVE overnight
        → DashScope Qwen Cloud (dashscope-intl.aliyuncs.com/compatible-mode/v1)
        → SQLite volume (/app/data/continuum.db)
```

Primary path: **ECS + Docker** (free trial only). Alternative: **Function Compute** custom container ([infra/fc/s.yaml](../infra/fc/s.yaml)). ROS: [infra/ros/continuum-ecs.template.json](../infra/ros/continuum-ecs.template.json).

## Overnight evidence (not a live PoD)

| Shot | Meaning |
|------|---------|
| `docs/screenshots/overnight_01_instances.png` | Singapore ECS empty |
| `docs/screenshots/overnight_03_sg_list.png` | `continuum-sg` exists, 0 In Use |
| `docs/screenshots/overnight_05_workbench.png` | Workbench hung on missing instance |
| `docs/screenshots/overnight_a2_ecs_trial.png` | Trial Center → paid Custom Launch |
| `docs/screenshots/overnight_a3_free_landing.png` | Free marketing CTA |
| `docs/screenshots/overnight_a4_sas_sg.png` | SAS Singapore = 0 |
| `docs/screenshots/overnight_a5b_fc_console.png` | FC Cloud Sandbox empty |
| `docs/screenshots/overnight_a6_instances_final.png` | Final Singapore ECS still 0 |

## Steps to reproduce (when free instance exists)

1. Claim **free** ECS (International Personal Trial / Start for Free) — prefer Singapore `ap-southeast-1`. **Abort** if console only offers paid catalog.
2. Security group: TCP **22** + **8000** — see [infra/ecs/security-group.md](../infra/ecs/security-group.md).
3. On instance:

```bash
git clone https://github.com/kenhuangus/continuum.git /opt/continuum
cd /opt/continuum
sudo docker build -t continuum:local .
sudo tee /etc/continuum.env <<'EOF'
DASHSCOPE_API_KEY=YOUR_KEY
CONTINUUM_AUTH_DISABLED=1
CONTINUUM_DB_PATH=/app/data/continuum.db
EOF
sudo chmod 600 /etc/continuum.env
sudo mkdir -p /app/data
sudo docker run -d --name continuum --restart unless-stopped \
  -p 8000:8000 --env-file /etc/continuum.env -v /app/data:/app/data continuum:local
curl -fsS http://127.0.0.1:8000/v1/health
```

4. From laptop: `curl -fsS http://PUBLIC_IP:8000/v1/health`
5. Capture Workbench **Running** → `docs/screenshots/alibaba_workbench.png`
6. Update this doc’s `PUBLIC_URL` / Instance ID / Region

Full runbook: [infra/ecs/DEPLOY.md](../infra/ecs/DEPLOY.md).

## Deployment checklist

- [x] Containerize API (`Dockerfile` at repo root)
- [x] Local image build + health smoke
- [x] ECS / ACR / FC / ROS scaffolding under `infra/`
- [x] Overnight free-tier attempts documented ([OVERNIGHT_STATUS.md](OVERNIGHT_STATUS.md))
- [ ] Live free ECS/FC with Continuum container
- [ ] Fresh Workbench screenshot (Running)
- [ ] Fill `PUBLIC_URL` / `INSTANCE_ID` / `REGION` with live values
- [ ] Paste code-file blob URL + screenshot on Devpost

## Blockers (2026-07-20)

| Check | Result |
|-------|--------|
| Former ECS `i-t4n56ciqqnpj9pzemhnb` | **Gone** from console; IP unreachable |
| Free Trial Center | Redirects to **paid** Custom Launch |
| Free landing / My Trial | Needs human claim; no free VM listed |
| SAS / FC sandbox / other regions | Empty |
| `aliyun` CLI profiles | Wrong account or Forbidden.RAM — cannot create via CLI on Chrome account |
| Live `PUBLIC_URL` | **None** |

## Qwen Cloud

```
https://dashscope-intl.aliyuncs.com/compatible-mode/v1
```

Implemented in `continuum_agent.client.QwenClient` (`packages/agent/continuum_agent/client.py`).

## Related

- [OVERNIGHT_STATUS.md](OVERNIGHT_STATUS.md)
- [DEVPOST_SUBMIT_PACKET.md](DEVPOST_SUBMIT_PACKET.md)
- [infra/README.md](../infra/README.md)
- [HACKATHON_SUBMIT.md](HACKATHON_SUBMIT.md)
