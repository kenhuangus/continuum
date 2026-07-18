# Proof of Alibaba Cloud Deployment

**Status:** Scaffolding ready · **Live Alibaba deploy:** blocked (no AccessKey / console session on this machine)

Continuum is containerized and smoke-tested locally. A public Alibaba endpoint and Workbench screenshot still require account credentials (see [Blockers](#blockers-machine-status-2026-07-18)).

## Devpost fields (fill when live)

| Field | Value |
|-------|-------|
| **Code file (DashScope / Qwen Cloud)** | `packages/agent/continuum_agent/client.py` — `DEFAULT_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"` |
| **Workbench screenshot path** | `docs/screenshots/alibaba_workbench.png` *(not captured yet — see [screenshots/README.md](screenshots/README.md))* |
| **Deployed endpoint (`PUBLIC_URL`)** | `TBD` — e.g. `http://<ECS_PUBLIC_IP>:8000` or FC HTTP trigger URL after deploy |
| **Instance / region** | `INSTANCE_ID=TBD` · prefer `ap-southeast-1` (Singapore, International) |

Paste a **public GitHub blob URL** to `client.py` on Devpost. Upload the Workbench PNG once captured.

## Architecture (deploy plane)

```
Internet / judges
    → ECS:8000 or FC HTTP trigger (Continuum FastAPI + demo UI)
        → DashScope Qwen Cloud (dashscope-intl.aliyuncs.com/compatible-mode/v1)
        → SQLite volume (/app/data/continuum.db)
```

Primary path: **ECS + Docker**. Alternative: **Function Compute** custom container ([infra/fc/s.yaml](../infra/fc/s.yaml)). ROS: [infra/ros/continuum-ecs.template.json](../infra/ros/continuum-ecs.template.json).

## Steps to reproduce

1. **Prerequisites**
   - Alibaba Cloud **International** account ([alibabacloud.com](https://www.alibabacloud.com))
   - AccessKey configured: `aliyun configure` (creates `~/.aliyun/config.json`)
   - `DASHSCOPE_API_KEY` from DashScope / Qwen Cloud console
   - Docker locally (verified: `continuum:local` builds and `/v1/health` returns `ok`)

2. **Build**
   ```powershell
   .\infra\scripts\build.ps1
   .\infra\scripts\run-local.ps1
   .\infra\scripts\smoke-health.ps1
   ```
   Or: `docker build -t continuum:local .` then `docker compose up`.

3. **Deploy (ECS — recommended)**
   - Follow [infra/ecs/DEPLOY.md](../infra/ecs/DEPLOY.md)
   - Security group: TCP **22** + **8000** ([infra/ecs/security-group.md](../infra/ecs/security-group.md))
   - On instance: `/etc/continuum.env` from [infra/ecs/continuum.env.example](../infra/ecs/continuum.env.example)
   - Run container with volume `/app/data`, publish `8000:8000`
   - Optional: push to ACR ([infra/acr/push.md](../infra/acr/push.md)) then pull on ECS
   - Optional ROS: create stack from [infra/ros/continuum-ecs.template.json](../infra/ros/continuum-ecs.template.json)

4. **Deploy (FC — alternative)**
   - Push image to ACR; set image URI in [infra/fc/s.yaml](../infra/fc/s.yaml)
   - `npm i -g @serverless-devs/s` → `s config add` → `export DASHSCOPE_API_KEY=...` → `s deploy` from `infra/fc/`
   - See [infra/fc/README.md](../infra/fc/README.md)

5. **Verify**
   ```bash
   curl http://PUBLIC_IP:8000/v1/health
   # expect {"status":"ok","service":"continuum",...}
   ```
   Open `http://PUBLIC_IP:8000/` for the demo UI.

6. **Workbench screenshot**
   - Follow [infra/scripts/capture_console_screenshot.md](../infra/scripts/capture_console_screenshot.md)
   - Save as `docs/screenshots/alibaba_workbench.png` (instance **Running**)

7. **Update this doc**
   - Replace `PUBLIC_URL`, `INSTANCE_ID`, and `REGION` placeholders above
   - Mark checklist items complete

## Deployment checklist

- [x] Containerize API (`Dockerfile` at repo root)
- [x] Local image build + health smoke (`continuum:local` → `/v1/health` = 200)
- [x] ECS / ACR / FC / ROS scaffolding under `infra/`
- [ ] Configure `aliyun` AccessKey (`~/.aliyun/config.json`)
- [ ] Set `DASHSCOPE_API_KEY` (local `.env` and/or `/etc/continuum.env` on ECS)
- [ ] Create ECS (or FC) and obtain public URL
- [ ] Capture `docs/screenshots/alibaba_workbench.png`
- [ ] Fill `PUBLIC_URL` / `INSTANCE_ID` / `REGION` in this file
- [ ] Paste code-file blob URL + screenshot on Devpost

## Blockers (machine status 2026-07-18)

| Check | Result |
|-------|--------|
| `aliyun` CLI | Installed **v3.4.8** (winget) |
| `~/.aliyun/config.json` | **Missing** — `aliyun configure list` fails |
| Env `DASHSCOPE_API_KEY` / `QWEN_API_KEY` | **Not set** |
| Docker | Available; image `continuum:local` builds; health OK on host port 18080 |
| Alibaba console (Playwright) | Redirects to **Login** — no browser session |
| Live `PUBLIC_URL` | **None** |
| `docs/screenshots/alibaba_workbench.png` | **Not present** |

**Unblock:** run `aliyun configure` with International AccessKey ID/Secret, create `.env` with `DASHSCOPE_API_KEY`, complete [infra/ecs/DEPLOY.md](../infra/ecs/DEPLOY.md), then capture the Workbench screenshot.

## Qwen Cloud

```
https://dashscope-intl.aliyuncs.com/compatible-mode/v1
```

Implemented in `continuum_agent.client.QwenClient` (`packages/agent/continuum_agent/client.py`). Configure via `.env` / `/etc/continuum.env` — see `.env.example`.

## Related

- [infra/README.md](../infra/README.md) — topology and scripts
- [HACKATHON_SUBMIT.md](HACKATHON_SUBMIT.md) — full submission checklist
- [screenshots/README.md](screenshots/README.md) — screenshot requirements
