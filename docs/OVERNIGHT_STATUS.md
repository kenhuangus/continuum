# Overnight Status — Continuum MemoryAgent Devpost

**Date:** 2026-07-20 (overnight pass)  
**Deadline:** Jul 20, 2026 2:00pm PDT  
**Track:** MemoryAgent  
**Repo:** https://github.com/kenhuangus/continuum (public, Apache-2.0)

## Why Continuum cannot deploy to Alibaba Cloud

Prior Singapore ECS is **gone**; Trial Center **redirects to paid Custom Launch**; free claim needs human **Start for Free** / eligibility; **no free running compute**; paid paths **aborted**. See attempt log below. Full follow-up: [RENDER_DEVPOST_STATUS.md](RENDER_DEVPOST_STATUS.md).

## Verdict

**No live Alibaba PUBLIC_URL.** Free Alibaba compute was not obtainable overnight after **6 distinct serious attempts**. Paid ECS paths were aborted.

**Fallback Try-it (not Alibaba PoD):** Continuum is live on **Render free** — https://continuum-8hwx.onrender.com/ · health `/v1/health` → `status: ok`.

## PUBLIC_URL

| Host | URL |
|------|-----|
| **Alibaba** | `NONE` — not publicly reachable on Alibaba Cloud |
| **Render (demo only)** | https://continuum-8hwx.onrender.com/ |

Prior known IP `http://47.237.148.192:8000` is **dead** (connection timeout; instance no longer listed).

## Attempt log (1–6)

| # | Attempt | What we did | Result |
|---|---------|-------------|--------|
| **1** | Existing free ECS redeploy | Opened kenhuangus Chrome → Singapore ECS → security group `continuum-sg` → Workbench for `i-t4n56ciqqnpj9pzemhnb` | **FAIL** — Instance **gone**. Singapore ECS list = **0**. SG `continuum-sg` shows **0 In Use**. Workbench spun on missing instance. Ports 22/8000 timeout. Shots: `overnight_01_instances.png`, `overnight_03_sg_list.png`, `overnight_05_workbench.png` |
| **2** | ECS International Personal Trial Center | Navigated `ecs-buy…/trialCenter#/internationalPersonalTrial` repeatedly | **FAIL** — Redirects to **paid Custom Launch** (`Subscription` / China Beijing or Hangzhou), not a free-trial SKU claim UI. Aborted (no paid create). Shots: `overnight_a2_ecs_trial.png`, `overnight_a2b_trial_center.png` |
| **3** | Free landing + My Trial reclaim | Opened `alibabacloud.com/free` (AI Cloud Free Trial / ECS $90 credits marketing) + My Trial / billing free-trial URLs | **FAIL** — Marketing CTA only; free-trial console URLs redirected to **Monthly Bill** (0 USD). No reclaimable free VM visible without human **Start for Free** / payment-method / CAPTCHA. Shots: `overnight_a3_free_landing.png`, `overnight_a3_my_trial.png`, `overnight_a3b_my_trial.png` |
| **4** | Simple Application Server (Singapore) | Opened SWAS console `ap-southeast-1` | **FAIL** — **0** servers in Singapore. Create would be a new purchase path; not confirmed free → stopped. Shot: `overnight_a4_sas_sg.png` |
| **5** | Function Compute + other ECS regions | `fcnext…` NXDOMAIN; `fc.console…` Cloud Sandbox (empty); ECS Tokyo + US-West lists | **FAIL** — FC sandbox has **no instances**; Tokyo/US-West ECS = **0**. No free running compute to deploy into. Shots: `overnight_a5_fc_sg.png`, `overnight_a5b_fc_console.png`, `overnight_a5_ecs_tokyo.png`, `overnight_a5_ecs_uswest.png` |
| **6** | SG rules + buy-wizard eligibility | Inspected `continuum-sg`; opened prepay wizard; rechecked Singapore instances | **FAIL / ABORT** — SG unused (2 rules, 0 in use). Wizard is **paid** Custom Launch → **did not create**. Final Singapore ECS still **0**. Shots: `overnight_a6_sg_rules.png`, `overnight_a6_wizard.png`, `overnight_a6_instances_final.png` |

### Account / CLI notes (no secrets)

