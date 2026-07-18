# Alibaba Cloud Deploy Guide (Windows) — Continuum

> **FREE TIER ONLY.** Claim ECS personal free trial or FC free CU; abort if payment is required beyond free-trial eligibility / payment method for trial claim. Do not use pay-as-you-go non-trial SKUs. Trial center: https://ecs-buy.alibabacloud.com/trialCenter#/internationalPersonalTrial

**Status (2026-07-18):** Deploy is **BLOCKED** until AccessKey + `DASHSCOPE_API_KEY` exist. Checked: no `~/.aliyun/config.json`, no `ALIBABA_CLOUD_*` / `ALICLOUD_*` / `DASHSCOPE_API_KEY` / `QWEN_API_KEY` env vars, no `.env`.

## 1. Create / login Alibaba Cloud International account

- Use International site: https://www.alibabacloud.com (**NOT** aliyun.com China)
- Register: https://www.alibabacloud.com/account/register
- Login: https://www.alibabacloud.com/account/login
- Claim free tier first: [ECS Trial Center](https://ecs-buy.alibabacloud.com/trialCenter#/internationalPersonalTrial) (prefer Singapore `ap-southeast-1`) or FC free CU

## 2. Create AccessKey (RAM least privilege)

- Prefer a **RAM user** over a root-account AccessKey
- Console: **RAM → Users → Create User** → enable programmatic access → create AccessKey
- Attach minimal policies for ECS + VPC + (optional) ACR/FC — e.g. `AliyunECSFullAccess`, `AliyunVPCReadOnlyAccess` for hackathon speed; tighten later
- Direct AK page: https://ram.console.aliyun.com/manage/ak
- **NEVER** commit AccessKey to git

## 3. Configure aliyun CLI (exact commands)

```powershell
# Install if missing (winget)
winget install Alibaba.AlibabaCloudCLI

# Configure International profile
aliyun configure --profile continuum --mode AK
# When prompted:
#   Access Key Id: <paste>
#   Access Key Secret: <paste>
#   Default Region Id: ap-southeast-1
#   Default Output Format: json
#   Default Language: en

aliyun configure list
aliyun configure set --profile continuum --region ap-southeast-1
$env:ALIYUN_PROFILE = "continuum"
```

Note: config lands in `%USERPROFILE%\.aliyun\config.json`

## 4. Set DASHSCOPE_API_KEY

- Get key: DashScope / Model Studio console (International) — https://dashscope.console.aliyun.com/apiKey or Qwen Cloud console
- Windows PowerShell (session):

```powershell
$env:DASHSCOPE_API_KEY = "sk-..."
$env:QWEN_API_KEY = $env:DASHSCOPE_API_KEY
```

- Or create `C:\Users\kenhu\qwen-hacktoh\.env` (gitignored) with `DASHSCOPE_API_KEY=...` and `QWEN_API_KEY=...`

## 5. Recommended path: ECS + Docker (free trial)

Copy key commands from `infra/ecs/DEPLOY.md` (already verified in repo):

- Claim free trial at the Trial Center; create Ubuntu 22.04 ECS in `ap-southeast-1` using **only** `FREE_TRIAL_INSTANCE_TYPE` from the offer (abort if routed to paid catalog). Public IP, SG open **22** + **8000**
- On instance:

```bash
git clone https://github.com/kenhuangus/continuum.git /opt/continuum
cd /opt/continuum
sudo docker build -t continuum:local .
sudo tee /etc/continuum.env <<'EOF'
DASHSCOPE_API_KEY=YOUR_KEY_HERE
QWEN_API_KEY=YOUR_KEY_HERE
CONTINUUM_DB_PATH=/app/data/continuum.db
CONTINUUM_AUTH_DISABLED=0
CONTINUUM_API_KEYS=demo_key_for_judges
CONTINUUM_CORS_ORIGINS=http://YOUR_PUBLIC_IP:8000
EOF
sudo chmod 600 /etc/continuum.env
sudo mkdir -p /app/data
sudo docker run -d --name continuum --restart unless-stopped -p 8000:8000 --env-file /etc/continuum.env -v /app/data:/app/data continuum:local
curl -fsS http://127.0.0.1:8000/v1/health
```

- Full detail: `infra/ecs/DEPLOY.md`

## 6. Alternative: Function Compute (free CU / free trial only)

- See `infra/fc/README.md` and `infra/fc/s.yaml`
- Abort if billed beyond free quota
- Push image to ACR, `npm i -g @serverless-devs/s`, `s config add`, export `DASHSCOPE_API_KEY`, `s deploy` from `infra/fc/`

## 7. Workbench screenshot

- Alibaba ECS console → Workbench or instance list showing **Running**
- Save as `docs/screenshots/alibaba_workbench.png`
- See `infra/scripts/capture_console_screenshot.md` if present

## 8. What to paste on Devpost

- **PUBLIC_URL:** `http://PUBLIC_IP:8000`
- **Code file blob:** `packages/agent/continuum_agent/client.py` (DashScope base URL)
- **Screenshot:** `docs/screenshots/alibaba_workbench.png`
- Update `docs/PROOF_OF_ALIBABA_DEPLOYMENT.md` with PUBLIC_URL / INSTANCE_ID / REGION

## 9. Time & free-tier caution

- Est. time: 30–60 min if account already verified; longer for new account KYC
- **FREE TIER ONLY** — claim ECS personal free trial ([Trial Center](https://ecs-buy.alibabacloud.com/trialCenter#/internationalPersonalTrial)) or FC free CU; abort if payment is required beyond free-trial eligibility / payment method for trial claim
- Do not select pay-as-you-go non-trial SKUs; DashScope tokens may bill separately — watch usage
- Release / stop the trial instance after demo so you stay within trial limits

## Next 3 actions for the human

1. Create/login International account, claim ECS free trial (Singapore), create RAM AccessKey
2. Run `aliyun configure --profile continuum --mode AK` (region `ap-southeast-1`)
3. Create `.env` with `DASHSCOPE_API_KEY`, then follow `infra/ecs/DEPLOY.md` (free-trial instance type only)
