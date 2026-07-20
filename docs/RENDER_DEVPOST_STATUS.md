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
| Attempts | **6** free-tier attempts failed — see [OVERNIGHT_STATUS.md](OVERNIGHT_STATUS.md) |

**Judge-facing explanation assets:**
- [ALIBABA_DEPLOYMENT_UNAVAILABLE.txt](ALIBABA_DEPLOYMENT_UNAVAILABLE.txt)
- [screenshots/alibaba_deployment_unavailable.png](screenshots/alibaba_deployment_unavailable.png)

Full log: [OVERNIGHT_STATUS.md](OVERNIGHT_STATUS.md). Alibaba PoD stays honest: [PROOF_OF_ALIBABA_DEPLOYMENT.md](PROOF_OF_ALIBABA_DEPLOYMENT.md).

---

## Render URL (Try-it — **not** Alibaba PoD)

| Item | Value |
|------|--------|
| **PUBLIC_URL** | **https://continuum-8hwx.onrender.com/** |
| **Health** | https://continuum-8hwx.onrender.com/v1/health → `{"status":"ok",...}` |
| **How** | Free Docker Web Service via Blueprint (`render.yaml`) |
| **Browser automation** | **Chrome UIA** (`pywinauto` + `chrome.exe` URL open + `PrintWindow`) — **not** cursor-ide-browser MCP / CDP. Skill: `active-chrome-browser-automation` |

Evidence screenshots: `docs/screenshots/render_invoke_poll_11.png`, `render_svc_continuum.png`

---

## Devpost submit status

| Item | Status |
|------|--------|
| Draft | Continuum · `1106234-continuum` |
| Manage URL | https://devpost.com/submit-to/29966-global-ai-hackathon-series-with-qwen-cloud/manage/submissions/1106234-continuum/ |
| Video | **https://youtu.be/OftGzFIvAAs** |
| Try-it | `https://continuum-8hwx.onrender.com/` |
| Repo | `https://github.com/kenhuangus/continuum` |
| Alibaba explanation | PNG + TXT uploaded / attached via Chrome UIA when possible |
| Fully submitted? | See `docs/_devpost_submit_progress.json` + `docs/screenshots/devpost11_submitted.png` |

---

## Related

- Skill (personal): `~/.cursor/skills/active-chrome-browser-automation/SKILL.md`
- Skill (project): `.cursor/skills/active-chrome-browser-automation/SKILL.md`
- Scripts: `scripts/_render_invoke_deploy.py`, `scripts/_devpost_upload_unavailable_submit.py`
