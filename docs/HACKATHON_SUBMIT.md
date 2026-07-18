# Continuum — Hackathon Submission Ship Plan

**Hackathon:** [Global AI Hackathon Series with Qwen Cloud](https://qwencloud-hackathon.devpost.com/)  
**Track:** Track 1 — MemoryAgent  
**Deadline:** Monday, **July 20, 2026 @ 2:00pm PDT** (= 5:00pm EDT). **No further extensions.**  
**Judging Period:** Jul 28 – Aug 11, 2026 (demo/test access must stay live through then)  
**Owner:** kenhuangus@gmail.com  
**As-of:** 2026-07-18  

Official sources: [Requirements](https://qwencloud-hackathon.devpost.com/) · [Rules](https://qwencloud-hackathon.devpost.com/rules) · [Resources](https://qwencloud-hackathon.devpost.com/resources) · [Updates](https://qwencloud-hackathon.devpost.com/updates) · [Proof of Deployment 101](https://qwencloud-hackathon.devpost.com/updates/45055-proof-of-deployment-101-what-judges-need-to-see) · [Last Weekend Sprint](https://qwencloud-hackathon.devpost.com/updates/45369-this-is-it-your-last-weekend-to-build)

---

## 1. Required deliverables (official)

| # | Deliverable | What judges need | Continuum status | Gap | Owner action |
|---|-------------|------------------|------------------|-----|--------------|
| 1 | **Public GitHub repo + OSI license** | Public repo with all source + run instructions; open-source **LICENSE at repo root** detectable in GitHub About | **PARTIAL** | `LICENSE` (Apache-2.0) and README exist locally, but git has **no commits**, **no remote**, repo not public | `git init` history → push public GitHub; confirm LICENSE shows in About; fill description / topics |
| 2 | **Proof of Alibaba Cloud deployment** | (a) Devpost field: link to **code file** using Alibaba/Qwen Cloud APIs (Base URL visible); (b) **Workbench screenshot** of running Alibaba resources ([PoD 101](https://qwencloud-hackathon.devpost.com/updates/45055-proof-of-deployment-101-what-judges-need-to-see)); project must have **actually run** on Alibaba Cloud, not localhost-only | **PARTIAL** | Code-link ready (`client.py` DashScope base URL). Docker + ECS/ACR scaffolding in `infra/` + fill-in [PROOF_OF_ALIBABA_DEPLOYMENT.md](PROOF_OF_ALIBABA_DEPLOYMENT.md). **Still pending:** live ECS run, Workbench screenshot (`docs/screenshots/alibaba_workbench.png`), filled `PUBLIC_URL` / `INSTANCE_ID` / `REGION` | Follow [infra/ecs/DEPLOY.md](../infra/ecs/DEPLOY.md); capture screenshot; fill proof placeholders; paste code-file link + screenshot on Devpost |
| 3 | **Architecture diagram** | Clear visual: Qwen Cloud ↔ backend ↔ DB ↔ frontend | **DONE** (local) | `docs/architecture.md` + `docs/architecture.mmd` exist; Devpost needs an **image** judges can open | Export PNG/SVG from mermaid; attach on Devpost; keep markdown as source of truth |
| 4 | **~3 min public demo video** | ≤3 min (judges not required past 3); **working product** footage; public on **YouTube, Vimeo, or Youku** (rules). Main page also lists Facebook Video — prefer YT/Vimeo/Youku | **MISSING** | No recorded/published video | Script Session A→B + forget + pack budget; record; upload **public**; leave hours for processing |
| 5 | **Text description + track** | English description of features/functionality; track = **MemoryAgent** | **PARTIAL** | Strong copy in `prd.md` / README; nothing on Devpost yet | Paste track + description; name **Qwen Cloud** in description and Built With |
| 6 | **Working demo / test access** | Link to website, functioning demo, or test build; credentials if private; free access through **Judging Period end** | **PARTIAL** | Local demo works (`uvicorn` + `/`); **not** publicly reachable | Public HTTPS URL on Alibaba; testing instructions in README + Devpost; keep up through Aug 11 |
| 7 | **English materials** | All submission materials in English (or EN translation) | **DONE** | — | Keep video narration / captions in English |
| 8 | **Optional: Blog / social (Blog Prize)** | Public blog or social post about building with QwenCloud; URL on submission | **MISSING** | No published post | Optional: 800–1500 word build post or LinkedIn/X thread; link on Devpost |

### Devpost form fields to pre-fill (from rules + weekend checklist)

- Project title / tagline  
- Track: **MemoryAgent**  
- Repo URL (public)  
- Proof of deployment: **code file URL** (e.g. `.../blob/main/packages/agent/continuum_agent/client.py`)  
- Proof of deployment: **Alibaba Workbench screenshot**  
- Architecture diagram (image)  
- Demo video URL (public)  
- Text description (what / who / how)  
- Built With: **Qwen Cloud**, Alibaba Cloud, Python, FastAPI, …  
- Testing instructions + demo URL (+ login if any)  
- Optional blog/social URL  
- Team invites accepted  

---

## 2. Technical must-haves for eligibility

| Requirement | Official bar | Continuum status | Gap / action |
|-------------|--------------|------------------|--------------|
| **Uses Qwen Cloud models/APIs** | Project built with Qwen models on Qwen Cloud; Stage One pass/fail on required APIs | **PARTIAL → near DONE in code** | `QwenClient` targets DashScope intl compatible-mode; app can run **offline** without key. **Must** demo with live `DASHSCOPE_API_KEY` / `QWEN_API_KEY` and cite Qwen in materials |
| **Deployed on Alibaba Cloud** | Backend ran on Alibaba Cloud; code link + Workbench screenshot; “No proof = not eligible” | **MISSING** (live) | Highest DQ risk. Scaffolding is ready (`Dockerfile`, `infra/ecs/`); still need a real ECS container + public URL + Workbench screenshot — do not submit PoD until those exist |
| **Significantly updated in Submission Period** | New project **or** significant updates after **May 26, 2026 8:00am PT**; explain updates | **AT RISK** | No git history yet. Create public repo **now** with commit history before deadline; Devpost blurb: “built during Submission Period (Phase A MemoryAgent vertical slice)” |

Acceptable proof Base URLs (from PoD update):

- `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` ← **already in** `client.py`  
- Token Plan: `https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1` (or Anthropic-compatible variant)

---

## 3. “When all is fine” launch sequence

Ordered path from **product-ready** → **Devpost submitted**. Estimates assume Continuum core demo already works locally.

| Step | Action | Est. effort | Depends on |
|------|--------|-------------|------------|
| 0 | **Code freeze** for demo path (chat, pack, forget, Session A→B). Only fix blockers | 0.5 h | Product ready |
| 1 | Confirm live Qwen calls (`DASHSCOPE_API_KEY`); smoke Session A→B on staging | 0.5–1 h | Qwen Cloud account + API key (free tier OK) |
| 2 | **Alibaba deploy**: Dockerfile → ACR (or direct ECS) → public HTTPS; set secrets; health check | 3–8 h | Alibaba Cloud account, billing/free tier, domain or public IP |
| 3 | Capture **Workbench screenshot** of running resources; update `docs/PROOF_OF_ALIBABA_DEPLOYMENT.md` with real endpoints + code links | 0.5–1 h | Step 2 |
| 4 | Export **architecture diagram** PNG; spot-check README quickstart against deployed URL | 0.5 h | — |
| 5 | First git commits; push **public** GitHub; verify LICENSE in About | 0.5–1 h | GitHub account |
| 6 | Record **≤3 min** demo (script below); upload YouTube/Vimeo/Youku **public**; wait for processing | 2–4 h (+ processing lag) | Working demo URL or local+deploy footage |
| 7 | Draft Devpost text (track, description, Built With, “built during hackathon”, testing instructions) | 1 h | Copy from `prd.md` § executive / Devpost draft |
| 8 | Optional: publish blog/social for Blog Prize | 1–2 h | — |
| 9 | **Incognito link audit**: repo, LICENSE, video, live demo, architecture image, proof doc | 0.5 h | Steps 2–7 |
| 10 | Create/edit Devpost submission; fill all fields; attach screenshot + diagram | 0.5–1 h | Devpost registration |
| 11 | **Submit ≥4–6 h before** Jul 20 2pm PDT; do not change linked artifacts after deadline | 0.25 h | Step 10 |
| 12 | Keep demo + API keys funded through **Aug 11** judging | ongoing | Alibaba + Qwen quota |

**Demo video script (~2:45)** — maps to Track 1 pillars:

1. **0:00–0:20** — Problem: agents forget across sessions  
2. **0:20–1:10** — Session A: store preferences/decisions (show memory inspector)  
3. **1:10–1:50** — Session B: pack under budget; answer cites memory IDs  
4. **1:50–2:20** — Forgetting / supersession: stale fact retired  
5. **2:20–2:45** — Qwen Cloud + Alibaba deploy proof + Apache-2.0 / open Memory OS CTA  

---

## 4. Risk list (DQ or score damage)

| Risk | Severity | Why |
|------|----------|-----|
| **No Alibaba deploy / no Workbench screenshot** | **DQ** | Official update: “No proof = not eligible” |
| **Repo private or missing LICENSE** | **DQ** | Required; license must be detectable at top of repo |
| **Localhost-only demo** | **DQ / Stage One fail** | Must show backend on Alibaba; judges need test access |
| **Video missing, private, or mockup-only** | **DQ / tanks Presentation (15%)** | Must show real functioning project; ≤3 min |
| **No Qwen Cloud usage in live demo** | **Stage One fail** | Must use required APIs; name Qwen Cloud in Built With |
| **Wrong or missing track** | Eligibility / mis-judging | Must select MemoryAgent |
| **Post-deadline edits to repo/video/form** | **DQ flag** | Weekend update: do not touch after lock |
| **Demo down during judging (Jul 28–Aug 11)** | Score / testing fail | Rules require access through Judging Period |
| **Overclaiming vs Phase A** | Tanks Technical Depth / trust | Don’t claim hybrid RAG / knapsack / full MCP if not shipped — see `docs/MEMORY_SAAS_ASSESSMENT.md` |
| **No git history / “existing project” unexplained** | Eligibility challenge | Document significant build during May 26–Jul 20 window |
| **Skipping Blog post** | Miss $500 Blog Prize only | Optional; does not DQ main track |
| **Copyrighted music / third-party marks in video** | Possible DQ | Rules forbid without permission |

---

## 5. Continuum readiness snapshot (2026-07-18)

| Area | State |
|------|--------|
| Phase A vertical slice (pack → agent → ingest, SQLite, demo UI) | Implemented locally |
| Qwen client Base URL | Present in `client.py` |
| Alibaba infra / proof | Scaffolding ready (Docker/ECS/ACR); live deploy + screenshot pending |
| Public GitHub | Not published (no commits/remote) |
| Demo video / Devpost | Not started |
| Scientific/SaaS bar vs PRD | Not yet — see `MEMORY_SAAS_ASSESSMENT.md`; ship honest Phase A claims for hackathon |

**P0 before submit (eligibility):** public repo + LICENSE · real Alibaba deploy + screenshot · live Qwen demo · ≤3 min video · architecture image · Devpost MemoryAgent + English description + test URL.

**P1 for score (not eligibility):** tighten eval story, MCP if real, honest docs, optional blog.

---

## 6. Quick links (local)

- [README](../README.md) · [prd.md](../prd.md) · [architecture.md](architecture.md) · [PROOF_OF_ALIBABA_DEPLOYMENT.md](PROOF_OF_ALIBABA_DEPLOYMENT.md) · [MEMORY_SAAS_ASSESSMENT.md](MEMORY_SAAS_ASSESSMENT.md) · [LICENSE](../LICENSE) · `packages/agent/continuum_agent/client.py`

---

End of file. No other files.
