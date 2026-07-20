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
| Draft created | **Yes** — Continuum · submission `1106234-continuum` · **DRAFT** |
| Manage URL | https://devpost.com/submit-to/29966-global-ai-hackathon-series-with-qwen-cloud/manage/submissions/1106234-continuum/ |
| Edit URL | https://devpost.com/submit-to/29966-global-ai-hackathon-series-with-qwen-cloud/manage/submissions/1106234-continuum/project_details/edit |
| Finalization | https://devpost.com/submit-to/29966-global-ai-hackathon-series-with-qwen-cloud/manage/submissions/1106234-continuum/finalization |
| Video demo URL | **https://youtu.be/OftGzFIvAAs** (ready to paste; not yet saved via automation) |
| Try-it URL | `https://continuum-8hwx.onrender.com/` |
| Repo | `https://github.com/kenhuangus/continuum` |
| Built With | Must include **Qwen Cloud** |
| Fully submitted? | **No** — 2026-07-20 ~00:33: cursor-ide-browser MCP had **no persistent tab** (`navigate` → *No browser tab available*; created tabs vanished immediately) |

Evidence: [YOUTUBE_UPLOAD_RESULT.md](YOUTUBE_UPLOAD_RESULT.md)

---

## Remaining blocker (Browser panel)

Open the Continuum draft in **this chat’s Cursor Browser panel** (logged in), then re-run agent submit:

1. **Project details** — paste Video `https://youtu.be/OftGzFIvAAs`; Try-it `https://continuum-8hwx.onrender.com/`; Built with **Qwen Cloud**; repo `https://github.com/kenhuangus/continuum`; Save.
2. **Additional info** — complete required fields (Individual if needed; keep existing personal values).
3. **Submit** — check terms/rules → **Submit project** → confirm **Submitted** (not DRAFT). Screenshot → `docs/screenshots/devpost_submitted.png`.

4. **Optional:** Render → add `DASHSCOPE_API_KEY` so judge chat works.

5. **Optional Alibaba PoD:** only if still required — human **Start for Free** free ECS (no paid SKUs), then deploy Docker.

---

## Related

- [FREE_HOSTING_OPTIONS.md](FREE_HOSTING_OPTIONS.md)
- `render.yaml` (repo root)
- [DEVPOST_SUBMIT_PACKET.md](DEVPOST_SUBMIT_PACKET.md)
