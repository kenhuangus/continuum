# Render + Devpost Status — Continuum

**Date:** 2026-07-20  
**Track:** MemoryAgent  
**Repo:** https://github.com/kenhuangus/continuum

---

## Why Continuum cannot deploy to Alibaba Cloud (overnight evidence)

**Alibaba free compute was not obtainable.** Continuum has **no live Alibaba `PUBLIC_URL`.**

| Fact | Detail |
|------|--------|
| Prior Singapore ECS | **Gone** — `i-t4n56ciqqnpj9pzemhnb` / `http://47.237.148.192:8000` dead; Singapore ECS list = **0**; SG `continuum-sg` **0 In Use** |
| Trial Center | Redirects to **paid Custom Launch** (Subscription) — not a free SKU claim UI → **aborted** (no paid create) |
| Free claim | Needs human **Start for Free** / eligibility / CAPTCHA on marketing + My Trial surfaces |
| Other free paths | SWAS Singapore = 0; FC sandbox empty; Tokyo/US-West ECS = 0 |
| Paid paths | Explicitly **aborted** |

Full log: [OVERNIGHT_STATUS.md](OVERNIGHT_STATUS.md). Alibaba PoD stays honest: [PROOF_OF_ALIBABA_DEPLOYMENT.md](PROOF_OF_ALIBABA_DEPLOYMENT.md).

---

## Render URL (Try-it — **not** Alibaba PoD)

| Item | Value |
|------|--------|
| **PUBLIC_URL** | **https://continuum-8hwx.onrender.com/** |
| **Health** | https://continuum-8hwx.onrender.com/v1/health → `{"status":"ok","service":"continuum",...}` |
| **How** | Free Docker Web Service via Blueprint `continuum-hackathon` (`render.yaml`) |
| **Env** | `CONTINUUM_AUTH_DISABLED=1`, `PORT=8000`, `CONTINUUM_DB_PATH=/app/data/continuum.db` |
| **DASHSCOPE_API_KEY** | **Not set** (missing from `.env`) — UI/health work; **chat may degrade** until set in Render dashboard |
| **Label for judges** | Non-Alibaba fallback demo host |

Evidence screenshots (local): `docs/screenshots/render_invoke_poll_11.png`, `render_svc_continuum.png`

---

## Devpost submit status

| Item | Status |
|------|--------|
| Draft created | **Yes** — Continuum · submission `1106234-continuum` · **DRAFT** · **2/5 steps** |
| Edit URL | https://devpost.com/submit-to/29966-global-ai-hackathon-series-with-qwen-cloud/manage/submissions/1106234-continuum/finalization |
| Overview | Name **Continuum** + elevator pitch saved |
| Project details | About / links partially filled; **Video demo link still required** |
| Additional info | Page opened; required Qs listed but **not fully answered** via automation |
| Final Submit | Clicked — blocked: *“Please complete required fields in Project details and Additional info”* |
| Fully submitted? | **No** |

---

## Remaining human steps (only true blockers)

Open the draft (Chrome already logged in):  
https://devpost.com/submit-to/29966-global-ai-hackathon-series-with-qwen-cloud/manage/submissions/1106234-continuum/project_details/edit

1. **Project details**
   - Confirm **About the project** text (paste from [DEVPOST_SUBMIT_PACKET.md](DEVPOST_SUBMIT_PACKET.md) if empty).
   - **Built with:** add tags including **Qwen Cloud** (plus FastAPI/Docker/etc.).
   - **Try it out:** `https://continuum-8hwx.onrender.com/`
   - **GitHub / code link:** `https://github.com/kenhuangus/continuum`
   - **Video demo link (required):** upload `demo_video/continuum_demo.mp4` to YouTube (public/unlisted) → paste URL. *(No YouTube URL available to the agent.)*
   - Optional: upload `docs/architecture.png` to Image gallery.
   - Select track **MemoryAgent** if shown on this form.
   - Click **Save & continue**.

2. **Additional info** (tab in stepper)
   - Submitter type → **Individual**
   - Country → **United States** (or yours)
   - Newly built vs existing → answer (e.g. **newly built**)
   - Start date → e.g. hackathon period date
   - Any other required custom questions
   - **Save & continue**

3. **Submit**
   - Check Official Rules / Terms checkbox
   - Click **Submit project**
   - Confirm status is no longer **DRAFT**

4. **Optional:** Render dashboard → continuum service → Environment → add `DASHSCOPE_API_KEY` so judge chat works.

5. **Optional Alibaba PoD:** only if still required — human **Start for Free** free ECS (no paid SKUs), then deploy Docker.

---

## Related

- [FREE_HOSTING_OPTIONS.md](FREE_HOSTING_OPTIONS.md)
- `render.yaml` (repo root)
- [DEVPOST_SUBMIT_PACKET.md](DEVPOST_SUBMIT_PACKET.md)
