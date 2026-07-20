# Render + Devpost Status — Continuum

**Date:** 2026-07-20  
**Track:** MemoryAgent  
**Repo:** https://github.com/kenhuangus/continuum

---

## Why Continuum cannot deploy to Alibaba Cloud (overnight evidence)

**Alibaba free compute was not obtainable.** Continuum therefore has **no live Alibaba `PUBLIC_URL`**.

| Fact | Detail |
|------|--------|
| Prior Singapore ECS | Gone — instance `i-t4n56ciqqnpj9pzemhnb` / IP `47.237.148.192:8000` dead; Singapore ECS list = **0**; SG `continuum-sg` **0 In Use** |
| Trial Center | `ecs-buy…/trialCenter` **redirects to paid Custom Launch** (Subscription) — not a free SKU claim UI → **aborted** (no paid create) |
| Free claim | Marketing `alibabacloud.com/free` + My Trial need human **Start for Free** / eligibility / CAPTCHA; automation could not complete |
| Other free paths | SWAS Singapore = 0; FC sandbox empty; Tokyo/US-West ECS = 0 |
| Paid paths | Explicitly **aborted** |

Full attempt log: [OVERNIGHT_STATUS.md](OVERNIGHT_STATUS.md). Alibaba PoD remains honest/not-live: [PROOF_OF_ALIBABA_DEPLOYMENT.md](PROOF_OF_ALIBABA_DEPLOYMENT.md).

---

## Render URL (Try-it — **not** Alibaba PoD)

| Item | Value |
|------|--------|
| **PUBLIC_URL (demo)** | https://continuum-8hwx.onrender.com/ |
| **Health** | https://continuum-8hwx.onrender.com/v1/health → `{"status":"ok","service":"continuum",...}` |
| **Plan** | Free Web Service (Docker) via Blueprint `continuum-hackathon` |
| **Env** | `CONTINUUM_AUTH_DISABLED=1`, `PORT=8000`, `CONTINUUM_DB_PATH=/app/data/continuum.db` |
| **DASHSCOPE_API_KEY** | **Not set** (missing from local `.env`) — health/UI work; **chat/LLM may degrade** until key added in Render dashboard |
| **Honest label** | Non-Alibaba fallback Try-it host for judges |

Blueprint deeplink used:  
`https://dashboard.render.com/blueprint/new?repo=https://github.com/kenhuangus/continuum`

---

## Devpost submit status

| Item | Status |
|------|--------|
| Project packet | [DEVPOST_SUBMIT_PACKET.md](DEVPOST_SUBMIT_PACKET.md) |
| Submit attempted | See section below / remaining human steps |
| Video | Local `demo_video/continuum_demo.mp4` — YouTube upload may still need human login |
| Architecture | `docs/architecture.png` |

---

## Remaining human steps (true blockers only)

1. **Optional:** Paste `DASHSCOPE_API_KEY` into Render → continuum service → Environment (so judge chat works).
2. **If Devpost Submit not finished below:** open https://qwencloud-hackathon.devpost.com/ → edit Continuum → paste Try-it URL `https://continuum-8hwx.onrender.com/` → attach architecture PNG → upload/link demo video → click **Submit** (CAPTCHA/SMS if any).
3. **Optional Alibaba PoD:** only if still required — human **Start for Free** claim free ECS, then deploy Docker (do **not** buy paid SKUs).

---

## Related

- [FREE_HOSTING_OPTIONS.md](FREE_HOSTING_OPTIONS.md)
- `render.yaml` (repo root)
- Screenshots: `docs/screenshots/render_invoke_*.png`, `render_svc_*.png`