| Surface | Observation |
|---------|-------------|
| Chrome (active) | `kenhu***@gm…` Main Account — owns empty Singapore ECS + leftover `continuum-sg` |
| `aliyun` profile `default` | RAM `power-application-user` on AccountId `1693146562821514` — **0 ECS**, balance **$0** |
| `aliyun` profile `continuum-free` | RAM `continuum-deploy` on AccountId `5331784392600943` — **Forbidden.RAM** on `ecs:DescribeInstances` |
| Session lock | Workstation had no foreground window overnight; used `chrome.exe URL` + PrintWindow (not a new browser profile) |

## Completed without human

- [x] Six free-tier attempts documented with screenshots under `docs/screenshots/overnight_*.png`
- [x] Updated `docs/PROOF_OF_ALIBABA_DEPLOYMENT.md` (honest: not live)
- [x] Wrote `docs/DEVPOST_SUBMIT_PACKET.md` (paste-ready Devpost fields)
- [x] Architecture wording remains accurate (**live pending** — not falsely marked live)
- [x] Local demo video present: `demo_video/continuum_demo.mp4` (~3:37, ~13 MB)
- [x] Public GitHub + Apache-2.0 confirmed
- [x] Architecture PNG: `docs/architecture.png`
- [x] Code proof blob ready: `packages/agent/continuum_agent/client.py` (DashScope intl base URL)

## Remaining human steps (minimal)

1. **Claim free compute** (if still eligible): unlock machine → Chrome already on Alibaba → **Start for Free** / My Trial → claim **free ECS** (Singapore preferred) — **no paid SKUs**. Or create FC free sandbox if offer allows Docker/HTTP.
2. **Deploy Continuum** on that free host (or ask agent once free VM exists): Docker + `CONTINUUM_AUTH_DISABLED=1` + `DASHSCOPE_API_KEY`; open SG **TCP 8000**; verify `curl http://PUBLIC_IP:8000/v1/health`.
3. **(Optional fallback Try-it URL)** If Alibaba stays blocked: deploy on **Render free** per [FREE_HOSTING_OPTIONS.md](FREE_HOSTING_OPTIONS.md) — **not** Alibaba proof; use only as Devpost live demo link.
4. **Capture Workbench screenshot** of **Running** resource → replace `docs/screenshots/alibaba_workbench.png` → push.
5. **Upload demo video** to YouTube (public or unlisted) from `demo_video/continuum_demo.mp4` — **login required**.
6. **Paste** fields from `docs/DEVPOST_SUBMIT_PACKET.md` into Devpost → attach architecture PNG + Workbench PNG → paste YouTube URL → **Submit** (CAPTCHA if any).

## Blockers

1. **No free running instance** on the logged-in account (Singapore/Tokyo/US-West empty; prior `i-t4n56ciqqnpj9pzemhnb` deleted/expired).
2. **Trial Center → paid Custom Launch** redirect; free SKU claim needs interactive **Start for Free** / eligibility that automation could not complete on a locked session.
3. **CLI RAM keys** cannot manage the kenhuangus Chrome account’s ECS (wrong account or insufficient policy on secondary accounts).
4. **YouTube + Devpost Submit** require human login / final click.

## Fallback: free hosting (non-Alibaba) for Devpost “Try it”

If Alibaba compute stays blocked, Continuum **can** run on other free hosts (Docker FastAPI on port 8000). That gives judges a clickable URL but **does not** replace Alibaba deployment proof.

- Full ranking + checklist: **[FREE_HOSTING_OPTIONS.md](FREE_HOSTING_OPTIONS.md)**
- **Best bet:** Render free Web Service (Docker, no credit card; spins down after ~15 min idle)
- **This session:** no free-host deploy completed — missing Render/Railway/Fly credentials; HF token is read-only; gcloud has no billing account; Docker engine down; no `DASHSCOPE_API_KEY` in `.env` → **PUBLIC_URL still NONE**

## Related files

- [FREE_HOSTING_OPTIONS.md](FREE_HOSTING_OPTIONS.md)
- [DEVPOST_SUBMIT_PACKET.md](DEVPOST_SUBMIT_PACKET.md)
- [PROOF_OF_ALIBABA_DEPLOYMENT.md](PROOF_OF_ALIBABA_DEPLOYMENT.md)
- [HACKATHON_SUBMIT.md](HACKATHON_SUBMIT.md)
- `_overnight_free_attempts.json` (machine log)
